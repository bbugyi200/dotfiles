"""Agent launch mixin for the ace TUI app."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..models import Agent


class AgentLaunchMixin:
    """Internal mixin providing agent launching functionality."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    marked_indices: set[int]
    _agents: list[Agent]

    # State for bulk agent runs (from AgentWorkflowMixin)
    _bulk_changespecs: list[ChangeSpec] | None = None
    # State for prompt input (from AgentWorkflowMixin)
    _prompt_context: object | None = None

    def _finish_agent_launch(self, prompt: str) -> None:
        """Complete agent launch with the given prompt.

        Args:
            prompt: The user's prompt for the agent.
        """
        if self._prompt_context is None:
            self.notify("No prompt context - cannot launch", severity="error")  # type: ignore[attr-defined]
            return

        # Unmount prompt bar first
        self._unmount_prompt_bar()  # type: ignore[attr-defined]

        # Check if this is a bulk run
        if self._bulk_changespecs:
            self._launch_bulk_agents(prompt)
            return

        ctx = self._prompt_context
        self._prompt_context = None

        # Launch single background agent
        self._launch_background_agent(
            cl_name=ctx.display_name,  # type: ignore[attr-defined]
            project_file=ctx.project_file,  # type: ignore[attr-defined]
            workspace_dir=ctx.workspace_dir,  # type: ignore[attr-defined]
            workspace_num=ctx.workspace_num,  # type: ignore[attr-defined]
            workflow_name=ctx.workflow_name,  # type: ignore[attr-defined]
            prompt=prompt,
            timestamp=ctx.timestamp,  # type: ignore[attr-defined]
            new_cl_name=ctx.new_cl_name,  # type: ignore[attr-defined]
            parent_cl_name=ctx.parent_cl_name,  # type: ignore[attr-defined]
            update_target=ctx.update_target,  # type: ignore[attr-defined]
            project_name=ctx.project_name,  # type: ignore[attr-defined]
            history_sort_key=ctx.history_sort_key,  # type: ignore[attr-defined]
            bug=ctx.bug,  # type: ignore[attr-defined]
            fixed_bug=ctx.fixed_bug,  # type: ignore[attr-defined]
        )

        # Refresh agents list (deferred to avoid lag)
        self.call_later(self._load_agents)  # type: ignore[attr-defined]
        self.notify(f"Agent started for {ctx.display_name}")  # type: ignore[attr-defined]

    def _launch_bulk_agents(self, prompt: str) -> None:
        """Launch agents for all bulk changespecs.

        Args:
            prompt: The user's prompt for all agents.
        """
        from gai_utils import generate_timestamp
        from running_field import (
            get_first_available_axe_workspace,
            get_workspace_directory_for_num,
        )

        if not self._bulk_changespecs:
            self.notify("No bulk changespecs", severity="error")  # type: ignore[attr-defined]
            return

        changespecs = self._bulk_changespecs
        self._bulk_changespecs = None

        # Extract new_cl_name before clearing context
        new_cl_name = self._prompt_context.new_cl_name if self._prompt_context else None  # type: ignore[attr-defined]
        self._prompt_context = None

        launched_count = 0
        failed_count = 0

        for cs in changespecs:
            project_name = cs.project_basename
            cl_name = cs.name

            project_file = os.path.expanduser(
                f"~/.gai/projects/{project_name}/{project_name}.gp"
            )

            if not os.path.isfile(project_file):
                self.notify(f"No project file for {cl_name}", severity="warning")  # type: ignore[attr-defined]
                failed_count += 1
                continue

            try:
                workspace_num = get_first_available_axe_workspace(project_file)
                timestamp = generate_timestamp()
                workflow_name = f"ace(run)-{timestamp}"
                workspace_dir, _ = get_workspace_directory_for_num(
                    workspace_num, project_name
                )
            except RuntimeError as e:
                self.notify(f"Workspace error for {cl_name}: {e}", severity="warning")  # type: ignore[attr-defined]
                failed_count += 1
                continue

            self._launch_background_agent(
                cl_name=cl_name,
                project_file=project_file,
                workspace_dir=workspace_dir,
                workspace_num=workspace_num,
                workflow_name=workflow_name,
                prompt=prompt,
                timestamp=timestamp,
                new_cl_name=new_cl_name,
                parent_cl_name=cl_name,
                update_target=cl_name,
                project_name=project_name,
                history_sort_key=cl_name,
            )
            launched_count += 1

        # Clear marks after bulk launch
        self.marked_indices = set()  # type: ignore[assignment]
        self._refresh_display()  # type: ignore[attr-defined]

        # Refresh agents list
        self.call_later(self._load_agents)  # type: ignore[attr-defined]

        # Show summary notification
        if failed_count > 0:
            self.notify(  # type: ignore[attr-defined]
                f"Started {launched_count} agent(s), {failed_count} failed",
                severity="warning",
            )
        else:
            self.notify(f"Started {launched_count} agent(s)")  # type: ignore[attr-defined]

    def _launch_background_agent(
        self,
        cl_name: str,
        project_file: str,
        workspace_dir: str,
        workspace_num: int,
        workflow_name: str,
        prompt: str,
        timestamp: str,
        new_cl_name: str | None = None,
        parent_cl_name: str | None = None,
        update_target: str = "",
        project_name: str = "",
        history_sort_key: str = "",
        bug: str | None = None,
        fixed_bug: str | None = None,
    ) -> None:
        """Launch agent as background process.

        Args:
            cl_name: Display name for the CL/project.
            project_file: Path to the project file.
            workspace_dir: Path to the workspace directory.
            workspace_num: The workspace number.
            workflow_name: Name for the workflow.
            prompt: The user's prompt for the agent.
            timestamp: Shared timestamp for artifacts.
            new_cl_name: If provided, create a new ChangeSpec with this name.
            parent_cl_name: The parent CL name for the new ChangeSpec (if any).
            update_target: What to checkout (CL name or "p4head").
            project_name: Project name for prompt history tracking.
            history_sort_key: CL name to associate with the prompt in history.
            bug: Bug number to associate with a new ChangeSpec (BUG: field).
            fixed_bug: Bug number for FIXED: field (mutually exclusive with bug).
        """
        import subprocess
        import tempfile

        from gai_utils import ensure_gai_directory

        # Write prompt to temp file (runner will read and delete)
        fd, prompt_file = tempfile.mkstemp(suffix=".md", prefix="gai_ace_prompt_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)

        # Get output file path
        workflows_dir = ensure_gai_directory("workflows")
        # Sanitize cl_name for filename
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in cl_name)
        output_path = os.path.join(
            workflows_dir, f"{safe_name}_ace-run-{timestamp}.txt"
        )

        # Build runner script path
        # From src/ace/tui/actions/ we need 4 dirname calls to get to src/
        runner_script = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            ),
            "axe_run_agent_runner.py",
        )

        # Start background process first to get actual PID
        # Args: cl_name, project_file, workspace_dir, output_path, workspace_num,
        #       workflow_name, prompt_file, timestamp, new_cl_name, parent_cl_name,
        #       update_target, project_name, history_sort_key, bug, fixed_bug
        try:
            with open(output_path, "w") as output_file:
                process = subprocess.Popen(
                    [
                        "python3",
                        runner_script,
                        cl_name,
                        project_file,
                        workspace_dir,
                        output_path,
                        str(workspace_num),
                        workflow_name,
                        prompt_file,
                        timestamp,
                        new_cl_name or "",
                        parent_cl_name or "",
                        update_target,
                        project_name,
                        history_sort_key,
                        bug or "",
                        fixed_bug or "",
                    ],
                    cwd=workspace_dir,
                    stdout=output_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # Detach from TUI process
                    env=os.environ,
                )
        except Exception as e:
            self.notify(f"Failed to start agent: {e}", severity="error")  # type: ignore[attr-defined]
            return

        # Claim workspace with actual subprocess PID
        from running_field import claim_workspace

        if not claim_workspace(
            project_file,
            workspace_num,
            workflow_name,
            process.pid,
            cl_name,
            artifacts_timestamp=timestamp,
            new_cl_name=new_cl_name,
        ):
            self.notify(  # type: ignore[attr-defined]
                "Failed to claim workspace, terminating agent", severity="error"
            )
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            return
