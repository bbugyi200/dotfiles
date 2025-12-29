"""Query edit modal for the ace TUI."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class QueryEditModal(ModalScreen[str | None]):
    """Modal for editing the search query."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_query: str) -> None:
        """Initialize the query edit modal.

        Args:
            current_query: The current query string
        """
        super().__init__()
        self.current_query = current_query

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("Edit Search Query", id="modal-title")
            yield Input(value=self.current_query, id="query-input")
            with Horizontal(id="button-row"):
                yield Button("Apply", id="apply", variant="primary")
                yield Button("Cancel", id="cancel", variant="default")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#query-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "apply":
            query_input = self.query_one("#query-input", Input)
            self.dismiss(query_input.value)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)
