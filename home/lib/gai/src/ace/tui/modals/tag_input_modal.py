"""Tag input modal for adding CL tags."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList


class _TagNameInput(Input):
    """Tag name input with readline-style key bindings and tag list navigation."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
        ("ctrl+n", "next_tag", "Next tag"),
        ("ctrl+p", "prev_tag", "Prev tag"),
    ]

    def action_next_tag(self) -> None:
        """Navigate to the next tag in the history list."""
        modal = self.screen
        assert isinstance(modal, TagInputModal)
        modal._navigate_tag_list(1)

    def action_prev_tag(self) -> None:
        """Navigate to the previous tag in the history list."""
        modal = self.screen
        assert isinstance(modal, TagInputModal)
        modal._navigate_tag_list(-1)


class _TagValueInput(Input):
    """Tag value input with readline-style key bindings and placeholder fill."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
        ("ctrl+e", "end_or_fill_placeholder", "End/Fill"),
    ]

    def action_end_or_fill_placeholder(self) -> None:
        """Fill placeholder if input is empty, otherwise move cursor to end."""
        if not self.value and self.placeholder:
            self.value = self.placeholder
            self.cursor_position = len(self.value)
        else:
            self.action_end()


class TagInputModal(ModalScreen[tuple[str, str] | None]):
    """Modal for entering a tag name and value.

    Returns (tag_name, tag_value) on success, or None if cancelled.
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, saved_tags: dict[str, str]) -> None:
        """Initialize the tag input modal.

        Args:
            saved_tags: Previously used tags (name→value) for suggestions.
        """
        super().__init__()
        self._saved_tags = saved_tags
        self._saved_names = list(saved_tags.keys())

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("Add Tag to CL", id="modal-title")
            yield Label("Tag Name:", id="tag-name-label")
            if self._saved_names:
                yield OptionList(*self._saved_names, id="tag-name-history")
            yield _TagNameInput(
                placeholder="e.g. BUG",
                id="tag-name-input",
            )
            yield Label("Tag Value:", id="tag-value-label")
            yield _TagValueInput(
                placeholder="e.g. 12345",
                id="tag-value-input",
            )

    def on_mount(self) -> None:
        """Focus the tag name input on mount."""
        self.query_one("#tag-name-input", _TagNameInput).focus()

    def _navigate_tag_list(self, direction: int) -> None:
        """Navigate the tag name history list.

        Args:
            direction: 1 for next (down), -1 for previous (up).
        """
        try:
            option_list = self.query_one("#tag-name-history", OptionList)
        except Exception:
            return

        if direction > 0:
            option_list.action_cursor_down()
        else:
            option_list.action_cursor_up()

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Auto-fill tag name input when a history item is highlighted."""
        option = event.option
        tag_name = option.prompt
        if isinstance(tag_name, str):
            name_input = self.query_one("#tag-name-input", _TagNameInput)
            name_input.value = tag_name
            name_input.cursor_position = len(tag_name)

            # Set last-used value as placeholder on the value input
            last_value = self._saved_tags.get(tag_name, "")
            value_input = self.query_one("#tag-value-input", _TagValueInput)
            value_input.placeholder = last_value if last_value else "e.g. 12345"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in inputs."""
        if event.input.id == "tag-name-input":
            # Move focus to value input
            self.query_one("#tag-value-input", _TagValueInput).focus()
        elif event.input.id == "tag-value-input":
            # Validate and dismiss
            name = self.query_one("#tag-name-input", _TagNameInput).value.strip()
            value = self.query_one("#tag-value-input", _TagValueInput).value.strip()
            if not name:
                self.notify("Tag name cannot be empty", severity="error")
                self.query_one("#tag-name-input", _TagNameInput).focus()
                return
            if not value:
                self.notify("Tag value cannot be empty", severity="error")
                return
            self.dismiss((name.upper(), value))

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)
