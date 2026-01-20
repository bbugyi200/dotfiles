"""Chat file selection modal for the ace TUI."""

import os
from dataclasses import dataclass
from datetime import datetime

from chat_history import (
    get_chat_file_full_path,
    list_chat_histories,
    load_chat_history,
    parse_chat_filename,
)
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from .base import FilterInput, OptionListNavigationMixin


@dataclass
class ChatFileItem:
    """Represents a chat file for selection."""

    basename: str
    full_path: str
    mtime: float
    workflow: str | None
    timestamp_str: str | None
    branch_or_workspace: str | None


class ChatSelectModal(OptionListNavigationMixin, ModalScreen[ChatFileItem | None]):
    """Modal for selecting a chat file to revive as an agent."""

    _option_list_id = "chat-select-list"
    BINDINGS = [*OptionListNavigationMixin.NAVIGATION_BINDINGS]

    def __init__(self) -> None:
        """Initialize the chat select modal."""
        super().__init__()
        self._all_items: list[ChatFileItem] = []
        self._filtered_items: list[ChatFileItem] = []
        self._load_items()

    def _load_items(self) -> None:
        """Load chat file items."""
        basenames = list_chat_histories()

        for basename in basenames:
            full_path = get_chat_file_full_path(basename)
            try:
                mtime = os.path.getmtime(full_path)
            except OSError:
                mtime = 0.0

            branch_or_workspace, workflow, _agent, timestamp = parse_chat_filename(
                basename
            )

            self._all_items.append(
                ChatFileItem(
                    basename=basename,
                    full_path=full_path,
                    mtime=mtime,
                    workflow=workflow,
                    timestamp_str=timestamp,
                    branch_or_workspace=branch_or_workspace,
                )
            )

        self._filtered_items = self._all_items.copy()

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="chat-select-modal-container"):
            yield Label("Revive Chat as Agent", id="modal-title")
            if not self._all_items:
                yield Label("No chat history found.")
            else:
                yield FilterInput(
                    placeholder="Type to filter by name...",
                    id="chat-select-filter-input",
                )
                with Horizontal(id="chat-select-panels"):
                    with Vertical(id="chat-select-list-panel"):
                        yield Label("Chats", id="chat-select-list-label")
                        yield OptionList(
                            *self._create_options(self._filtered_items),
                            id="chat-select-list",
                        )
                    with Vertical(id="chat-select-preview-panel"):
                        yield Label("Preview", id="chat-select-preview-label")
                        with VerticalScroll(id="chat-select-preview-scroll"):
                            yield Static("", id="chat-select-preview")
                            yield Static("", id="chat-select-metadata")
                yield Static(
                    "j/k ↑/↓ ^n/^p: navigate • Enter: select • Esc/q: cancel",
                    id="chat-select-hints",
                )

    def _create_styled_label(self, item: ChatFileItem) -> Text:
        """Create styled text for a chat list item."""
        text = Text()

        # Workflow indicator with color
        if item.workflow:
            workflow_colors = {
                "run": "#87AFFF",  # Blue
                "rerun": "#87AFFF",
                "crs": "#00D787",  # Cyan-green
                "mentor": "#AF87D7",  # Purple
                "fix_hook": "#FFAF00",  # Orange
                "summarize_hook": "#D7AF5F",  # Gold
            }
            color = workflow_colors.get(item.workflow, "#FFFFFF")
            text.append(f"[{item.workflow}] ", style=f"bold {color}")
        else:
            text.append("[?] ", style="dim")

        # Branch/workspace name
        if item.branch_or_workspace:
            text.append(item.branch_or_workspace, style="#00D7AF")
        else:
            text.append(item.basename[:30], style="dim")

        # Timestamp
        if item.timestamp_str:
            # Format: YYmmdd_HHMMSS -> HH:MM
            try:
                time_part = item.timestamp_str[7:11]  # HHMM
                formatted_time = f"{time_part[:2]}:{time_part[2:]}"
                text.append(f" {formatted_time}", style="dim")
            except (IndexError, ValueError):
                pass

        return text

    def _create_options(self, items: list[ChatFileItem]) -> list[Option]:
        """Create options from chat file items."""
        return [
            Option(self._create_styled_label(item), id=str(i))
            for i, item in enumerate(items)
        ]

    def _get_filtered_items(self, filter_text: str) -> list[ChatFileItem]:
        """Get items that match the filter text."""
        if not filter_text:
            return self._all_items.copy()

        filter_lower = filter_text.lower()
        return [
            item
            for item in self._all_items
            if filter_lower in item.basename.lower()
            or (
                item.branch_or_workspace
                and filter_lower in item.branch_or_workspace.lower()
            )
            or (item.workflow and filter_lower in item.workflow.lower())
        ]

    def on_mount(self) -> None:
        """Focus the input and show initial preview on mount."""
        if self._all_items:
            filter_input = self.query_one("#chat-select-filter-input", FilterInput)
            filter_input.focus()
            # Show preview for first item
            if self._filtered_items:
                self._update_preview(self._filtered_items[0])

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input change - update the option list."""
        self._filtered_items = self._get_filtered_items(event.value)
        option_list = self.query_one("#chat-select-list", OptionList)
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

        option_list = self.query_one("#chat-select-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is not None and 0 <= highlighted < len(self._filtered_items):
            self.dismiss(self._filtered_items[highlighted])
        else:
            # Select first item if none highlighted
            self.dismiss(self._filtered_items[0])

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
                self.dismiss(self._filtered_items[idx])

    def _update_preview(self, item: ChatFileItem) -> None:
        """Update preview panel with chat content and metadata."""
        try:
            preview = self.query_one("#chat-select-preview", Static)
            metadata = self.query_one("#chat-select-metadata", Static)

            # Load and truncate chat content for preview
            try:
                content = load_chat_history(item.full_path)
                # Truncate for preview
                max_preview_chars = 2000
                if len(content) > max_preview_chars:
                    content = content[:max_preview_chars] + "\n\n... (truncated)"
                preview.update(content)
            except Exception:
                preview.update("(Unable to load chat content)")

            # Metadata section
            meta_text = Text()
            meta_text.append("\n--- Metadata ---\n", style="dim")

            if item.branch_or_workspace:
                meta_text.append("CL/Branch: ", style="bold")
                meta_text.append(f"{item.branch_or_workspace}\n")

            if item.workflow:
                meta_text.append("Workflow: ", style="bold")
                meta_text.append(f"{item.workflow}\n")

            if item.timestamp_str:
                # Parse timestamp: YYmmdd_HHMMSS
                try:
                    ts = item.timestamp_str
                    formatted = (
                        f"20{ts[:2]}-{ts[2:4]}-{ts[4:6]} {ts[7:9]}:{ts[9:11]}:{ts[11:]}"
                    )
                    meta_text.append("Timestamp: ", style="bold")
                    meta_text.append(f"{formatted}\n")
                except (IndexError, ValueError):
                    pass

            # File modification time
            try:
                mtime_dt = datetime.fromtimestamp(item.mtime)
                meta_text.append("Modified: ", style="bold")
                meta_text.append(f"{mtime_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
            except Exception:
                pass

            meta_text.append("File: ", style="bold")
            meta_text.append(f"{item.full_path}\n")

            metadata.update(meta_text)

        except Exception:
            pass

    def _clear_preview(self) -> None:
        """Clear the preview panel."""
        try:
            preview = self.query_one("#chat-select-preview", Static)
            metadata = self.query_one("#chat-select-metadata", Static)
            preview.update("")
            metadata.update("")
        except Exception:
            pass
