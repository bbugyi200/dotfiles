"""Parallel step execution mixin for workflow execution."""

import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from xprompt.workflow_executor_steps_embedded import EmbeddedWorkflowInfo
from xprompt.workflow_models import (
    ParallelConfig,
    StepState,
    StepStatus,
    Workflow,
    WorkflowExecutionError,
    WorkflowStep,
)

if TYPE_CHECKING:
    from xprompt.workflow_output import WorkflowOutputHandler


class ParallelMixin:
    """Mixin class providing parallel step execution for WorkflowExecutor.

    This mixin requires the following attributes on self:
        - workflow: Workflow
        - context: dict[str, Any]
        - state: WorkflowState
        - output_handler: WorkflowOutputHandler | None

    This mixin requires the following methods on self:
        - _execute_prompt_step(step, step_state) -> bool
        - _execute_python_step(step, step_state) -> bool
        - _execute_bash_step(step, step_state) -> bool
        - _collect_results(results, join_mode) -> Any
        - _expand_embedded_workflows_in_prompt(prompt) -> tuple
        - _execute_embedded_workflow_steps(steps, context, name, ...) -> bool
    """

    # Type hints for attributes from WorkflowExecutor
    workflow: Workflow
    context: dict[str, Any]
    state: Any  # WorkflowState
    output_handler: "WorkflowOutputHandler | None"

    # Method type declarations for methods provided by other mixins/main class
    _execute_prompt_step: Any
    _execute_python_step: Any
    _execute_bash_step: Any
    _collect_results: Any
    _expand_embedded_workflows_in_prompt: Any
    _execute_embedded_workflow_steps: Any
    _propagate_embedded_exports: Any
    _save_prompt_step_marker: Any
    _get_step_type: Any

    def _execute_single_nested_step(
        self,
        nested_step: WorkflowStep,
        context_copy: dict[str, Any],
    ) -> tuple[str, dict[str, Any] | None, str | None]:
        """Execute a single nested step within a parallel block.

        Args:
            nested_step: The workflow step to execute.
            context_copy: A copy of the workflow context for this step.

        Returns:
            Tuple of (step_name, output, error_message).
            output is None if step failed, error_message is None on success.
        """
        # Create a temporary step state for execution
        temp_step_state = StepState(
            name=nested_step.name,
            status=StepStatus.IN_PROGRESS,
        )

        # Temporarily swap context
        original_context = self.context
        self.context = context_copy

        try:
            # Execute based on step type
            if nested_step.is_prompt_step():
                success = self._execute_prompt_step(nested_step, temp_step_state)
            elif nested_step.is_python_step():
                success = self._execute_python_step(nested_step, temp_step_state)
            else:
                success = self._execute_bash_step(nested_step, temp_step_state)

            if not success:
                return (nested_step.name, None, f"Step '{nested_step.name}' failed")

            return (nested_step.name, temp_step_state.output, None)

        except Exception as e:
            return (nested_step.name, None, str(e))
        finally:
            # Restore original context
            self.context = original_context

    def _pre_expand_parallel_embedded_workflows(
        self,
        nested_steps: list[WorkflowStep],
    ) -> tuple[list[WorkflowStep], list[EmbeddedWorkflowInfo]]:
        """Pre-expand embedded workflows in nested prompt steps.

        Hoists pre-steps (before parallel) and post-steps (after parallel) out
        of the parallel block. prompt_part content is expanded inline.

        Args:
            nested_steps: The nested steps from the parallel config.

        Returns:
            Tuple of (possibly-modified nested steps, collected
            EmbeddedWorkflowInfo list).
        """
        from xprompt import process_xprompt_references
        from xprompt.workflow_executor_utils import render_template

        modified_steps: list[WorkflowStep] = []
        all_embedded_workflows: list[EmbeddedWorkflowInfo] = []
        cumulative_pre_step_offset = 0

        for ns in nested_steps:
            if not (ns.is_prompt_step() and ns.prompt):
                modified_steps.append(ns)
                continue

            # Full prompt expansion pipeline (same as _execute_prompt_step)
            rendered = render_template(ns.prompt, self.context)
            expanded = process_xprompt_references(
                rendered, extra_xprompts=self.workflow.xprompts
            )
            expanded, embedded_wfs, pre_step_count = (
                self._expand_embedded_workflows_in_prompt(
                    expanded, pre_step_offset=cumulative_pre_step_offset
                )
            )
            cumulative_pre_step_offset += pre_step_count

            if embedded_wfs:
                all_embedded_workflows.extend(embedded_wfs)

            if expanded != ns.prompt:
                # Prompt was modified by expansion — use a deep copy with new prompt
                ns_copy = copy.deepcopy(ns)
                ns_copy.prompt = expanded
                modified_steps.append(ns_copy)
            else:
                modified_steps.append(ns)

        return modified_steps, all_embedded_workflows

    def _execute_parallel_step(
        self,
        step: WorkflowStep,
        step_state: StepState,
    ) -> bool:
        """Execute a step with parallel: configuration.

        Runs all nested steps concurrently using ThreadPoolExecutor.
        Results are collected and merged based on join: mode (default: object).

        Args:
            step: The workflow step definition.
            step_state: The runtime state for this step.

        Returns:
            True if all parallel steps succeeded, False otherwise.
        """
        if not step.parallel_config:
            return False

        config: ParallelConfig = step.parallel_config
        nested_steps = config.steps

        # Pre-expand embedded workflows (hoists pre/post steps out of parallel)
        nested_steps, collected_embedded_workflows = (
            self._pre_expand_parallel_embedded_workflows(nested_steps)
        )

        # Notify parallel execution start
        if self.output_handler:
            step_names = [s.name for s in nested_steps]
            self.output_handler.on_parallel_start(step.name, step_names)

        # Pre-create "running" markers for parallel children with parent step info
        parent_idx = self.state.current_step_index
        total = len(self.workflow.steps)
        for child_idx, nested_step in enumerate(nested_steps):
            child_state = StepState(
                name=nested_step.name, status=StepStatus.IN_PROGRESS
            )
            self._save_prompt_step_marker(
                nested_step.name,
                child_state,
                self._get_step_type(nested_step),
                step_index=child_idx,
                parent_step_index=parent_idx,
                parent_total_steps=total,
            )

        # Execute all nested steps in parallel
        results: dict[str, dict[str, Any]] = {}
        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=len(nested_steps)) as executor:
            # Create deep copies of context for each parallel step
            futures = {
                executor.submit(
                    self._execute_single_nested_step,
                    nested_step,
                    copy.deepcopy(self.context),
                ): nested_step.name
                for nested_step in nested_steps
            }

            for future in as_completed(futures):
                step_name, output, error = future.result()

                if error:
                    errors.append(error)
                    if config.fail_fast:
                        # Cancel remaining futures (best effort)
                        for f in futures:
                            f.cancel()
                        break
                elif output is not None:
                    results[step_name] = output

                # Notify individual step completion
                if self.output_handler:
                    self.output_handler.on_parallel_step_complete(
                        step.name, step_name, output, error
                    )

        # Check for failures
        if errors:
            step_state.error = "; ".join(errors)
            if self.output_handler:
                self.output_handler.on_parallel_complete(step.name, None, errors)
            raise WorkflowExecutionError(
                f"Parallel step '{step.name}' failed: {step_state.error}"
            )

        # Combine results based on join mode (default: object for parallel)
        join_mode = step.join or "object"

        if join_mode == "object":
            # Results already nested under step names
            combined = results
        else:
            # Convert to list of results for other join modes
            result_list = [results[s.name] for s in nested_steps if s.name in results]
            combined = self._collect_results(result_list, join_mode)

        step_state.output = combined
        self.context[step.name] = combined
        self.state.context = dict(self.context)

        # Notify parallel complete
        if self.output_handler:
            self.output_handler.on_parallel_complete(step.name, combined, None)

        # Execute post-steps from embedded workflows
        cumulative_post_offset = 0
        for info in collected_embedded_workflows:
            if info.post_steps:
                from xprompt.workflow_output import ParentStepContext

                parent_ctx = ParentStepContext(
                    step_index=self.state.current_step_index,
                    total_steps=len(self.workflow.steps),
                )
                success = self._execute_embedded_workflow_steps(
                    info.post_steps,
                    info.context,
                    f"embedded:post:{step.name}",
                    parent_step_context=parent_ctx,
                    step_index_offset=cumulative_post_offset,
                )
                if not success:
                    raise WorkflowExecutionError(
                        f"Post-steps for embedded workflow in parallel step "
                        f"'{step.name}' failed"
                    )
                cumulative_post_offset += len(info.post_steps)

        # Propagate exports from embedded workflows into parent context
        self._propagate_embedded_exports(collected_embedded_workflows)

        return True
