"""Command history selection modal with filtering for the ace TUI."""

from dataclasses import dataclass

from command_history import CommandEntry, get_commands_for_display
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from .base import FilterInput, OptionListNavigationMixin


@dataclass
class _CommandDisplayItem:
    """Wrapper for command entry with display info."""

    entry: CommandEntry
    marker: str  # "*", "~", or " "
    display_context: str  # Padded project/CL context


class CommandHistoryModal(OptionListNavigationMixin, ModalScreen[str | None]):
    """Modal for selecting a command from history with filtering and preview."""

    _option_list_id = "command-history-list"
    BINDINGS = [
        *OptionListNavigationMixin.NAVIGATION_BINDINGS,
    ]

    def __init__(
        self,
        current_cl: str | None = None,
        current_project: str | None = None,
    ) -> None:
        """Initialize the command history modal.

        Args:
            current_cl: CL/ChangeSpec name to prioritize in sorting.
            current_project: Project name for secondary sorting.
        """
        super().__init__()
        self._current_cl = current_cl
        self._current_project = current_project
        self._all_items: list[_CommandDisplayItem] = []
        self._filtered_items: list[_CommandDisplayItem] = []
        self._load_items()

    def _load_items(self) -> None:
        """Load command history items."""
        items = get_commands_for_display(
            current_cl=self._current_cl,
            current_project=self._current_project,
        )

        if not items:
            return

        # Calculate max context length for alignment
        max_context_len = max(
            len(f"{entry.project}/{entry.cl_name}" if entry.cl_name else entry.project)
            for _, entry in items
        )

        for display_str, entry in items:
            # Parse marker from display string (first char)
            marker = display_str[0] if display_str else " "
            # Build context string
            if entry.cl_name:
                context = f"{entry.project}/{entry.cl_name}"
            else:
                context = entry.project
            display_context = context.ljust(max_context_len)

            self._all_items.append(
                _CommandDisplayItem(
                    entry=entry,
                    marker=marker,
                    display_context=display_context,
                )
            )

        self._filtered_items = self._all_items.copy()

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="command-history-modal-container"):
            yield Label("Run Command", id="modal-title")
            # Header showing sort context
            header_text = self._get_header_text()
            yield Static(header_text, id="command-history-header")

            yield FilterInput(
                placeholder="Type to filter or enter new command...",
                id="command-history-filter-input",
            )
            with Horizontal(id="command-history-panels"):
                with Vertical(id="command-history-list-panel"):
                    yield Label("History", id="command-history-list-label")
                    yield OptionList(
                        *self._create_options(self._filtered_items),
                        id="command-history-list",
                    )
                with Vertical(id="command-history-preview-panel"):
                    yield Label("Details", id="command-history-preview-label")
                    with VerticalScroll(id="command-history-preview-scroll"):
                        yield Static("", id="command-history-preview")
                        yield Static("", id="command-history-metadata")
            yield Static(
                "j/k ^n/^p: navigate | Enter: submit selected or typed | Esc/q: cancel",
                id="command-history-hints",
            )

    def _get_header_text(self) -> Text:
        """Get header text showing sort context."""
        text = Text()
        if self._current_cl and self._current_project:
            text.append("* ", style="bold green")
            text.append(f"= {self._current_cl}  ")
            text.append("~ ", style="bold yellow")
            text.append(f"= {self._current_project}")
        elif self._current_project:
            text.append("~ ", style="bold yellow")
            text.append(f"= {self._current_project}")
        else:
            text.append("Showing all commands")
        return text

    def _create_styled_label(self, item: _CommandDisplayItem) -> Text:
        """Create styled text for a command list item."""
        text = Text()

        # Color-coded marker
        if item.marker == "*":
            text.append("* ", style="bold green")
        elif item.marker == "~":
            text.append("~ ", style="bold yellow")
        else:
            text.append("  ")

        # Project/CL context (dimmed)
        text.append(item.display_context, style="dim cyan")
        text.append(" | ", style="dim")

        # Truncated command preview
        preview = item.entry.command
        if len(preview) > 35:
            preview = preview[:35] + "..."
        text.append(preview)

        return text

    def _create_options(self, items: list[_CommandDisplayItem]) -> list[Option]:
        """Create options from command items."""
        return [
            Option(self._create_styled_label(item), id=str(i))
            for i, item in enumerate(items)
        ]

    def _get_filtered_items(self, filter_text: str) -> list[_CommandDisplayItem]:
        """Get items that match the filter text."""
        if not filter_text:
            return self._all_items.copy()

        filter_lower = filter_text.lower()
        return [
            item
            for item in self._all_items
            if filter_lower in item.entry.command.lower()
            or filter_lower in item.entry.project.lower()
            or (item.entry.cl_name and filter_lower in item.entry.cl_name.lower())
        ]

    def _get_selected_command(self) -> str | None:
        """Get the command text for the currently highlighted item."""
        if not self._filtered_items:
            return None
        option_list = self.query_one("#command-history-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is not None and 0 <= highlighted < len(self._filtered_items):
            return self._filtered_items[highlighted].entry.command
        return self._filtered_items[0].entry.command

    def on_mount(self) -> None:
        """Focus the input and show initial preview on mount."""
        filter_input = self.query_one("#command-history-filter-input", FilterInput)
        filter_input.focus()
        # Show preview for first item if history exists
        if self._filtered_items:
            self._update_preview(self._filtered_items[0])

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input change - update the option list."""
        self._filtered_items = self._get_filtered_items(event.value)
        option_list = self.query_one("#command-history-list", OptionList)
        option_list.clear_options()
        for option in self._create_options(self._filtered_items):
            option_list.add_option(option)
        # Update preview for first filtered item
        if self._filtered_items:
            self._update_preview(self._filtered_items[0])
        else:
            self._clear_preview()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key - submit selected command or typed text."""
        # If there's a selected history item, use that
        if self._filtered_items:
            command = self._get_selected_command()
            if command:
                self.dismiss(command)
                return

        # Otherwise, submit the typed text as a new command
        typed_text = event.value.strip()
        if typed_text:
            self.dismiss(typed_text)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Update preview when highlighting changes."""
        if event.option and event.option.id is not None:
            idx = int(event.option.id)
            if 0 <= idx < len(self._filtered_items):
                self._update_preview(self._filtered_items[idx])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection (click/double-click) - submit directly."""
        if event.option and event.option.id is not None:
            idx = int(event.option.id)
            if 0 <= idx < len(self._filtered_items):
                self.dismiss(self._filtered_items[idx].entry.command)

    def _update_preview(self, item: _CommandDisplayItem) -> None:
        """Update preview panel with full command and metadata."""
        try:
            preview = self.query_one("#command-history-preview", Static)
            metadata = self.query_one("#command-history-metadata", Static)

            # Full command text
            preview.update(item.entry.command)

            # Metadata section
            meta_text = Text()
            meta_text.append("\n--- Metadata ---\n", style="dim")
            meta_text.append("Project: ", style="bold")
            meta_text.append(f"{item.entry.project}\n")
            if item.entry.cl_name:
                meta_text.append("CL: ", style="bold")
                meta_text.append(f"{item.entry.cl_name}\n")
            meta_text.append("Created: ", style="bold")
            meta_text.append(f"{item.entry.timestamp}\n")
            meta_text.append("Last Used: ", style="bold")
            meta_text.append(f"{item.entry.last_used}\n")
            metadata.update(meta_text)

        except Exception:
            pass

    def _clear_preview(self) -> None:
        """Clear the preview panel."""
        try:
            preview = self.query_one("#command-history-preview", Static)
            metadata = self.query_one("#command-history-metadata", Static)
            preview.update("")
            metadata.update("")
        except Exception:
            pass
