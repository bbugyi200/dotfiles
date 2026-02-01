"""Workflow execution engine for multi-step agent workflows."""

import json
import os
import re
import subprocess
from datetime import datetime
from typing import Any, Protocol

from jinja2 import Environment, StrictUndefined

from xprompt.workflow_models import (
    StepState,
    StepStatus,
    Workflow,
    WorkflowExecutionError,
    WorkflowState,
    WorkflowStep,
)


class HITLHandler(Protocol):
    """Protocol for human-in-the-loop handlers."""

    def prompt(
        self,
        step_name: str,
        step_type: str,
        output: Any,
    ) -> "HITLResult":
        """Prompt the user for action on step output.

        Args:
            step_name: Name of the step being reviewed.
            step_type: Either "agent" or "bash".
            output: The step's output data.

        Returns:
            HITLResult indicating the user's decision.
        """
        ...


class HITLResult:
    """Result of a HITL prompt."""

    def __init__(
        self,
        action: str,
        feedback: str | None = None,
        approved: bool = False,
        edited_output: Any = None,
    ) -> None:
        """Initialize HITL result.

        Args:
            action: One of "accept", "edit", "reject", "rerun", or "feedback".
            feedback: User feedback text (for "feedback" action).
            approved: Whether the user approved (for confirmation prompts).
            edited_output: Edited data from user (for "edit" action).
        """
        self.action = action
        self.feedback = feedback
        self.approved = approved
        self.edited_output = edited_output


def _create_jinja_env() -> Environment:
    """Create a Jinja2 environment for template rendering."""
    env = Environment(undefined=StrictUndefined)
    # Add tojson filter
    env.filters["tojson"] = json.dumps
    return env


