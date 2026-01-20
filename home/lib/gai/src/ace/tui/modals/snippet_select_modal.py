"""Snippet selection modal with filtering for the ace TUI."""

from rich.text import Text
from snippet_config import get_all_snippets
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from .base import FilterInput, OptionListNavigationMixin


class SnippetSelectModal(OptionListNavigationMixin, ModalScreen[str | None]):
    """Modal for selecting a snippet with filtering and preview."""

    _option_list_id = "snippet-list"
    BINDINGS = [*OptionListNavigationMixin.NAVIGATION_BINDINGS]

    def __init__(self) -> None:
        """Initialize the snippet modal."""
        super().__init__()
        self.snippets = get_all_snippets()
        self._filtered_names: list[str] = sorted(self.snippets.keys())

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="snippet-modal-container"):
            yield Label("Select Snippet", id="modal-title")
            if not self.snippets:
                yield Label("No snippets configured in ~/.config/gai/gai.yml")
            else:
                yield FilterInput(
                    placeholder="Type to filter...", id="snippet-filter-input"
                )
                with Horizontal(id="snippet-panels"):
                    with Vertical(id="snippet-list-panel"):
                        yield Label("Snippets", id="snippet-list-label")
                        yield OptionList(
                            *self._create_options(self._filtered_names),
                            id="snippet-list",
                        )
                    with Vertical(id="snippet-preview-panel"):
                        yield Label("Preview", id="snippet-preview-label")
                        with VerticalScroll(id="snippet-preview-scroll"):
                            yield Static("", id="snippet-preview")
                yield Static(
                    "j/k ↑/↓ ^n/^p: navigate • Enter: select • Esc/q: cancel",
                    id="snippet-hints",
                )

    def _create_styled_label(self, name: str) -> Text:
        """Create styled text for a snippet name."""
        text = Text()
        text.append("#", style="bold #87D7FF")  # Cyan hash
        text.append(name)
        return text

    def _create_options(self, names: list[str]) -> list[Option]:
        """Create options from snippet names."""
        return [Option(self._create_styled_label(name), id=name) for name in names]

    def _get_filtered_names(self, filter_text: str) -> list[str]:
        """Get snippet names that match the filter text."""
        all_names = sorted(self.snippets.keys())
        if not filter_text:
            return all_names
        filter_lower = filter_text.lower()
        return [name for name in all_names if filter_lower in name.lower()]

    def on_mount(self) -> None:
        """Focus the input and show initial preview on mount."""
        if self.snippets:
            filter_input = self.query_one("#snippet-filter-input", FilterInput)
            filter_input.focus()
            # Show preview for first item
            if self._filtered_names:
                self._update_preview_for_name(self._filtered_names[0])

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input change - update the option list."""
        self._filtered_names = self._get_filtered_names(event.value)
        option_list = self.query_one("#snippet-list", OptionList)
        option_list.clear_options()
        for option in self._create_options(self._filtered_names):
            option_list.add_option(option)
        # Update preview for first filtered item
        if self._filtered_names:
            self._update_preview_for_name(self._filtered_names[0])
        else:
            self._clear_preview()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Handle Enter key in input - select highlighted item."""
        if not self._filtered_names:
            return

        option_list = self.query_one("#snippet-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is not None and 0 <= highlighted < len(self._filtered_names):
            self.dismiss(self._filtered_names[highlighted])
        else:
            # Select first item if none highlighted
            self.dismiss(self._filtered_names[0])

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

    def _update_preview_for_name(self, name: str) -> None:
        """Update preview for a snippet by name."""
        try:
            preview = self.query_one("#snippet-preview", Static)
            content = self.snippets.get(name, "")
            preview.update(content)
        except Exception:
            pass

    def _clear_preview(self) -> None:
        """Clear the preview panel."""
        try:
            preview = self.query_one("#snippet-preview", Static)
            preview.update("")
        except Exception:
            pass
