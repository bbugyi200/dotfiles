"""HITL (Human-in-the-Loop) types for workflow execution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from xprompt.workflow_models import WorkflowStep


def output_types_from_step(step: WorkflowStep) -> dict[str, str] | None:
    """Get the output type mapping for a workflow step.

    Extracts field name to type mappings from the step's OutputSpec schema.

    Args:
        step: The workflow step definition.

    Returns:
        Dict mapping field names to type strings, or None if no output spec.
    """
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


class HITLHandler(Protocol):
    """Protocol for human-in-the-loop handlers."""

    def prompt(
        self,
        step_name: str,
        step_type: str,
        output: Any,
        *,
        has_output: bool = False,
        output_types: dict[str, str] | None = None,
    ) -> HITLResult:
        """Prompt the user for action on step output.

        Args:
            step_name: Name of the step being reviewed.
            step_type: Either "prompt" or "bash".
            output: The step's output data.
            has_output: Whether the step has an output field defined.
            output_types: Mapping of field names to their types (e.g. "path").

        Returns:
            HITLResult indicating the user's decision.
        """
        ...


class HITLResult:
    """Result of a HITL prompt."""

    def __init__(
        self,
        action: str,
        feedback: str | None = None,
        approved: bool = False,
        edited_output: Any = None,
    ) -> None:
        """Initialize HITL result.

        Args:
            action: One of "accept", "edit", "reject", "rerun", or "feedback".
            feedback: User feedback text (for "feedback" action).
            approved: Whether the user approved (for confirmation prompts).
            edited_output: Edited data from user (for "edit" action).
        """
        self.action = action
        self.feedback = feedback
        self.approved = approved
        self.edited_output = edited_output
