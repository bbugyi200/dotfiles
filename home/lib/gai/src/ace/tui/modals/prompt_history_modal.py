"""Prompt history selection modal with filtering for the ace TUI."""

from dataclasses import dataclass

from prompt_history import PromptEntry, get_prompts_for_fzf
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.widgets.option_list import Option


class _FilterInput(Input):
    """Custom Input with readline-style key bindings."""

    BINDINGS = [
        ("ctrl+f", "cursor_right", "Forward"),
        ("ctrl+b", "cursor_left", "Backward"),
    ]


@dataclass
class _PromptDisplayItem:
    """Wrapper for prompt entry with display info."""

    entry: PromptEntry
    marker: str  # "*", "~", or " "
    display_branch: str  # Padded branch name


class PromptHistoryModal(ModalScreen[str | None]):
    """Modal for selecting a prompt from history with filtering and preview."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
        ("j", "next_option", "Next"),
        ("k", "prev_option", "Previous"),
        ("down", "next_option", "Next"),
        ("up", "prev_option", "Previous"),
        ("ctrl+n", "next_option", "Next"),
        ("ctrl+p", "prev_option", "Previous"),
    ]

    def __init__(
        self,
        sort_by: str | None = None,
        workspace: str | None = None,
    ) -> None:
        """Initialize the prompt history modal.

        Args:
            sort_by: Branch/CL name to prioritize in sorting.
            workspace: Workspace/project name for secondary sorting.
        """
        super().__init__()
        self._sort_by = sort_by
        self._workspace = workspace
        self._all_items: list[_PromptDisplayItem] = []
        self._filtered_items: list[_PromptDisplayItem] = []
        self._load_items()

    def _load_items(self) -> None:
        """Load prompt history items."""
        items = get_prompts_for_fzf(
            current_branch=self._sort_by,
            current_workspace=self._workspace,
        )

        if not items:
            return

        # Calculate max branch length for alignment
        max_branch_len = max(len(entry.branch_or_workspace) for _, entry in items)

        for display_str, entry in items:
            # Parse marker from display string (first char)
            marker = display_str[0] if display_str else " "
            display_branch = entry.branch_or_workspace.ljust(max_branch_len)

            self._all_items.append(
                _PromptDisplayItem(
                    entry=entry,
                    marker=marker,
                    display_branch=display_branch,
                )
            )

        self._filtered_items = self._all_items.copy()

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="prompt-history-modal-container"):
            yield Label("Select Prompt from History", id="modal-title")
            if not self._all_items:
                yield Label("No prompt history found.")
            else:
                # Header showing sort context
                header_text = self._get_header_text()
                yield Static(header_text, id="prompt-history-header")

                yield _FilterInput(
                    placeholder="Type to filter...", id="prompt-history-filter-input"
                )
                with Horizontal(id="prompt-history-panels"):
                    with Vertical(id="prompt-history-list-panel"):
                        yield Label("History", id="prompt-history-list-label")
                        yield OptionList(
                            *self._create_options(self._filtered_items),
                            id="prompt-history-list",
                        )
                    with Vertical(id="prompt-history-preview-panel"):
                        yield Label("Preview", id="prompt-history-preview-label")
                        with VerticalScroll(id="prompt-history-preview-scroll"):
                            yield Static("", id="prompt-history-preview")
                            yield Static("", id="prompt-history-metadata")
                yield Static(
                    "j/k ↑/↓ ^n/^p: navigate • Enter: select • Esc/q: cancel",
                    id="prompt-history-hints",
                )

    def _get_header_text(self) -> Text:
        """Get header text showing sort context."""
        text = Text()
        if self._sort_by and self._workspace:
            text.append("* ", style="bold green")
            text.append(f"= {self._sort_by}  ")
            text.append("~ ", style="bold yellow")
            text.append(f"= {self._workspace}")
        elif self._sort_by:
            text.append("* ", style="bold green")
            text.append(f"= {self._sort_by}")
        else:
            text.append("* ", style="bold green")
            text.append("= current branch")
        return text

    def _create_styled_label(self, item: _PromptDisplayItem) -> Text:
        """Create styled text for a prompt list item."""
        text = Text()

        # Color-coded marker
        if item.marker == "*":
            text.append("* ", style="bold green")
        elif item.marker == "~":
            text.append("~ ", style="bold yellow")
        else:
            text.append("  ")

        # Branch/workspace name (dimmed)
        text.append(item.display_branch, style="dim cyan")
        text.append(" | ", style="dim")

        # Truncated prompt preview
        preview = item.entry.text.replace("\n", " ").replace("\r", " ")
        if len(preview) > 40:
            preview = preview[:40] + "..."
        text.append(preview)

        return text

    def _create_options(self, items: list[_PromptDisplayItem]) -> list[Option]:
        """Create options from prompt items."""
        return [
            Option(self._create_styled_label(item), id=str(i))
            for i, item in enumerate(items)
        ]

    def _get_filtered_items(self, filter_text: str) -> list[_PromptDisplayItem]:
        """Get items that match the filter text."""
        if not filter_text:
            return self._all_items.copy()

        filter_lower = filter_text.lower()
        return [
            item
            for item in self._all_items
            if filter_lower in item.entry.text.lower()
            or filter_lower in item.entry.branch_or_workspace.lower()
        ]

    def on_mount(self) -> None:
        """Focus the input and show initial preview on mount."""
        if self._all_items:
            filter_input = self.query_one("#prompt-history-filter-input", _FilterInput)
            filter_input.focus()
            # Show preview for first item
            if self._filtered_items:
                self._update_preview(self._filtered_items[0])

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input change - update the option list."""
        self._filtered_items = self._get_filtered_items(event.value)
        option_list = self.query_one("#prompt-history-list", OptionList)
        option_list.clear_options()
        for option in self._create_options(self._filtered_items):
            option_list.add_option(option)
        # Update preview for first filtered item
        if self._filtered_items:
            self._update_preview(self._filtered_items[0])
        else:
            self._clear_preview()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Handle Enter key in input - select highlighted item."""
        if not self._filtered_items:
            return

        option_list = self.query_one("#prompt-history-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is not None and 0 <= highlighted < len(self._filtered_items):
            self.dismiss(self._filtered_items[highlighted].entry.text)
        else:
            # Select first item if none highlighted
            self.dismiss(self._filtered_items[0].entry.text)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Update preview when highlighting changes."""
        if event.option and event.option.id is not None:
            idx = int(event.option.id)
            if 0 <= idx < len(self._filtered_items):
                self._update_preview(self._filtered_items[idx])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        if event.option and event.option.id is not None:
            idx = int(event.option.id)
            if 0 <= idx < len(self._filtered_items):
                self.dismiss(self._filtered_items[idx].entry.text)

    def _update_preview(self, item: _PromptDisplayItem) -> None:
        """Update preview panel with full prompt and metadata."""
        try:
            preview = self.query_one("#prompt-history-preview", Static)
            metadata = self.query_one("#prompt-history-metadata", Static)

            # Full prompt text
            preview.update(item.entry.text)

            # Metadata section
            meta_text = Text()
            meta_text.append("\n--- Metadata ---\n", style="dim")
            meta_text.append("Branch: ", style="bold")
            meta_text.append(f"{item.entry.branch_or_workspace}\n")
            if item.entry.workspace:
                meta_text.append("Workspace: ", style="bold")
                meta_text.append(f"{item.entry.workspace}\n")
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
            preview = self.query_one("#prompt-history-preview", Static)
            metadata = self.query_one("#prompt-history-metadata", Static)
            preview.update("")
            metadata.update("")
        except Exception:
            pass

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(None)

    def action_next_option(self) -> None:
        """Move to next option."""
        if self._all_items:
            self.query_one("#prompt-history-list", OptionList).action_cursor_down()

    def action_prev_option(self) -> None:
        """Move to previous option."""
        if self._all_items:
            self.query_one("#prompt-history-list", OptionList).action_cursor_up()
