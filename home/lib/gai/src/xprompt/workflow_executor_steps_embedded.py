"""Embedded workflow step execution mixin."""

import re
from typing import TYPE_CHECKING, Any

from xprompt.workflow_executor_types import HITLHandler
from xprompt.workflow_executor_utils import render_template
from xprompt.workflow_models import (
    StepState,
    StepStatus,
    Workflow,
    WorkflowExecutionError,
    WorkflowState,
    WorkflowStep,
)

if TYPE_CHECKING:
    from xprompt.workflow_output import ParentStepContext, WorkflowOutputHandler


# Pattern to match workflow references in prompts (same as processor.py)
_WORKFLOW_REF_PATTERN = (
    r"(?:^|(?<=\s)|(?<=[(\[{\"']))"
    r"#([a-zA-Z_][a-zA-Z0-9_]*(?:/[a-zA-Z_][a-zA-Z0-9_]*)*)"
    r"(?:(\()|:(`[^`]*`|[a-zA-Z0-9_.-]+)|(\+))?"  # Supports backtick-delimited colon args
)


class EmbeddedWorkflowMixin:
    """Mixin class providing embedded workflow execution.

    This mixin requires the following attributes on self:
        - workflow: Workflow
        - context: dict[str, Any]
        - artifacts_dir: str
        - hitl_handler: HITLHandler | None
        - output_handler: WorkflowOutputHandler | None
        - state: WorkflowState

    This mixin requires the following methods on self:
        - _get_step_type(step) -> str
        - _evaluate_condition(condition) -> bool
        - _save_prompt_step_marker(step_name, step_state, ...) -> None
        - _execute_prompt_step(step, step_state) -> bool
        - _execute_python_step(step, step_state) -> bool
        - _execute_bash_step(step, step_state) -> bool
    """

    # Type hints for attributes from WorkflowExecutor
    workflow: Workflow
    context: dict[str, Any]
    artifacts_dir: str
    hitl_handler: HITLHandler | None
    output_handler: "WorkflowOutputHandler | None"
    state: WorkflowState

    # Method type declarations for methods provided by other mixins/main class
    _get_step_type: Any  # (step: WorkflowStep) -> str
    _evaluate_condition: Any  # (condition: str) -> bool
    _save_prompt_step_marker: Any  # (step_name, step_state, ...) -> None
    _execute_prompt_step: Any  # (step, step_state) -> bool
    _execute_python_step: Any  # (step, step_state) -> bool
    _execute_bash_step: Any  # (step, step_state) -> bool

    def _execute_embedded_workflow_steps(
        self,
        steps: list[WorkflowStep],
        embedded_context: dict[str, Any],
        parent_step_name: str,
        parent_step_context: "ParentStepContext | None" = None,
        is_pre_prompt_step: bool = False,
    ) -> bool:
        """Execute steps from an embedded workflow.

        Runs steps inline as part of the containing workflow execution,
        accumulating outputs into the embedded workflow's context.

        Args:
            steps: List of workflow steps to execute.
            embedded_context: Context for the embedded workflow (args + outputs).
            parent_step_name: Name of the parent step for error messages.
            parent_step_context: Context for parent step numbering in output.
            is_pre_prompt_step: True if these are pre-prompt steps (before the main
                prompt), which should be hidden in the Agents tab.

        Returns:
            True if all steps succeeded, False if any failed.
        """
        del parent_step_name  # Unused but kept for API consistency
        total_steps = len(steps)

        for i, step in enumerate(steps):
            # Create a temporary step state for execution
            temp_state = StepState(name=step.name, status=StepStatus.PENDING)

            # Save original context and temporarily use embedded context
            original_context = self.context
            self.context = embedded_context

            try:
                # Determine step type for display
                step_type = self._get_step_type(step)

                # Evaluate if: condition
                if step.condition:
                    condition_result = self._evaluate_condition(step.condition)
                    if not condition_result:
                        temp_state.status = StepStatus.SKIPPED
                        # Notify output handler about skipped step
                        if self.output_handler:
                            self.output_handler.on_step_start(
                                step.name,
                                step_type,
                                i,
                                total_steps,
                                condition=step.condition,
                                condition_result=False,
                                parent_step_context=parent_step_context,
                            )
                            self.output_handler.on_step_skip(
                                step.name, reason="condition false"
                            )
                        continue

                # Notify step start
                if self.output_handler:
                    self.output_handler.on_step_start(
                        step.name,
                        step_type,
                        i,
                        total_steps,
                        parent_step_context=parent_step_context,
                    )

                temp_state.status = StepStatus.IN_PROGRESS

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

                # Save marker for embedded step with parent context
                step_source = (
                    step.bash
                    if step_type == "bash"
                    else (step.python if step_type == "python" else None)
                )
                self._save_prompt_step_marker(
                    step.name,
                    temp_state,
                    step_type,
                    step_source,
                    i,
                    parent_step_index=(
                        parent_step_context.step_index if parent_step_context else None
                    ),
                    parent_total_steps=(
                        parent_step_context.total_steps if parent_step_context else None
                    ),
                    is_pre_prompt_step=is_pre_prompt_step,
                    hidden=step.hidden,
                )

                # Notify step complete
                if self.output_handler:
                    self.output_handler.on_step_complete(step.name, temp_state.output)

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
                # Strip backticks if present (backtick-delimited syntax)
                if colon_arg.startswith("`") and colon_arg.endswith("`"):
                    colon_arg = colon_arg[1:-1]
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
                from xprompt.workflow_output import ParentStepContext

                parent_ctx = ParentStepContext(
                    step_index=self.state.current_step_index,
                    total_steps=len(self.workflow.steps),
                )
                success = self._execute_embedded_workflow_steps(
                    pre_steps,
                    embedded_context,
                    f"embedded:{name}",
                    parent_step_context=parent_ctx,
                    is_pre_prompt_step=True,
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

                # Handle section content (starting with ### or ---)
                # Prepend \n\n when the workflow ref is not at the start of a line
                if prompt_part_content.startswith(
                    "###"
                ) or prompt_part_content.startswith("---"):
                    is_at_line_start = (
                        match.start() == 0 or prompt[match.start() - 1] == "\n"
                    )
                    if not is_at_line_start:
                        prompt_part_content = "\n\n" + prompt_part_content

            # Replace the workflow reference with the prompt_part content
            prompt = prompt[: match.start()] + prompt_part_content + prompt[match_end:]

            # Store post-steps for execution after the main prompt
            if post_steps:
                embedded_workflows.append((pre_steps, post_steps, embedded_context))

        return prompt, embedded_workflows
