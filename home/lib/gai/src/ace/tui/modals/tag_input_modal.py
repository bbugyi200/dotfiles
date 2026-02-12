"""Tag input modal for adding CL tags."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList
from textual.widgets import Input, Label


class _TagInput(Input):
    """Custom Input with readline-style key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
    ]


class TagInputModal(ModalScreen[tuple[str, str] | None]):
    """Modal for entering a tag name and value.

    Returns (tag_name, tag_value) on success, or None if cancelled.
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, saved_names: list[str]) -> None:
        """Initialize the tag input modal.

        Args:
            saved_names: Previously used tag names for autocomplete suggestions.
        """
        super().__init__()
        self._saved_names = saved_names

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        suggester = (
            SuggestFromList(self._saved_names, case_sensitive=False)
            if self._saved_names
            else None
        )
        with Container():
            yield Label("Add Tag to CL", id="modal-title")
            yield Label("Tag Name:", id="tag-name-label")
            yield _TagInput(
                placeholder="e.g. BUG",
                suggester=suggester,
                id="tag-name-input",
            )
            yield Label("Tag Value:", id="tag-value-label")
            yield _TagInput(
                placeholder="e.g. 12345",
                id="tag-value-input",
            )

    def on_mount(self) -> None:
        """Focus the tag name input on mount."""
        self.query_one("#tag-name-input", _TagInput).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in inputs."""
        if event.input.id == "tag-name-input":
            # Move focus to value input
            self.query_one("#tag-value-input", _TagInput).focus()
        elif event.input.id == "tag-value-input":
            # Validate and dismiss
            name = self.query_one("#tag-name-input", _TagInput).value.strip()
            value = self.query_one("#tag-value-input", _TagInput).value.strip()
            if not name:
                self.notify("Tag name cannot be empty", severity="error")
                self.query_one("#tag-name-input", _TagInput).focus()
                return
            if not value:
                self.notify("Tag value cannot be empty", severity="error")
                return
            self.dismiss((name.upper(), value))

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)
