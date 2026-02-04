"""Step execution mixin for workflow execution."""

import os
import re
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

# Pattern to match workflow references in prompts (same as processor.py)
_WORKFLOW_REF_PATTERN = (
    r"(?:^|(?<=\s)|(?<=[(\[{\"']))"
    r"#([a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*)"
    r"(?:(\()|:([a-zA-Z0-9_.-]+)|(\+))?"
)


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
        - _save_prompt_step_marker(step_name, step_state) -> None
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

    def _save_prompt_step_marker(
        self,
        step_name: str,
        step_state: StepState,
        step_type: str = "prompt",
        step_source: str | None = None,
        step_index: int | None = None,
    ) -> None:
        """Save a marker file for prompt steps to track them in the TUI."""
        raise NotImplementedError

    def _execute_embedded_workflow_steps(
        self,
        steps: list[WorkflowStep],
        embedded_context: dict[str, Any],
        parent_step_name: str,
    ) -> bool:
        """Execute steps from an embedded workflow.

        Runs steps inline as part of the containing workflow execution,
        accumulating outputs into the embedded workflow's context.

        Args:
            steps: List of workflow steps to execute.
            embedded_context: Context for the embedded workflow (args + outputs).
            parent_step_name: Name of the parent step for error messages.

        Returns:
            True if all steps succeeded, False if any failed.
        """
        for step in steps:
            # Create a temporary step state for execution
            temp_state = StepState(name=step.name, status=StepStatus.IN_PROGRESS)

            # Save original context and temporarily use embedded context
            original_context = self.context
            self.context = embedded_context

            try:
                if step.is_prompt_step():
                    success = self._execute_prompt_step(step, temp_state)
                elif step.is_python_step():
                    success = self._execute_python_step(step, temp_state)
                elif step.is_bash_step():
                    success = self._execute_bash_step(step, temp_state)
                else:
                    raise WorkflowExecutionError(
                        f"Unsupported step type in embedded workflow: {step.name}"
                    )

                if not success:
                    return False
            finally:
                # Restore original context
                self.context = original_context

        return True

    def _expand_embedded_workflows_in_prompt(
        self,
        prompt: str,
    ) -> tuple[
        str, list[tuple[list[WorkflowStep], list[WorkflowStep], dict[str, Any]]]
    ]:
        """Detect and expand embedded workflows in a prompt.

        Finds workflow references in the prompt, executes their pre-steps,
        and replaces the references with prompt_part content.

        Args:
            prompt: The prompt text that may contain workflow references.

        Returns:
            Tuple of (expanded_prompt, list of (pre_steps, post_steps, context) tuples).
            The post_steps should be executed after the main prompt completes.
        """
        from xprompt._parsing import find_matching_paren_for_args, parse_args
        from xprompt.loader import get_all_workflows

        workflows = get_all_workflows()
        embedded_workflows: list[
            tuple[list[WorkflowStep], list[WorkflowStep], dict[str, Any]]
        ] = []

        # Find all potential workflow references
        matches = list(re.finditer(_WORKFLOW_REF_PATTERN, prompt, re.MULTILINE))

        # Process from last to first to preserve positions
        for match in reversed(matches):
            name = match.group(1)

            # Skip if not a workflow
            if name not in workflows:
                continue

            workflow = workflows[name]

            # Skip workflows without prompt_part (they're not embeddable)
            # They will be handled by the regular workflow execution
            if not workflow.has_prompt_part():
                continue

            # Extract arguments
            has_open_paren = match.group(2) is not None
            colon_arg = match.group(3)
            plus_suffix = match.group(4)
            match_end = match.end()

            positional_args: list[str] = []
            named_args: dict[str, str] = {}

            if has_open_paren:
                paren_start = match.end() - 1
                paren_end = find_matching_paren_for_args(prompt, paren_start)
                if paren_end is not None:
                    paren_content = prompt[paren_start + 1 : paren_end]
                    positional_args, named_args = parse_args(paren_content)
                    match_end = paren_end + 1
            elif colon_arg is not None:
                positional_args = [colon_arg]
            elif plus_suffix is not None:
                positional_args = ["true"]

            # Build args dict
            args: dict[str, Any] = dict(named_args)
            for i, value in enumerate(positional_args):
                if i < len(workflow.inputs):
                    input_arg = workflow.inputs[i]
                    if input_arg.name not in args:
                        args[input_arg.name] = value

            # Apply defaults
            for input_arg in workflow.inputs:
                if input_arg.name not in args and input_arg.default is not None:
                    args[input_arg.name] = str(input_arg.default)

            # Get pre and post steps
            pre_steps = workflow.get_pre_prompt_steps()
            post_steps = workflow.get_post_prompt_steps()

            # Create isolated context for the embedded workflow
            embedded_context: dict[str, Any] = dict(args)

            # Execute pre-steps to populate context
            if pre_steps:
                success = self._execute_embedded_workflow_steps(
                    pre_steps, embedded_context, f"embedded:{name}"
                )
                if not success:
                    raise WorkflowExecutionError(
                        f"Pre-steps for embedded workflow '{name}' failed"
                    )

            # Render prompt_part with the embedded context (args + pre-step outputs)
            prompt_part_content = workflow.get_prompt_part_content()
            if prompt_part_content:
                prompt_part_content = render_template(
                    prompt_part_content, embedded_context
                )

            # Replace the workflow reference with the prompt_part content
            prompt = prompt[: match.start()] + prompt_part_content + prompt[match_end:]

            # Store post-steps for execution after the main prompt
            if post_steps:
                embedded_workflows.append((pre_steps, post_steps, embedded_context))

        return prompt, embedded_workflows

    def _execute_prompt_step(
        self,
        step: WorkflowStep,
        step_state: StepState,
    ) -> bool:
        """Execute a prompt step.

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
            raise WorkflowExecutionError(f"Prompt step '{step.name}' has no prompt")

        # Render prompt with Jinja2 context
        rendered_prompt = render_template(step.prompt, self.context)

        # Expand embedded workflows first (before xprompt processing)
        # This executes pre-steps and replaces workflow refs with prompt_part content
        expanded_prompt, embedded_workflows = self._expand_embedded_workflows_in_prompt(
            rendered_prompt
        )

        # Get output schema before expansion
        output_spec = get_primary_output_schema(expanded_prompt)

        # Expand xprompt references
        expanded_prompt = process_xprompt_references(expanded_prompt)

        # Add format instructions if output schema exists
        if output_spec is not None:
            format_instructions = generate_format_instructions(output_spec)
            if format_instructions:
                expanded_prompt += format_instructions

        # Save initial marker to show step is running in TUI
        step_state.status = StepStatus.IN_PROGRESS
        self._save_prompt_step_marker(step.name, step_state)

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
            self._save_prompt_step_marker(step.name, step_state)

            result = self.hitl_handler.prompt(
                step.name, "prompt", output, has_output=step.output is not None
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

        # Mark step completed after HITL (prompt work is done)
        step_state.status = StepStatus.COMPLETED

        # Store output in context under step name
        step_state.output = output
        self.context[step.name] = output
        self.state.context = dict(self.context)

        # Save prompt step marker for TUI visibility
        self._save_prompt_step_marker(step.name, step_state)

        # Execute post-steps from embedded workflows
        for _, post_steps, embedded_context in embedded_workflows:
            if post_steps:
                success = self._execute_embedded_workflow_steps(
                    post_steps, embedded_context, f"embedded:post:{step.name}"
                )
                if not success:
                    raise WorkflowExecutionError(
                        f"Post-steps for embedded workflow in step '{step.name}' failed"
                    )

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
            self._save_prompt_step_marker(
                step.name, step_state, step_type="bash", step_source=rendered_command
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
            step.name, step_state, step_type="bash", step_source=rendered_command
        )

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
            self._save_prompt_step_marker(
                step.name, step_state, step_type="python", step_source=rendered_code
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
            step.name, step_state, step_type="python", step_source=rendered_code
        )

        # Store output in context under step name
        step_state.output = output
        self.context[step.name] = output
        self.state.context = dict(self.context)

        return True
