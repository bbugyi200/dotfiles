"""Workflow execution engine for multi-step agent workflows."""

import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any

from xprompt.workflow_executor_types import HITLHandler, HITLResult
from xprompt.workflow_executor_utils import (
    create_jinja_env,
    parse_bash_output,
    render_template,
)
from xprompt.workflow_models import (
    LoopConfig,
    StepState,
    StepStatus,
    Workflow,
    WorkflowExecutionError,
    WorkflowState,
    WorkflowStep,
)

# Re-export for backward compatibility
__all__ = ["WorkflowExecutor", "HITLHandler", "HITLResult"]


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

            # Evaluate if: condition
            if step.condition and not self._evaluate_condition(step.condition):
                step_state.status = StepStatus.SKIPPED
                self._save_state()
                continue

            step_state.status = StepStatus.IN_PROGRESS
            self._save_state()

            try:
                # Handle control flow constructs
                if step.for_loop:
                    success = self._execute_for_step(step, step_state)
                elif step.repeat_config:
                    success = self._execute_repeat_step(step, step_state)
                elif step.while_config:
                    success = self._execute_while_step(step, step_state)
                elif step.is_agent_step():
                    success = self._execute_agent_step(step, step_state)
                elif step.is_python_step():
                    success = self._execute_python_step(step, step_state)
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

    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate a Jinja2 condition expression.

        Args:
            condition: The condition expression to evaluate.

        Returns:
            True if condition evaluates to truthy, False otherwise.
        """
        env = create_jinja_env()
        try:
            template = env.from_string(condition)
            result = template.render(self.context)
            # Handle string "True"/"False" and actual boolean results
            if isinstance(result, bool):
                return result
            result_str = result.strip().lower()
            return result_str not in ("", "false", "none", "0", "[]", "{}")
        except Exception:
            return False

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
            for var_idx, var_name in enumerate(var_names):
                iteration_context[var_name] = lists[var_idx][iteration_idx]

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

        for _ in range(config.max_iterations):
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
            if self._evaluate_condition(config.condition):
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

        for _ in range(config.max_iterations):
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
            if not self._evaluate_condition(config.condition):
                # Condition is false, stop looping
                return True

        # Max iterations reached with condition still true
        raise WorkflowExecutionError(
            f"Step '{step.name}' while loop exceeded max iterations "
            f"({config.max_iterations}) with condition still true"
        )

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
        rendered_prompt = render_template(step.prompt, self.context)

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
            from .output_validation import validate_against_schema

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

            result_hitl = self.hitl_handler.prompt(step.name, "python", output)

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
