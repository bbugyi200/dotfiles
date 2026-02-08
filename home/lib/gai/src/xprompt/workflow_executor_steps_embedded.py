"""Embedded workflow step execution mixin."""

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from shared_utils import apply_section_marker_handling

from xprompt.models import OutputSpec
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

_logger = logging.getLogger(__name__)


@dataclass
class EmbeddedWorkflowInfo:
    """Information about an embedded workflow expanded from a prompt reference.

    Attributes:
        pre_steps: Steps executed before the prompt_part.
        post_steps: Steps executed after the main prompt completes.
        context: Isolated context for the embedded workflow (args + outputs).
        workflow_name: Name of the embedded workflow.
        nested_step_name: For parallel: which nested step this belongs to.
    """

    pre_steps: list[WorkflowStep]
    post_steps: list[WorkflowStep]
    context: dict[str, Any]
    workflow_name: str
    nested_step_name: str | None = None


def _get_type_to_keys(spec: OutputSpec) -> dict[str, list[str]]:
    """Build a mapping from property type → list of property names.

    Args:
        spec: The OutputSpec to extract type info from.

    Returns:
        Dict mapping type strings (e.g. "path") to lists of property names.
    """
    result: dict[str, list[str]] = {}
    for key, prop in spec.schema.get("properties", {}).items():
        prop_type = prop.get("type", "") if isinstance(prop, dict) else ""
        result.setdefault(prop_type, []).append(key)
    return result