def _render_template(template: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 template with the given context.

    Args:
        template: The template string with {{ var }} placeholders.
        context: Dictionary of variable values.

    Returns:
        The rendered template string.
    """
    env = _create_jinja_env()
    jinja_template = env.from_string(template)
    return jinja_template.render(context)


def _parse_bash_output(output: str) -> dict[str, Any]:
    """Parse bash command output into a dictionary.

    Supports three formats:
    1. JSON: {"key": "value", ...}
    2. Key=Value: Each line is key=value
    3. Positional: Each line is a value (keys must be inferred from schema)

    Args:
        output: The command output string.

    Returns:
        Dictionary of parsed values.
    """
    output = output.strip()

    # Try JSON first
    if output.startswith("{") or output.startswith("["):
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass

    # Try key=value format
    result: dict[str, Any] = {}
    lines = output.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for key=value pattern
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)=(.*)$", line)
        if match:
            key, value = match.groups()
            result[key] = value
        else:
            # If we find a line without =, treat whole output as text
            # This handles multi-line values
            if not result:
                return {"_output": output}

    return result


class WorkflowExecutor:
    """Executes workflow steps sequentially with context accumulation."""

    def __init__(
        self,
        workflow: Workflow,
        args: dict[str, Any],
        artifacts_dir: str,
        hitl_handler: HITLHandler | None = None,
    ) -> None:
        """Initialize the workflow executor.

        Args:
            workflow: The workflow to execute.
            args: Input arguments matching workflow.inputs.
            artifacts_dir: Directory for workflow artifacts.
            hitl_handler: Optional handler for HITL prompts.
        """
        self.workflow = workflow
        self.context: dict[str, Any] = dict(args)
        self.artifacts_dir = artifacts_dir
        self.hitl_handler = hitl_handler

        # Initialize state
        self.state = WorkflowState(
            workflow_name=workflow.name,
            status="running",
            current_step_index=0,
            steps=[
                StepState(name=step.name, status=StepStatus.PENDING)
                for step in workflow.steps
            ],
            context=dict(args),
            artifacts_dir=artifacts_dir,
            start_time=datetime.now().isoformat(),
        )

    def _save_state(self) -> None:
        """Save workflow state to JSON file."""
        state_path = os.path.join(self.artifacts_dir, "workflow_state.json")
        state_dict = {
            "workflow_name": self.state.workflow_name,
            "status": self.state.status,
            "current_step_index": self.state.current_step_index,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "output": s.output,
                    "error": s.error,
                }
                for s in self.state.steps
            ],
            "context": self.state.context,
            "artifacts_dir": self.state.artifacts_dir,
            "start_time": self.state.start_time,
        }
        os.makedirs(self.artifacts_dir, exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state_dict, f, indent=2)

    def execute(self) -> bool:
        """Execute all workflow steps sequentially.

        Returns:
            True if workflow completed successfully, False otherwise.
        """
        self._save_state()

        for i, step in enumerate(self.workflow.steps):
            self.state.current_step_index = i
            step_state = self.state.steps[i]
            step_state.status = StepStatus.IN_PROGRESS
            self._save_state()

            try:
                if step.is_agent_step():
                    success = self._execute_agent_step(step, step_state)
                else:
                    success = self._execute_bash_step(step, step_state)

                if not success:
                    step_state.status = StepStatus.FAILED
                    self.state.status = "failed"
                    self._save_state()
                    return False

                step_state.status = StepStatus.COMPLETED
                self._save_state()

            except Exception as e:
                step_state.status = StepStatus.FAILED
                step_state.error = str(e)
                self.state.status = "failed"
                self._save_state()
                raise WorkflowExecutionError(f"Step '{step.name}' failed: {e}") from e

        self.state.status = "completed"
        self._save_state()
        return True

    def _execute_agent_step(
        self,
        step: WorkflowStep,
        step_state: StepState,
    ) -> bool:
        """Execute an agent step.

        Args:
            step: The workflow step definition.
            step_state: The runtime state for this step.

        Returns:
            True if step succeeded, False if rejected by user.
        """
        from gemini_wrapper import invoke_agent
        from shared_utils import ensure_str_content

        from xprompt import (
            extract_structured_content,
            generate_format_instructions,
            get_primary_output_schema,
            process_xprompt_references,
            validate_response,
        )
        from xprompt.output_validation import OutputValidationError

        if not step.prompt:
            raise WorkflowExecutionError(f"Agent step '{step.name}' has no prompt")

        # Render prompt with Jinja2 context
        rendered_prompt = _render_template(step.prompt, self.context)

        # Get output schema before expansion
        output_spec = get_primary_output_schema(rendered_prompt)

        # Expand xprompt references
        expanded_prompt = process_xprompt_references(rendered_prompt)

        # Add format instructions if output schema exists
        if output_spec is not None:
            format_instructions = generate_format_instructions(output_spec)
            if format_instructions:
                expanded_prompt += format_instructions

        # Invoke agent
        response = invoke_agent(
            expanded_prompt,
            agent_type=f"workflow-{self.workflow.name}-{step.name}",
            artifacts_dir=self.artifacts_dir,
            workflow=self.workflow.name,
        )
        response_text = ensure_str_content(response.content)

        # Parse and validate output
        output: dict[str, Any] = {}
        validation_error: str | None = None

        if step.output and output_spec is not None:
            try:
                data, validation_error = validate_response(response_text, output_spec)
                if isinstance(data, dict):
                    output = data
                else:
                    output = {"_data": data}
                if validation_error:
                    output["_validation_error"] = validation_error
            except OutputValidationError as e:
                # Could not parse JSON/YAML at all
                output = {"_raw": response_text, "_validation_error": e.message}
                validation_error = e.message
        elif step.output:
            try:
                data, _ = extract_structured_content(response_text)
                if isinstance(data, dict):
                    output = data
                else:
                    output = {"_data": data}
            except Exception:
                output = {"_raw": response_text}
        else:
            output = {"_raw": response_text}

        # Fail if validation error and no HITL to handle it
        if validation_error and not (step.hitl and self.hitl_handler):
            raise WorkflowExecutionError(
                f"Step '{step.name}' output validation failed: {validation_error}"
            )

        # HITL review if required
        if step.hitl and self.hitl_handler:
            step_state.status = StepStatus.WAITING_HITL
            self.state.status = "waiting_hitl"
            self._save_state()

            result = self.hitl_handler.prompt(step.name, "agent", output)

            if result.action == "reject":
                return False
            elif result.action == "accept":
                pass  # Continue with output as-is
            elif result.action == "edit":
                if result.edited_output is not None:
                    output = result.edited_output
                # Continue with edited output
            # Future: handle feedback for regeneration

        # Store output in context under step name
        step_state.output = output
        self.context[step.name] = output
        self.state.context = dict(self.context)

        return True

    def _execute_bash_step(
        self,
        step: WorkflowStep,
        step_state: StepState,
    ) -> bool:
        """Execute a bash step.

        Args:
            step: The workflow step definition.
            step_state: The runtime state for this step.

        Returns:
            True if step succeeded, False if rejected by user.
        """
        if not step.bash:
            raise WorkflowExecutionError(f"Bash step '{step.name}' has no command")

        # Render command with Jinja2 context
        rendered_command = _render_template(step.bash, self.context)

        # Execute command
        try:
            result = subprocess.run(
                rendered_command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
            )
        except Exception as e:
            raise WorkflowExecutionError(
                f"Failed to execute bash step '{step.name}': {e}"
            ) from e

        if result.returncode != 0:
            error_msg = (
                result.stderr.strip()
                if result.stderr
                else f"Exit code {result.returncode}"
            )
            raise WorkflowExecutionError(f"Bash step '{step.name}' failed: {error_msg}")

        # Parse output
        output = _parse_bash_output(result.stdout)

        # Validate output against schema if specified
        if step.output and step.output.schema:
            from .output_validation import validate_against_schema

            is_valid, validation_err = validate_against_schema(
                output, step.output.schema
            )
            if not is_valid:
                raise WorkflowExecutionError(
                    f"Bash step '{step.name}' output validation failed: {validation_err}"
                )

        # HITL review if required
        if step.hitl and self.hitl_handler:
            step_state.status = StepStatus.WAITING_HITL
            self.state.status = "waiting_hitl"
            self._save_state()

            result_hitl = self.hitl_handler.prompt(step.name, "bash", output)

            if result_hitl.action == "reject":
                return False
            elif result_hitl.action == "accept":
                # Set approved flag in output for subsequent steps
                output["approved"] = True
            # Future: handle rerun

        # Store output in context under step name
        step_state.output = output
        self.context[step.name] = output
        self.state.context = dict(self.context)

        return True
