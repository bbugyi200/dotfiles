"""Step execution mixin for workflow execution.

This module provides the combined StepMixin class that includes all step
execution functionality. It combines:
- ScriptStepMixin: bash and python step execution
- EmbeddedWorkflowMixin: embedded workflow detection and expansion
- PromptStepMixin: prompt step execution with agent invocation

The individual mixins are split into separate files to keep file sizes manageable.
"""

from xprompt.workflow_executor_steps_embedded import (
    _WORKFLOW_REF_PATTERN,
    EmbeddedWorkflowMixin,
)
from xprompt.workflow_executor_steps_prompt import PromptStepMixin, capture_git_diff
from xprompt.workflow_executor_steps_script import ScriptStepMixin

# Re-export for backward compatibility
__all__ = ["StepMixin", "_WORKFLOW_REF_PATTERN", "capture_git_diff"]


class StepMixin(ScriptStepMixin, EmbeddedWorkflowMixin, PromptStepMixin):
    """Combined mixin providing all step execution functionality.

    MRO: StepMixin -> ScriptStepMixin -> EmbeddedWorkflowMixin -> PromptStepMixin

    This class inherits from all step-related mixins, combining their
    functionality. The MRO ensures proper method resolution across mixins.

    Required attributes (from WorkflowExecutor):
        - workflow: Workflow
        - context: dict[str, Any]
        - artifacts_dir: str
        - hitl_handler: HITLHandler | None
        - output_handler: WorkflowOutputHandler | None
        - state: WorkflowState

    Required methods (from WorkflowExecutor):
        - _save_state() -> None
        - _save_prompt_step_marker(step_name, step_state, ...) -> None
        - _get_step_type(step) -> str
        - _evaluate_condition(condition) -> bool
    """

    pass
