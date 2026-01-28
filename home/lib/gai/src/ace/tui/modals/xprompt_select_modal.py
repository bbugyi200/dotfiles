"""XPrompt selection modal with filtering for the ace TUI."""

from rich.markdown import Markdown
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.widgets.option_list import Option
from xprompt import get_all_snippets

from .base import FilterInput, OptionListNavigationMixin


class XPromptSelectModal(OptionListNavigationMixin, ModalScreen[str | None]):
    """Modal for selecting an xprompt with filtering and preview."""

    _option_list_id = "xprompt-list"
    BINDINGS = [
        *OptionListNavigationMixin.NAVIGATION_BINDINGS,
        ("ctrl+d", "scroll_down", "Scroll down"),
        ("ctrl+u", "scroll_up", "Scroll up"),
    ]

    def __init__(self) -> None:
        """Initialize the xprompt modal."""
        super().__init__()
        self.xprompts = get_all_snippets()
        self._filtered_names: list[str] = sorted(self.xprompts.keys())

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="xprompt-modal-container"):
            yield Label("Select XPrompt", id="modal-title")
            if not self.xprompts:
                yield Label("No xprompts configured")
            else:
                yield FilterInput(
                    placeholder="Type to filter...", id="xprompt-filter-input"
                )
                with Horizontal(id="xprompt-panels"):
                    with Vertical(id="xprompt-list-panel"):
                        yield Label("XPrompts", id="xprompt-list-label")
                        yield OptionList(
                            *self._create_options(self._filtered_names),
                            id="xprompt-list",
                        )
                    with Vertical(id="xprompt-preview-panel"):
                        yield Label("Preview", id="xprompt-preview-label")
                        with VerticalScroll(id="xprompt-preview-scroll"):
                            yield Static("", id="xprompt-preview")
                yield Static(
                    "j/k ↑/↓: navigate • ^d/^u: scroll preview • Enter: select • Esc/q: cancel",
                    id="xprompt-hints",
                )

    def _create_styled_label(self, name: str) -> Text:
        """Create styled text for an xprompt name."""
        text = Text()
        text.append("#", style="bold #87D7FF")  # Cyan hash
        text.append(name)
        return text

    def _create_options(self, names: list[str]) -> list[Option]:
        """Create options from xprompt names."""
        return [Option(self._create_styled_label(name), id=name) for name in names]

    def _get_filtered_names(self, filter_text: str) -> list[str]:
        """Get xprompt names that match the filter text."""
        all_names = sorted(self.xprompts.keys())
        if not filter_text:
            return all_names
        filter_lower = filter_text.lower()
        return [name for name in all_names if filter_lower in name.lower()]

    def on_mount(self) -> None:
        """Focus the input and show initial preview on mount."""
        if self.xprompts:
            filter_input = self.query_one("#xprompt-filter-input", FilterInput)
            filter_input.focus()
            # Show preview for first item
            if self._filtered_names:
                self._update_preview_for_name(self._filtered_names[0])

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input change - update the option list."""
        self._filtered_names = self._get_filtered_names(event.value)
        option_list = self.query_one("#xprompt-list", OptionList)
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

        option_list = self.query_one("#xprompt-list", OptionList)
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

    def action_scroll_down(self) -> None:
        """Scroll preview panel down (half page)."""
        scroll = self.query_one("#xprompt-preview-scroll", VerticalScroll)
        scroll.scroll_relative(y=10)

    def action_scroll_up(self) -> None:
        """Scroll preview panel up (half page)."""
        scroll = self.query_one("#xprompt-preview-scroll", VerticalScroll)
        scroll.scroll_relative(y=-10)

    def _update_preview_for_name(self, name: str) -> None:
        """Update preview for an xprompt by name."""
        try:
            preview = self.query_one("#xprompt-preview", Static)
            content = self.xprompts.get(name, "")
            # Render as markdown for syntax highlighting
            preview.update(Markdown(content))
        except Exception:
            pass

    def _clear_preview(self) -> None:
        """Clear the preview panel."""
        try:
            preview = self.query_one("#xprompt-preview", Static)
            preview.update("")
        except Exception:
            pass


# Backward compatibility alias
SnippetSelectModal = XPromptSelectModal
