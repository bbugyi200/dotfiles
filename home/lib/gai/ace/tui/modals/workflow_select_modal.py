"""Workflow selection modal for the ace TUI."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option


class WorkflowSelectModal(ModalScreen[int | None]):
    """Modal for selecting which workflow to run."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
        ("j", "next_option", "Next"),
        ("k", "prev_option", "Previous"),
    ]

    def __init__(self, workflows: list[str]) -> None:
        """Initialize the workflow selection modal.

        Args:
            workflows: List of available workflow names
        """
        super().__init__()
        self.workflows = workflows

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("Select Workflow", id="modal-title")
            yield OptionList(
                *[
                    Option(f"{i + 1}. {name}", id=str(i))
                    for i, name in enumerate(self.workflows)
                ],
                id="workflow-list",
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        if event.option and event.option.id:
            self.dismiss(int(event.option.id))

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)

    def action_next_option(self) -> None:
        """Move to next option."""
        self.query_one("#workflow-list", OptionList).action_cursor_down()

    def action_prev_option(self) -> None:
        """Move to previous option."""
        self.query_one("#workflow-list", OptionList).action_cursor_up()
