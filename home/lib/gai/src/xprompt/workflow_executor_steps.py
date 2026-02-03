"""Step execution mixin for workflow execution."""

import os
import subprocess
import sys
from typing import TYPE_CHECKING, Any

from xprompt.workflow_executor_types import HITLHandler
from xprompt.workflow_executor_utils import parse_bash_output, render_template
from xprompt.workflow_models import (
    StepState,
    StepStatus,
    Workflow,
    WorkflowExecutionError,
    WorkflowState,
    WorkflowStep,
)

if TYPE_CHECKING:
    from xprompt.workflow_output import WorkflowOutputHandler


class StepMixin:
    """Mixin class providing step execution functionality for WorkflowExecutor.

    This mixin requires the following attributes on self:
        - workflow: Workflow
        - context: dict[str, Any]
        - artifacts_dir: str
        - hitl_handler: HITLHandler | None
        - output_handler: WorkflowOutputHandler | None
        - state: WorkflowState

    This mixin requires the following methods on self:
        - _save_state() -> None
        - _save_agent_step_marker(step_name, step_state) -> None
    """

    # Type hints for attributes from WorkflowExecutor
    workflow: Workflow
    context: dict[str, Any]
    artifacts_dir: str
    hitl_handler: HITLHandler | None
    output_handler: "WorkflowOutputHandler | None"
    state: WorkflowState

    # Method stubs for type checking - implemented in main class
    def _save_state(self) -> None:
        """Save workflow state to JSON file."""
        raise NotImplementedError

    def _save_agent_step_marker(self, step_name: str, step_state: StepState) -> None:
        """Save a marker file for agent steps to track them in the TUI."""
        raise NotImplementedError

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

        if not step.agent:
            raise WorkflowExecutionError(
                f"Agent step '{step.name}' has no agent prompt"
            )

        # Render prompt with Jinja2 context
        rendered_prompt = render_template(step.agent, self.context)

        # Get output schema before expansion
        output_spec = get_primary_output_schema(rendered_prompt)

        # Expand xprompt references
        expanded_prompt = process_xprompt_references(rendered_prompt)

        # Add format instructions if output schema exists
        if output_spec is not None:
            format_instructions = generate_format_instructions(output_spec)
            if format_instructions:
                expanded_prompt += format_instructions

        # Save initial marker to show step is running in TUI
        step_state.status = StepStatus.IN_PROGRESS
        self._save_agent_step_marker(step.name, step_state)

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
            self._save_agent_step_marker(step.name, step_state)

            result = self.hitl_handler.prompt(
                step.name, "agent", output, has_output=step.output is not None
            )

            if result.action == "reject":
                return False
            elif result.action == "accept":
                pass  # Continue with output as-is
            elif result.action == "edit":
                if result.edited_output is not None:
                    output = result.edited_output
                # Continue with edited output
            # Future: handle feedback for regeneration

        # Mark step completed after HITL (agent work is done)
        step_state.status = StepStatus.COMPLETED

        # Store output in context under step name
        step_state.output = output
        self.context[step.name] = output
        self.state.context = dict(self.context)

        # Save agent step marker for TUI visibility
        self._save_agent_step_marker(step.name, step_state)

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
            self._save_agent_step_marker(step.name, step_state)

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
        self._save_agent_step_marker(step.name, step_state)

        # Store output in context under step name
        step_state.output = output
        self.context[step.name] = output
        self.state.context = dict(self.context)

        return True

    def _execute_python_step(
        self,
        step: WorkflowStep,
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
            self._save_agent_step_marker(step.name, step_state)

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
        self._save_agent_step_marker(step.name, step_state)

        # Store output in context under step name
        step_state.output = output
        self.context[step.name] = output
        self.state.context = dict(self.context)

        return True
