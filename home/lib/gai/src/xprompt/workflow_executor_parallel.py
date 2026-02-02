"""Parallel step execution mixin for workflow execution."""

import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from xprompt.workflow_models import (
    ParallelConfig,
    StepState,
    StepStatus,
    WorkflowExecutionError,
    WorkflowStep,
)

if TYPE_CHECKING:
    from xprompt.workflow_output import WorkflowOutputHandler


class ParallelMixin:
    """Mixin class providing parallel step execution for WorkflowExecutor.

    This mixin requires the following attributes on self:
        - context: dict[str, Any]
        - state: WorkflowState
        - output_handler: WorkflowOutputHandler | None

    This mixin requires the following methods on self:
        - _execute_agent_step(step, step_state) -> bool
        - _execute_python_step(step, step_state) -> bool
        - _execute_bash_step(step, step_state) -> bool
        - _collect_results(results, join_mode) -> Any
    """

    # Type hints for attributes from WorkflowExecutor
    context: dict[str, Any]
    state: Any  # WorkflowState
    output_handler: "WorkflowOutputHandler | None"

    # Method type declarations for methods provided by other mixins/main class
    _execute_agent_step: Any
    _execute_python_step: Any
    _execute_bash_step: Any
    _collect_results: Any

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
            if nested_step.is_agent_step():
                success = self._execute_agent_step(nested_step, temp_step_state)
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

        # Notify parallel execution start
        if self.output_handler:
            step_names = [s.name for s in nested_steps]
            self.output_handler.on_parallel_start(step.name, step_names)

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

        return True