def map_output_by_type(
    parent_spec: OutputSpec,
    embedded_spec: OutputSpec,
    embedded_output: dict[str, Any],
) -> dict[str, Any] | None:
    """Map embedded output values to parent output keys by matching property types.

    For each property type declared in the parent output spec, find the
    corresponding property in the embedded output spec with the same type
    and map its value to the parent key name.

    Args:
        parent_spec: The parent step's output specification.
        embedded_spec: The embedded post-step's output specification.
        embedded_output: The actual output dict from the embedded step.

    Returns:
        A new dict with parent key names mapped to embedded values, or None
        if the types don't match (e.g. parent has a type not present in embedded).
    """
    parent_types = _get_type_to_keys(parent_spec)
    embedded_types = _get_type_to_keys(embedded_spec)

    if not parent_types:
        return None

    mapped: dict[str, Any] = {}
    for prop_type, parent_keys in parent_types.items():
        embedded_keys = embedded_types.get(prop_type, [])
        if len(parent_keys) > len(embedded_keys):
            _logger.debug(
                "Type mismatch: parent has %d keys of type %r but embedded has %d",
                len(parent_keys),
                prop_type,
                len(embedded_keys),
            )
            return None
        # Map positionally: first parent key of type T gets first embedded key of type T
        for parent_key, embedded_key in zip(parent_keys, embedded_keys, strict=False):
            if embedded_key not in embedded_output:
                return None
            mapped[parent_key] = embedded_output[embedded_key]

    return mapped


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
        step_index_offset: int = 0,
        embedded_workflow_name: str | None = None,
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
                                step_index_offset + i,
                                total_steps,
                                condition=step.condition,
                                condition_result=False,
                                parent_step_context=parent_step_context,
                            )
                            self.output_handler.on_step_skip(
                                step.name, reason="condition false"
                            )
                        embedded_context[step.name] = {}
                        continue

                # Notify step start
                if self.output_handler:
                    self.output_handler.on_step_start(
                        step.name,
                        step_type,
                        step_index_offset + i,
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
                    step_index_offset + i,
                    parent_step_index=(
                        parent_step_context.step_index if parent_step_context else None
                    ),
                    parent_total_steps=(
                        parent_step_context.total_steps if parent_step_context else None
                    ),
                    is_pre_prompt_step=is_pre_prompt_step,
                    hidden=step.hidden,
                    embedded_workflow_name=embedded_workflow_name,
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
        pre_step_offset: int = 0,
    ) -> tuple[str, list[EmbeddedWorkflowInfo], int]:
        """Detect and expand embedded workflows in a prompt.

        Finds workflow references in the prompt, executes their pre-steps,
        and replaces the references with prompt_part content.

        Args:
            prompt: The prompt text that may contain workflow references.
            pre_step_offset: Starting offset for sub-step numbering of pre-steps.

        Returns:
            Tuple of (expanded_prompt, list of EmbeddedWorkflowInfo,
            total_pre_steps_executed). The post_steps should be executed
            after the main prompt completes.
        """
        from xprompt._parsing import find_matching_paren_for_args, parse_args
        from xprompt.loader import get_all_workflows

        workflows = get_all_workflows()
        embedded_workflows: list[EmbeddedWorkflowInfo] = []
        expanded_metadata: list[dict[str, Any]] = []
        running_offset = pre_step_offset

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

            # Capture explicit args before applying defaults
            explicit_args = dict(args)
            expanded_metadata.append({"name": name, "args": explicit_args})

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
                    step_index_offset=running_offset,
                    embedded_workflow_name=name,
                )
                if not success:
                    raise WorkflowExecutionError(
                        f"Pre-steps for embedded workflow '{name}' failed"
                    )
                running_offset += len(pre_steps)

            # Render prompt_part with the embedded context (args + pre-step outputs)
            prompt_part_content = workflow.get_prompt_part_content()
            if prompt_part_content:
                prompt_part_content = render_template(
                    prompt_part_content, embedded_context
                )

                # Handle section markers (### or ---) with proper line positioning
                is_at_line_start = (
                    match.start() == 0 or prompt[match.start() - 1] == "\n"
                )
                prompt_part_content = apply_section_marker_handling(
                    prompt_part_content, is_at_line_start
                )

            # Replace the workflow reference with the prompt_part content
            prompt = prompt[: match.start()] + prompt_part_content + prompt[match_end:]

            # Store post-steps for execution after the main prompt
            if post_steps:
                embedded_workflows.append(
                    EmbeddedWorkflowInfo(
                        pre_steps=pre_steps,
                        post_steps=post_steps,
                        context=embedded_context,
                        workflow_name=name,
                    )
                )

        # Save embedded workflow metadata (reversed to restore original order)
        if expanded_metadata and os.path.isdir(self.artifacts_dir):
            ordered_metadata = list(reversed(expanded_metadata))
            # Write shared file (backward compat for gai run agents)
            metadata_path = os.path.join(self.artifacts_dir, "embedded_workflows.json")
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(ordered_metadata, f, indent=2)
            # Write step-specific file for multi-step workflows
            current_step_name = self.workflow.steps[self.state.current_step_index].name
            step_metadata_path = os.path.join(
                self.artifacts_dir,
                f"embedded_workflows_{current_step_name}.json",
            )
            with open(step_metadata_path, "w", encoding="utf-8") as f:
                json.dump(ordered_metadata, f, indent=2)

        return prompt, embedded_workflows, running_offset - pre_step_offset

    def _propagate_last_embedded_output(
        self,
        embedded_workflows: list[EmbeddedWorkflowInfo],
        step: WorkflowStep,
        step_state: StepState,
    ) -> None:
        """Propagate the last embedded workflow's output to the parent step.

        If the parent prompt step declares ``output`` AND the last post-step of
        the last embedded workflow also declares ``output``, and each parent
        output property type matches a corresponding embedded output property
        type, then build a remapped output dict and overwrite
        ``step_state.output`` and ``self.context[step.name]``.

        Matching is by property **type** (not name), so a parent declaring
        ``{my_path: path}`` will match an embedded step declaring
        ``{file_path: path}``.

        Args:
            embedded_workflows: List of embedded workflow info from expansion.
            step: The parent prompt step.
            step_state: The parent step's runtime state.
        """
        if not step.output:
            return
        if not embedded_workflows:
            return

        last_info = embedded_workflows[-1]
        if not last_info.post_steps:
            return

        last_post_step = last_info.post_steps[-1]
        if not last_post_step.output:
            return

        # Get the actual output of the last post-step from the embedded context
        embedded_output = last_info.context.get(last_post_step.name)
        if not isinstance(embedded_output, dict):
            return

        mapped = map_output_by_type(step.output, last_post_step.output, embedded_output)
        if mapped is None:
            return

        # Propagate: overwrite step output with remapped output
        step_state.output = mapped
        self.context[step.name] = mapped
