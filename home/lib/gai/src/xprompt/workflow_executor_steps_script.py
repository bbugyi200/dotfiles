"""Script step execution mixin (bash and python steps)."""

import os
import subprocess
import sys
from typing import TYPE_CHECKING, Any

from xprompt.workflow_executor_types import HITLHandler
from xprompt.workflow_executor_utils import parse_bash_output, render_template
from xprompt.workflow_models import (
    StepState,
    StepStatus,
    WorkflowExecutionError,
    WorkflowState,
)

if TYPE_CHECKING:
    from xprompt.workflow_models import WorkflowStep
    from xprompt.workflow_output import WorkflowOutputHandler


class ScriptStepMixin:
    """Mixin class providing bash and python step execution.

    This mixin requires the following attributes on self:
        - context: dict[str, Any]
        - artifacts_dir: str
        - hitl_handler: HITLHandler | None
        - state: WorkflowState

    This mixin requires the following methods on self:
        - _save_state() -> None
        - _save_prompt_step_marker(step_name, step_state, ...) -> None
    """

    # Type hints for attributes from WorkflowExecutor
    context: dict[str, Any]
    artifacts_dir: str
    hitl_handler: HITLHandler | None
    output_handler: "WorkflowOutputHandler | None"
    state: WorkflowState

    # Method stubs for type checking - implemented in main class
    def _save_state(self) -> None:
        """Save workflow state to JSON file."""
        raise NotImplementedError

    def _save_prompt_step_marker(
        self,
        step_name: str,
        step_state: StepState,
        step_type: str = "prompt",
        step_source: str | None = None,
        step_index: int | None = None,
        parent_step_index: int | None = None,
        parent_total_steps: int | None = None,
        is_pre_prompt_step: bool = False,
        diff_path: str | None = None,
        hidden: bool = False,
    ) -> None:
        """Save a marker file for prompt steps to track them in the TUI."""
        raise NotImplementedError

    def _execute_bash_step(
        self,
        step: "WorkflowStep",
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
        rendered_command = render_template(step.bash, self.context)

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
        output = parse_bash_output(result.stdout)

        # Validate output against schema if specified
        if step.output and step.output.schema:
            from xprompt.output_validation import validate_against_schema

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
            self._save_prompt_step_marker(
                step.name,
                step_state,
                step_type="bash",
                step_source=rendered_command,
                hidden=step.hidden,
            )

            result_hitl = self.hitl_handler.prompt(
                step.name, "bash", output, has_output=step.output is not None
            )

            if result_hitl.action == "reject":
                return False
            elif result_hitl.action == "accept":
                # Set approved flag in output for subsequent steps
                output["approved"] = True
            elif result_hitl.action == "edit":
                if result_hitl.edited_output is not None:
                    output = result_hitl.edited_output
                # Continue with edited output
            # Future: handle rerun

        # Mark step completed after HITL
        step_state.status = StepStatus.COMPLETED
        self._save_prompt_step_marker(
            step.name,
            step_state,
            step_type="bash",
            step_source=rendered_command,
            hidden=step.hidden,
        )

        # Store output in context under step name
        step_state.output = output
        self.context[step.name] = output
        self.state.context = dict(self.context)

        return True

    def _execute_python_step(
        self,
        step: "WorkflowStep",
        step_state: StepState,
    ) -> bool:
        """Execute a python step.

        Args:
            step: The workflow step definition.
            step_state: The runtime state for this step.

        Returns:
            True if step succeeded, False if rejected by user.
        """
        if not step.python:
            raise WorkflowExecutionError(f"Python step '{step.name}' has no code")

        # Render code with Jinja2 context
        rendered_code = render_template(step.python, self.context)

        # Execute python code using the same interpreter
        try:
            result = subprocess.run(
                [sys.executable, "-c", rendered_code],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
            )
        except Exception as e:
            raise WorkflowExecutionError(
                f"Failed to execute python step '{step.name}': {e}"
            ) from e

        if result.returncode != 0:
            error_msg = (
                result.stderr.strip()
                if result.stderr
                else f"Exit code {result.returncode}"
            )
            raise WorkflowExecutionError(
                f"Python step '{step.name}' failed: {error_msg}"
            )

        # Parse output (same formats as bash: JSON, key=value, plain text)
        output = parse_bash_output(result.stdout)

        # Validate output against schema if specified
        if step.output and step.output.schema:
            from xprompt.output_validation import validate_against_schema

            is_valid, validation_err = validate_against_schema(
                output, step.output.schema
            )
            if not is_valid:
                raise WorkflowExecutionError(
                    f"Python step '{step.name}' output validation failed: "
                    f"{validation_err}"
                )

        # HITL review if required
        if step.hitl and self.hitl_handler:
            step_state.status = StepStatus.WAITING_HITL
            self.state.status = "waiting_hitl"
            self._save_state()
            self._save_prompt_step_marker(
                step.name,
                step_state,
                step_type="python",
                step_source=rendered_code,
                hidden=step.hidden,
            )

            result_hitl = self.hitl_handler.prompt(
                step.name, "python", output, has_output=step.output is not None
            )

            if result_hitl.action == "reject":
                return False
            elif result_hitl.action == "accept":
                # Set approved flag in output for subsequent steps
                output["approved"] = True
            elif result_hitl.action == "edit":
                if result_hitl.edited_output is not None:
                    output = result_hitl.edited_output
                # Continue with edited output
            # Future: handle rerun

        # Mark step completed after HITL
        step_state.status = StepStatus.COMPLETED
        self._save_prompt_step_marker(
            step.name,
            step_state,
            step_type="python",
            step_source=rendered_code,
            hidden=step.hidden,
        )

        # Store output in context under step name
        step_state.output = output
        self.context[step.name] = output
        self.state.context = dict(self.context)

        return True
