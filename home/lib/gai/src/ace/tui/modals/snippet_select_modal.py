"""Snippet selection modal for the ace TUI."""

from snippet_config import get_all_snippets
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option


class SnippetSelectModal(ModalScreen[str | None]):
    """Modal for selecting a snippet to insert."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
        ("j", "next_option", "Next"),
        ("k", "prev_option", "Previous"),
    ]

    def __init__(self) -> None:
        """Initialize the snippet modal."""
        super().__init__()
        self.snippets = get_all_snippets()

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Label("Select Snippet", id="modal-title")
            if not self.snippets:
                yield Label("No snippets configured in ~/.config/gai/gai.yml")
            else:
                yield OptionList(
                    *[
                        Option(f"#{name}", id=name)
                        for name in sorted(self.snippets.keys())
                    ],
                    id="snippet-list",
                )
                yield Static("", id="snippet-preview")

    def on_mount(self) -> None:
        """Initialize preview when mounted."""
        if self.snippets:
            option_list = self.query_one("#snippet-list", OptionList)
            # Show preview for first item
            if option_list.option_count > 0:
                self._update_preview(0)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Update preview when highlighting changes."""
        if event.option and event.option.id:
            self._update_preview_for_name(str(event.option.id))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        if event.option and event.option.id:
            self.dismiss(str(event.option.id))

    def _update_preview(self, index: int) -> None:
        """Update the preview for the option at the given index."""
        option_list = self.query_one("#snippet-list", OptionList)
        option = option_list.get_option_at_index(index)
        if option and option.id:
            self._update_preview_for_name(str(option.id))

    def _update_preview_for_name(self, name: str) -> None:
        """Update preview for a snippet by name."""
        preview = self.query_one("#snippet-preview", Static)
        content = self.snippets.get(name, "")
        # Truncate preview to first 3 lines
        lines = content.split("\n")[:3]
        preview_text = "\n".join(lines)
        if len(content.split("\n")) > 3:
            preview_text += "\n..."
        preview.update(preview_text)

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)

    def action_next_option(self) -> None:
        """Move to next option."""
        if self.snippets:
            self.query_one("#snippet-list", OptionList).action_cursor_down()

    def action_prev_option(self) -> None:
        """Move to previous option."""
        if self.snippets:
            self.query_one("#snippet-list", OptionList).action_cursor_up()
