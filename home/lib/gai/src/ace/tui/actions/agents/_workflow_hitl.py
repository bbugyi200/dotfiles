"""Agent workflow human-in-the-loop methods for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models import Agent


class AgentWorkflowHITLMixin:
    """Mixin providing workflow human-in-the-loop methods.

    Type hints below declare attributes that are defined at runtime by AceApp.
    """

    def _edit_hitl_output(self, output: object) -> object | None:
        """Open HITL output in editor for user modification.

        Args:
            output: The output data to edit.

        Returns:
            The edited data, or None if cancelled/error.
        """
        import os
        import subprocess
        import tempfile

        import yaml  # type: ignore[import-untyped]
        from shared_utils import dump_yaml

        # Unwrap _data if present
        data = output.get("_data", output) if isinstance(output, dict) else output

        # Convert to YAML
        yaml_content = dump_yaml(data, sort_keys=False)

        # Create temp file
        fd, temp_path = tempfile.mkstemp(suffix=".yml", prefix="workflow_edit_")
        os.close(fd)

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        # Open in editor with TUI suspended
        editor = os.environ.get("EDITOR", "nvim")
        with self.suspend():  # type: ignore[attr-defined]
            subprocess.run([editor, temp_path], check=False)

        # Read edited content
        with open(temp_path, encoding="utf-8") as f:
            edited_content = f.read()

        os.unlink(temp_path)

        if not edited_content.strip():
            return None

        # Parse YAML back to dict
        try:
            edited_data = yaml.safe_load(edited_content)
            # Re-wrap in _data if original was wrapped
            if isinstance(output, dict) and "_data" in output:
                return {"_data": edited_data}
            return edited_data
        except yaml.YAMLError as e:
            self.notify(f"Invalid YAML: {e}", severity="error")  # type: ignore[attr-defined]
            return None

    def _answer_workflow_hitl(self, agent: Agent) -> None:
        """Answer a workflow HITL prompt.

        Reads the hitl_request.json file, shows a modal with options,
        and writes the response to hitl_response.json.

        Args:
            agent: The workflow agent with WAITING INPUT status.
        """
        import json
        from pathlib import Path

        from ...modals import WorkflowHITLInput, WorkflowHITLModal
        from ...models.agent import AgentType

        if agent.agent_type != AgentType.WORKFLOW:
            self.notify("Not a workflow agent", severity="error")  # type: ignore[attr-defined]
            return

        if agent.raw_suffix is None:
            self.notify("Cannot find workflow artifacts", severity="error")  # type: ignore[attr-defined]
            return

        # Extract project name from project_file
        project_path = Path(agent.project_file)
        project_name = project_path.parent.name

        # Build path to hitl_request.json
        artifacts_dir = (
            Path.home()
            / ".gai"
            / "projects"
            / project_name
            / "artifacts"
            / f"workflow-{agent.workflow}"
            / agent.raw_suffix
        )
        request_path = artifacts_dir / "hitl_request.json"

        if not request_path.exists():
            self.notify("No HITL request found", severity="warning")  # type: ignore[attr-defined]
            return

        # Read the request file
        try:
            with open(request_path, encoding="utf-8") as f:
                request_data = json.load(f)
        except Exception as e:
            self.notify(f"Error reading HITL request: {e}", severity="error")  # type: ignore[attr-defined]
            return

        # Create input data for modal
        input_data = WorkflowHITLInput(
            step_name=request_data.get("step_name", "unknown"),
            step_type=request_data.get("step_type", "agent"),
            output=request_data.get("output", {}),
            workflow_name=agent.workflow or "unknown",
            has_output=request_data.get("has_output", False),
        )

        # Show the HITL modal
        def on_dismiss(result: object) -> None:
            from xprompt import HITLResult

            if result is None:
                return

            # Verify result is HITLResult
            if not isinstance(result, HITLResult):
                return

            # Handle edit action - open editor in TUI process
            if result.action == "edit":
                edited_output = self._edit_hitl_output(request_data.get("output", {}))
                if edited_output is not None:
                    result = HITLResult(action="edit", edited_output=edited_output)
                else:
                    # User cancelled or error - abort
                    return

            # Write response file
            response_path = artifacts_dir / "hitl_response.json"
            response_data = {
                "action": result.action,
                "approved": result.approved,
            }
            if result.edited_output is not None:
                response_data["edited_output"] = result.edited_output
            if result.feedback is not None:
                response_data["feedback"] = result.feedback

            try:
                with open(response_path, "w", encoding="utf-8") as f:
                    json.dump(response_data, f, indent=2, default=str)
                self.notify(f"Sent {result.action} response")  # type: ignore[attr-defined]
            except Exception as e:
                self.notify(f"Error writing response: {e}", severity="error")  # type: ignore[attr-defined]

            # Refresh agents after a short delay to pick up status change
            self.call_later(self._load_agents)  # type: ignore[attr-defined]

        self.push_screen(WorkflowHITLModal(input_data), on_dismiss)  # type: ignore[attr-defined]
