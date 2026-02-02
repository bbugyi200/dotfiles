"""Loop handling mixin for workflow execution."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from xprompt.workflow_executor_utils import create_jinja_env
from xprompt.workflow_models import (
    LoopConfig,
    ParallelConfig,
    StepState,
    WorkflowExecutionError,
    WorkflowStep,
)

if TYPE_CHECKING:
    from xprompt.workflow_output import WorkflowOutputHandler


class LoopMixin:
    """Mixin class providing loop handling functionality for WorkflowExecutor.

    This mixin requires the following attributes on self:
        - context: dict[str, Any]
        - state: WorkflowState
        - output_handler: WorkflowOutputHandler | None

    This mixin requires the following methods on self:
        - _evaluate_condition(condition: str) -> bool
        - _execute_agent_step(step, step_state) -> bool
        - _execute_python_step(step, step_state) -> bool
        - _execute_bash_step(step, step_state) -> bool
        - _execute_single_nested_step(nested_step, context_copy) -> tuple

    NOTE: This class must come AFTER _StepMixin in the MRO so that the step
    execution methods are properly resolved from _StepMixin.
    """

    # Type hints for attributes from WorkflowExecutor
    context: dict[str, Any]
    state: Any  # WorkflowState
    output_handler: "WorkflowOutputHandler | None"

    # Method type declarations for methods provided by other mixins/main class
    # These are not implemented here - they're provided via MRO
    _evaluate_condition: Any  # (condition: str) -> bool
    _execute_agent_step: Any  # (step, step_state) -> bool
    _execute_python_step: Any  # (step, step_state) -> bool
    _execute_bash_step: Any  # (step, step_state) -> bool
    _execute_single_nested_step: Any  # (nested_step, context_copy) -> tuple

    def _resolve_for_lists(
        self, for_loop: dict[str, str]
    ) -> tuple[list[str], list[list[Any]]]:
        """Resolve for: loop expressions to lists.

        Args:
            for_loop: Dict mapping variable names to Jinja2 expressions.

        Returns:
            Tuple of (variable_names, list_of_lists) where each inner list
            corresponds to the resolved values for that variable.

        Raises:
            WorkflowExecutionError: If lists have unequal lengths.
        """
        var_names = list(for_loop.keys())
        lists: list[list[Any]] = []

        for expr in for_loop.values():
            env = create_jinja_env()
            # Use compile_expression to get the actual value, not string rendering
            # This handles cases where the context has actual Python lists
            compiled = env.compile_expression(
                expr.strip().removeprefix("{{").removesuffix("}}").strip()
            )
            result = compiled(**self.context)

            # Parse the result as a list
            if isinstance(result, list):
                resolved_list = result
            elif isinstance(result, str):
                # Try to parse as JSON list
                try:
                    resolved_list = json.loads(result)
                    if not isinstance(resolved_list, list):
                        resolved_list = [resolved_list]
                except json.JSONDecodeError:
                    # Treat as single-item list
                    resolved_list = [result]
            else:
                resolved_list = [result]

            lists.append(resolved_list)

        # Validate all lists have equal length
        if lists:
            first_len = len(lists[0])
            for idx, lst in enumerate(lists[1:], 1):
                if len(lst) != first_len:
                    raise WorkflowExecutionError(
                        f"for: loop lists have unequal lengths: "
                        f"'{var_names[0]}' has {first_len} items, "
                        f"'{var_names[idx]}' has {len(lst)} items"
                    )

        return var_names, lists

    def _collect_results(
        self, results: list[dict[str, Any]], join_mode: str | None
    ) -> Any:
        """Combine iteration outputs based on join: mode.

        Args:
            results: List of output dicts from each iteration.
            join_mode: One of "array", "text", "object", "lastOf", or None.

        Returns:
            Combined result based on join mode.
        """
        if not results:
            return [] if join_mode != "object" else {}

        mode = join_mode or "array"

        if mode == "array":
            return results
        elif mode == "lastOf":
            return results[-1]
        elif mode == "text":
            # Concatenate string representations
            texts = []
            for r in results:
                if "_raw" in r:
                    texts.append(str(r["_raw"]))
                elif "_output" in r:
                    texts.append(str(r["_output"]))
                else:
                    texts.append(json.dumps(r))
            return "\n".join(texts)
        elif mode == "object":
            # Merge all dicts into one
            merged: dict[str, Any] = {}
            for r in results:
                merged.update(r)
            return merged
        else:
            return results

    def _execute_for_step(
        self,
        step: WorkflowStep,
        step_state: StepState,
    ) -> bool:
        """Execute a step with for: loop iteration.

        Args:
            step: The workflow step definition.
            step_state: The runtime state for this step.

        Returns:
            True if all iterations succeeded, False otherwise.
        """
        if not step.for_loop:
            return False

        var_names, lists = self._resolve_for_lists(step.for_loop)
        if not lists or not lists[0]:
            # Empty list - store empty result and continue
            step_state.output = self._collect_results([], step.join)
            self.context[step.name] = step_state.output
            self.state.context = dict(self.context)
            return True

        results: list[dict[str, Any]] = []
        num_iterations = len(lists[0])

        for iteration_idx in range(num_iterations):
            # Build iteration context with loop variables
            iteration_context = dict(self.context)
            loop_vars: dict[str, Any] = {}
            for var_idx, var_name in enumerate(var_names):
                iteration_context[var_name] = lists[var_idx][iteration_idx]
                loop_vars[var_name] = lists[var_idx][iteration_idx]

            # Notify iteration start
            if self.output_handler:
                self.output_handler.on_step_iteration(
                    step.name,
                    iteration_idx + 1,
                    num_iterations,
                    loop_vars,
                )

            # Temporarily update context for this iteration
            original_context = self.context
            self.context = iteration_context

            try:
                # Execute the step with iteration context
                if step.is_agent_step():
                    success = self._execute_agent_step(step, step_state)
                elif step.is_python_step():
                    success = self._execute_python_step(step, step_state)
                else:
                    success = self._execute_bash_step(step, step_state)

                if not success:
                    self.context = original_context
                    return False

                # Collect this iteration's output
                if step_state.output:
                    results.append(step_state.output)

            finally:
                # Restore original context
                self.context = original_context

        # Combine results and store in context
        combined = self._collect_results(results, step.join)
        step_state.output = combined
        self.context[step.name] = combined
        self.state.context = dict(self.context)

        return True

    def _execute_repeat_step(
        self,
        step: WorkflowStep,
        step_state: StepState,
    ) -> bool:
        """Execute a step with repeat:/until: loop.

        Executes step, then checks condition after each iteration.
        Raises error if max iterations reached without condition being satisfied.

        Args:
            step: The workflow step definition.
            step_state: The runtime state for this step.

        Returns:
            True if loop completed successfully, False otherwise.
        """
        if not step.repeat_config:
            return False

        config: LoopConfig = step.repeat_config

        for iteration_idx in range(config.max_iterations):
            # Execute the step
            if step.is_agent_step():
                success = self._execute_agent_step(step, step_state)
            elif step.is_python_step():
                success = self._execute_python_step(step, step_state)
            else:
                success = self._execute_bash_step(step, step_state)

            if not success:
                return False

            # Check until: condition after execution
            condition_result = self._evaluate_condition(config.condition)

            # Notify iteration complete
            if self.output_handler:
                self.output_handler.on_repeat_iteration(
                    step.name,
                    iteration_idx + 1,
                    config.max_iterations,
                    condition_result,
                )

            if condition_result:
                return True

        # Max iterations reached without condition becoming true
        raise WorkflowExecutionError(
            f"Step '{step.name}' repeat loop exceeded max iterations "
            f"({config.max_iterations}) without satisfying until: condition"
        )

    def _execute_while_step(
        self,
        step: WorkflowStep,
        step_state: StepState,
    ) -> bool:
        """Execute a step with while: loop.

        Executes step once to establish context, then checks condition
        before each subsequent iteration.
        Raises error if max iterations reached.

        Args:
            step: The workflow step definition.
            step_state: The runtime state for this step.

        Returns:
            True if loop completed successfully, False otherwise.
        """
        if not step.while_config:
            return False

        config: LoopConfig = step.while_config

        for iteration_idx in range(config.max_iterations):
            # Execute the step first
            if step.is_agent_step():
                success = self._execute_agent_step(step, step_state)
            elif step.is_python_step():
                success = self._execute_python_step(step, step_state)
            else:
                success = self._execute_bash_step(step, step_state)

            if not success:
                return False

            # Check while: condition after execution (for next iteration)
            condition_result = self._evaluate_condition(config.condition)

            # Notify iteration complete
            if self.output_handler:
                self.output_handler.on_repeat_iteration(
                    step.name,
                    iteration_idx + 1,
                    config.max_iterations,
                    condition_result,
                )

            if not condition_result:
                # Condition is false, stop looping
                return True

        # Max iterations reached with condition still true
        raise WorkflowExecutionError(
            f"Step '{step.name}' while loop exceeded max iterations "
            f"({config.max_iterations}) with condition still true"
        )

    def _execute_for_parallel_step(
        self,
        step: WorkflowStep,
        step_state: StepState,
    ) -> bool:
        """Execute a step with for: + parallel: combination.

        The outer for: loop iterates sequentially, and for each iteration,
        all parallel: steps run concurrently.

        Args:
            step: The workflow step definition.
            step_state: The runtime state for this step.

        Returns:
            True if all iterations and parallel steps succeeded, False otherwise.
        """
        if not step.for_loop or not step.parallel_config:
            return False

        var_names, lists = self._resolve_for_lists(step.for_loop)
        if not lists or not lists[0]:
            # Empty list - store empty result and continue
            step_state.output = self._collect_results([], step.join)
            self.context[step.name] = step_state.output
            self.state.context = dict(self.context)
            return True

        config: ParallelConfig = step.parallel_config
        nested_steps = config.steps
        num_iterations = len(lists[0])

        all_results: list[dict[str, Any]] = []

        for iteration_idx in range(num_iterations):
            # Build iteration context with loop variables
            iteration_context = dict(self.context)
            loop_vars: dict[str, Any] = {}
            for var_idx, var_name in enumerate(var_names):
                iteration_context[var_name] = lists[var_idx][iteration_idx]
                loop_vars[var_name] = lists[var_idx][iteration_idx]

            # Notify iteration start
            if self.output_handler:
                self.output_handler.on_step_iteration(
                    step.name,
                    iteration_idx + 1,
                    num_iterations,
                    loop_vars,
                )

            # Execute all nested steps in parallel for this iteration
            iteration_results: dict[str, dict[str, Any]] = {}
            errors: list[str] = []

            with ThreadPoolExecutor(max_workers=len(nested_steps)) as executor:
                # Create deep copies of iteration context for each parallel step
                futures = {
                    executor.submit(
                        self._execute_single_nested_step,
                        nested_step,
                        copy.deepcopy(iteration_context),
                    ): nested_step.name
                    for nested_step in nested_steps
                }

                for future in as_completed(futures):
                    step_name_result, output, error = future.result()

                    if error:
                        errors.append(error)
                        if config.fail_fast:
                            for f in futures:
                                f.cancel()
                            break
                    elif output is not None:
                        iteration_results[step_name_result] = output

            # Check for failures
            if errors:
                step_state.error = "; ".join(errors)
                raise WorkflowExecutionError(
                    f"Parallel step '{step.name}' failed in iteration "
                    f"{iteration_idx + 1}: {step_state.error}"
                )

            # Merge parallel results for this iteration
            # Each iteration produces a dict with results from each parallel step
            all_results.append(iteration_results)

        # Combine all iteration results based on join mode
        join_mode = step.join or "array"
        combined = self._collect_results(all_results, join_mode)

        step_state.output = combined
        self.context[step.name] = combined
        self.state.context = dict(self.context)

        return True
