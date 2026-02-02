"""HITL (Human-in-the-Loop) types for workflow execution."""

from typing import Any, Protocol


class HITLHandler(Protocol):
    """Protocol for human-in-the-loop handlers."""

    def prompt(
        self,
        step_name: str,
        step_type: str,
        output: Any,
        *,
        has_output: bool = False,
    ) -> "HITLResult":
        """Prompt the user for action on step output.

        Args:
            step_name: Name of the step being reviewed.
            step_type: Either "agent" or "bash".
            output: The step's output data.
            has_output: Whether the step has an output field defined.

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
