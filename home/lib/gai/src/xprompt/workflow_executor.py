"""Workflow execution engine for multi-step agent workflows."""

import json
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from xprompt.workflow_executor_loops import LoopMixin
from xprompt.workflow_executor_parallel import ParallelMixin
from xprompt.workflow_executor_steps import StepMixin
from xprompt.workflow_executor_types import HITLHandler, HITLResult
from xprompt.workflow_executor_utils import create_jinja_env
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

# Import LoopInfo unconditionally since it's used at runtime
from xprompt.workflow_output import LoopInfo

# Re-export for backward compatibility
__all__ = ["WorkflowExecutor", "HITLHandler", "HITLResult"]


class WorkflowExecutor(StepMixin, LoopMixin, ParallelMixin):
    """Executes workflow steps sequentially with context accumulation."""

    def __init__(
        self,
        workflow: Workflow,
        args: dict[str, Any],
        artifacts_dir: str,
        hitl_handler: HITLHandler | None = None,
        output_handler: "WorkflowOutputHandler | None" = None,
    ) -> None:
        """Initialize the workflow executor.

        Args:
            workflow: The workflow to execute.
            args: Input arguments matching workflow.inputs.
            artifacts_dir: Directory for workflow artifacts.
            hitl_handler: Optional handler for HITL prompts.
            output_handler: Optional handler for verbose output display.
        """
        self.workflow = workflow
        self.context: dict[str, Any] = dict(args)
        self.artifacts_dir = artifacts_dir
        self.hitl_handler = hitl_handler
        self.output_handler = output_handler
        self._current_embedded_workflow_name: str | None = None

        # Detect step inputs - args that match step names with output schemas
        # These are used to skip steps and use pre-provided outputs
        self._step_inputs: dict[str, Any] = {}
        for step in workflow.steps:
            if step.name in args and step.output is not None:
                self._step_inputs[step.name] = args[step.name]

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

        # Extract declared workflow inputs (exclude auto-generated step inputs)
        inputs = {}
        for input_arg in self.workflow.inputs:
            if input_arg.is_step_input:
                continue
            if input_arg.name in self.state.context:
                inputs[input_arg.name] = self.state.context[input_arg.name]

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
                    "hidden": self.workflow.steps[i].hidden,
                    "output_types": self._get_output_types(i),
                }
                for i, s in enumerate(self.state.steps)
            ],
            "context": self.state.context,
            "inputs": inputs,
            "artifacts_dir": self.state.artifacts_dir,
            "start_time": self.state.start_time,
            "pid": os.getpid(),
            "appears_as_agent": self.workflow.appears_as_agent(),
            "is_anonymous": self.workflow.is_anonymous(),
        }
        os.makedirs(self.artifacts_dir, exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state_dict, f, indent=2)

    def _get_output_types(self, step_index: int) -> dict[str, str] | None:
        """Get the output type mapping for a workflow step.

        Extracts field name to type mappings from the step's OutputSpec schema.

        Args:
            step_index: Index of the step in the workflow.

        Returns:
            Dict mapping field names to type strings, or None if no output spec.
        """
        step = self.workflow.steps[step_index]
        if step.output is None:
            return None
        properties = step.output.schema.get("properties")
        if not properties or not isinstance(properties, dict):
            return None
        return {
            name: prop.get("type", "text")
            for name, prop in properties.items()
            if isinstance(prop, dict)
        }

    def execute(self) -> bool:
        """Execute all workflow steps sequentially.

        Returns:
            True if workflow completed successfully, False otherwise.
        """
        self._save_state()
        total_steps = len(self.workflow.steps)

        # Notify workflow start
        if self.output_handler:
            self.output_handler.on_workflow_start(
                self.workflow.name,
                dict(self.context),
                total_steps,
            )

        for i, step in enumerate(self.workflow.steps):
            self.state.current_step_index = i
            step_state = self.state.steps[i]
            step_start_time = time.time()

            # Determine step type for display
            step_type = self._get_step_type(step)

            # Check if step should be skipped due to provided step input
            if step.name in self._step_inputs:
                step_state.status = StepStatus.SKIPPED
                step_state.output = self._step_inputs[step.name]
                self.context[step.name] = self._step_inputs[step.name]
                self._save_state()
                if self.output_handler:
                    self.output_handler.on_step_start(
                        step.name,
                        step_type,
                        i,
                        total_steps,
                    )
                    self.output_handler.on_step_skip(
                        step.name, reason="step input provided"
                    )
                continue

            # Evaluate if: condition
            condition_result: bool | None = None
            if step.condition:
                condition_result = self._evaluate_condition(step.condition)
                if not condition_result:
                    step_state.status = StepStatus.SKIPPED
                    self._save_state()
                    # Notify step skipped
                    if self.output_handler:
                        self.output_handler.on_step_start(
                            step.name,
                            step_type,
                            i,
                            total_steps,
                            condition=step.condition,
                            condition_result=condition_result,
                        )
                        self.output_handler.on_step_skip(
                            step.name, reason="condition false"
                        )
                    continue

            step_state.status = StepStatus.IN_PROGRESS
            self._save_state()

            # Save initial "running" marker with step index for TUI display
            self._save_prompt_step_marker(
                step.name,
                step_state,
                step_type,
                step_index=i,
                hidden=step.hidden,
                output_types=self._get_output_types(i),
            )

            # Notify step start
            if self.output_handler:
                loop_info = self._get_loop_info(step)
                self.output_handler.on_step_start(
                    step.name,
                    step_type,
                    i,
                    total_steps,
                    condition=step.condition,
                    condition_result=condition_result,
                    loop_info=loop_info,
                )

            try:
                # Handle control flow constructs
                if step.for_loop and step.parallel_config:
                    success = self._execute_for_parallel_step(step, step_state)
                elif step.for_loop:
                    success = self._execute_for_step(step, step_state)
                elif step.repeat_config:
                    success = self._execute_repeat_step(step, step_state)
                elif step.while_config:
                    success = self._execute_while_step(step, step_state)
                elif step.parallel_config:
                    success = self._execute_parallel_step(step, step_state)
                elif step.is_prompt_step():
                    success = self._execute_prompt_step(step, step_state)
                elif step.is_python_step():
                    success = self._execute_python_step(step, step_state)
                else:
                    success = self._execute_bash_step(step, step_state)

                if not success:
                    step_state.status = StepStatus.FAILED
                    self.state.status = "failed"
                    self._save_state()
                    if self.output_handler:
                        self.output_handler.on_workflow_failed(
                            f"Step '{step.name}' failed"
                        )
                    return False

                step_state.status = StepStatus.COMPLETED
                self._save_state()
                step_type = self._get_step_type(step)
                step_source = (
                    step.bash
                    if step_type == "bash"
                    else (step.python if step_type == "python" else None)
                )
                self._save_prompt_step_marker(
                    step.name,
                    step_state,
                    step_type,
                    step_source,
                    i,
                    hidden=step.hidden,
                    output_types=self._get_output_types(i),
                )

                # Notify step complete
                if self.output_handler:
                    duration = time.time() - step_start_time
                    self.output_handler.on_step_complete(
                        step.name,
                        step_state.output,
                        duration=duration,
                    )

            except Exception as e:
                step_state.status = StepStatus.FAILED
                step_state.error = str(e)
                self.state.status = "failed"
                self._save_state()
                if self.output_handler:
                    self.output_handler.on_workflow_failed(str(e))
                raise WorkflowExecutionError(f"Step '{step.name}' failed: {e}") from e

        self.state.status = "completed"
        self._save_state()

        # Notify workflow complete
        if self.output_handler:
            final_output = None
            if self.state.steps:
                final_output = self.state.steps[-1].output
            self.output_handler.on_workflow_complete(final_output)

        return True

    def _get_step_type(self, step: WorkflowStep) -> str:
        """Get the display type for a step.

        Args:
            step: The workflow step.

        Returns:
            String type identifier (agent, bash, python, parallel).
        """
        if step.is_parallel_step():
            return "parallel"
        elif step.is_prompt_step():
            return "prompt"
        elif step.is_python_step():
            return "python"
        else:
            return "bash"

    def _get_loop_info(self, step: WorkflowStep) -> LoopInfo | None:
        """Get loop information for a step.

        Args:
            step: The workflow step.

        Returns:
            LoopInfo if step has a loop, None otherwise.
        """
        if step.for_loop:
            # Resolve the loop items to show count
            try:
                _, lists = self._resolve_for_lists(step.for_loop)
                items = lists[0] if lists else []
            except Exception:
                items = []
            return LoopInfo(loop_type="for", items=items)
        elif step.repeat_config:
            return LoopInfo(
                loop_type="repeat",
                max_iterations=step.repeat_config.max_iterations,
            )
        elif step.while_config:
            return LoopInfo(
                loop_type="while",
                max_iterations=step.while_config.max_iterations,
            )
        elif step.parallel_config:
            # Return parallel info - items are the nested step names
            nested_names = [s.name for s in step.parallel_config.steps]
            return LoopInfo(loop_type="parallel", items=nested_names)
        return None

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
        output_types: dict[str, str] | None = None,
        embedded_workflow_name: str | None = None,
    ) -> None:
        """Save a marker file for prompt steps to track them in the TUI.

        Args:
            step_name: Name of the prompt step.
            step_state: The runtime state for this step.
            step_type: Type of step ("prompt", "bash", or "python").
            step_source: Source code/command for bash/python steps.
            step_index: Index of the step in the workflow (0-based).
            parent_step_index: Index of the parent step for embedded workflow steps.
            parent_total_steps: Total steps in the parent workflow for embedded steps.
            is_pre_prompt_step: True if this is a pre-prompt step from an embedded
                workflow, which should be hidden in the Agents tab.
            diff_path: Path to the git diff file for this step, if available.
        """
        if embedded_workflow_name:
            marker_filename = f"prompt_step_{embedded_workflow_name}__{step_name}.json"
        else:
            marker_filename = f"prompt_step_{step_name}.json"
        marker_path = os.path.join(self.artifacts_dir, marker_filename)

        # Read existing marker once for preserving fields not passed by caller.
        existing_marker: dict[str, Any] | None = None
        try:
            with open(marker_path, encoding="utf-8") as f:
                existing_marker = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

        # Preserve step index fields when not provided (e.g. when
        # _execute_prompt_step saves a marker but the caller already
        # wrote one with proper step numbering).
        if step_index is None and existing_marker:
            step_index = existing_marker.get("step_index")
            if parent_step_index is None:
                parent_step_index = existing_marker.get("parent_step_index")
            if parent_total_steps is None:
                parent_total_steps = existing_marker.get("parent_total_steps")

        # Always preserve diff_path from existing marker when not provided,
        # so that execute()'s post-step marker rewrite doesn't clobber it.
        if diff_path is None and existing_marker:
            diff_path = existing_marker.get("diff_path")

        marker_data = {
            "workflow_name": self.workflow.name,
            "step_name": step_name,
            "status": step_state.status.value,
            "output": step_state.output,
            "artifacts_dir": self.artifacts_dir,
            "step_type": step_type,
            "step_source": step_source,
            "step_index": step_index,
            "total_steps": len(self.workflow.steps),
            "parent_step_index": parent_step_index,
            "parent_total_steps": parent_total_steps,
            "hidden": hidden,
            "is_pre_prompt_step": is_pre_prompt_step,
            "diff_path": diff_path,
            "output_types": output_types,
            "embedded_workflow_name": embedded_workflow_name,
            "error": step_state.error,
        }
        try:
            with open(marker_path, "w", encoding="utf-8") as f:
                json.dump(marker_data, f, indent=2, default=str)
        except Exception:
            # Non-critical - just for TUI visibility
            pass
