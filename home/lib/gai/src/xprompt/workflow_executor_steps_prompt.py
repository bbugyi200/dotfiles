"""Prompt step execution mixin."""

import os
import subprocess
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
    from xprompt.workflow_output import WorkflowOutputHandler


def capture_git_diff() -> str | None:
    """Capture uncommitted changes as a git diff.

    Returns:
        The git diff output, or None if no changes or an error occurred.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except Exception:
        pass
    return None


class PromptStepMixin:
    """Mixin class providing prompt step execution.

    This mixin requires the following attributes on self:
        - workflow: Workflow
        - context: dict[str, Any]
        - artifacts_dir: str
        - hitl_handler: HITLHandler | None
        - state: WorkflowState

    This mixin requires the following methods on self:
        - _save_state() -> None
        - _save_prompt_step_marker(step_name, step_state, ...) -> None
        - _expand_embedded_workflows_in_prompt(prompt) -> tuple
        - _execute_embedded_workflow_steps(steps, context, name, ...) -> bool
    """

    # Type hints for attributes from WorkflowExecutor
    workflow: Workflow
    context: dict[str, Any]
    artifacts_dir: str
    hitl_handler: HITLHandler | None
    output_handler: "WorkflowOutputHandler | None"
    state: WorkflowState

    # Method type declarations for methods provided by other mixins/main class
    _save_state: Any  # () -> None
    _save_prompt_step_marker: Any  # (step_name, step_state, ...) -> None
    _expand_embedded_workflows_in_prompt: Any  # (prompt) -> tuple
    _execute_embedded_workflow_steps: Any  # (steps, context, name, ...) -> bool
    _propagate_last_embedded_output: (
        Any  # (embedded_workflows, step, step_state) -> None
    )

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
            process_xprompt_references,
        )

        if not step.prompt:
            raise WorkflowExecutionError(f"Prompt step '{step.name}' has no prompt")

        # Render prompt with Jinja2 context
        rendered_prompt = render_template(step.prompt, self.context)

        # Expand xprompt references FIRST
        # This allows xprompts to contain embedded workflow references (like #json:...)
        # which will be expanded in the next step
        expanded_prompt = process_xprompt_references(
            rendered_prompt,
            extra_xprompts=self.workflow.xprompts,
            scope=self.context,
        )

        # Then expand embedded workflows
        # This executes pre-steps and replaces workflow refs with prompt_part content
        expanded_prompt, embedded_workflows, _ = (
            self._expand_embedded_workflows_in_prompt(expanded_prompt)
        )

        # Save initial marker to show step is running in TUI
        step_state.status = StepStatus.IN_PROGRESS
        self._save_prompt_step_marker(step.name, step_state, hidden=step.hidden)

        # Invoke agent
        # Extract base workflow name (without project prefix) to avoid slashes in filenames
        base_name = (
            self.workflow.name.split("/")[-1]
            if "/" in self.workflow.name
            else self.workflow.name
        )
        response = invoke_agent(
            expanded_prompt,
            agent_type=f"workflow-{base_name}-{step.name}",
            artifacts_dir=self.artifacts_dir,
            workflow=self.workflow.name,
        )
        response_text = ensure_str_content(response.content)

        # Parse and validate output
        output: dict[str, Any] = {}

        if step.output:
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

        # HITL review if required
        if step.hitl and self.hitl_handler:
            step_state.status = StepStatus.WAITING_HITL
            self.state.status = "waiting_hitl"
            self._save_state()
            self._save_prompt_step_marker(step.name, step_state, hidden=step.hidden)

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

        # Capture git diff if changes were made
        diff_content = capture_git_diff()
        diff_path: str | None = None
        if diff_content:
            diff_path = os.path.join(self.artifacts_dir, f"{step.name}_diff.txt")
            try:
                with open(diff_path, "w", encoding="utf-8") as f:
                    f.write(diff_content)
            except Exception:
                diff_path = None

        # Save prompt step marker for TUI visibility
        self._save_prompt_step_marker(
            step.name, step_state, diff_path=diff_path, hidden=step.hidden
        )

        # Execute post-steps from embedded workflows
        cumulative_post_offset = 0
        for info in embedded_workflows:
            if info.post_steps:
                from xprompt.workflow_output import ParentStepContext

                # Make agent prompt and response available to post-steps
                info.context["_prompt"] = expanded_prompt
                info.context["_response"] = response_text
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
                        f"Post-steps for embedded workflow in step '{step.name}' failed"
                    )
                cumulative_post_offset += len(info.post_steps)

        # Propagate output from last embedded workflow's last post-step
        self._propagate_last_embedded_output(embedded_workflows, step, step_state)

        return True
