"""Beautiful help modal for the ace TUI."""

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ..base import CopyModeForwardingMixin

if TYPE_CHECKING:
    from ...app import AceApp

from .bindings import (
    AGENTS_BINDINGS,
    AXE_BINDINGS,
    CLS_BINDINGS,
    COLUMN_SPLITS,
    CONTENT_WIDTH,
    TAB_DISPLAY_NAMES,
    TabName,
)
from .query_sections import add_query_history_section, add_saved_queries_section


def _create_load_query_action(slot: str) -> Callable[["HelpModal"], None]:
    """Create an action method for loading a saved query slot.

    Args:
        slot: The query slot number (0-9).

    Returns:
        An action method that loads the saved query and closes the modal.
    """

    def action(self: "HelpModal") -> None:
        if self._current_tab != "changespecs":
            return
        self.dismiss(None)
        getattr(cast("AceApp", self.app), f"action_load_saved_query_{slot}")()

    return action


class HelpModal(CopyModeForwardingMixin, ModalScreen[None]):
    """Beautiful help modal showing all keybindings and saved queries."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
        ("question_mark", "close", "Close"),
        ("ctrl+d", "scroll_down", "Scroll down"),
        ("ctrl+u", "scroll_up", "Scroll up"),
        # Saved query keybindings (CLs tab only)
        Binding("1", "load_query_1", "Load Q1", show=False),
        Binding("2", "load_query_2", "Load Q2", show=False),
        Binding("3", "load_query_3", "Load Q3", show=False),
        Binding("4", "load_query_4", "Load Q4", show=False),
        Binding("5", "load_query_5", "Load Q5", show=False),
        Binding("6", "load_query_6", "Load Q6", show=False),
        Binding("7", "load_query_7", "Load Q7", show=False),
        Binding("8", "load_query_8", "Load Q8", show=False),
        Binding("9", "load_query_9", "Load Q9", show=False),
        Binding("0", "load_query_0", "Load Q0", show=False),
        # Query history navigation (CLs tab only)
        Binding("circumflex_accent", "go_prev_query", "Prev Query", show=False),
        Binding("underscore", "go_next_query", "Next Query", show=False),
    ]

    def __init__(
        self,
        current_tab: "TabName",
        active_query: str | None = None,
    ) -> None:
        """Initialize the help modal.

        Args:
            current_tab: The currently active tab name.
            active_query: The current canonical query string (for highlighting).
        """
        super().__init__()
        self._current_tab = current_tab
        self._active_query = active_query

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="help-modal-container"):
            yield Static(self._build_title(), id="help-title")
            with VerticalScroll(id="help-content-scroll"):
                with Horizontal(id="help-columns"):
                    yield Static(self._build_left_column(), classes="help-column")
                    yield Static(self._build_right_column(), classes="help-column")
            yield Static(
                "Press ? / q / Esc to close  |  Ctrl+D/U to scroll",
                id="help-footer",
            )

    def _build_title(self) -> Text:
        """Build the styled title."""
        text = Text()
        text.append("\n")
        text.append("  ", style="")
        text.append("\u2726 ", style="bold #FFD700")  # Star
        text.append("gai ace Help", style="bold white")
        text.append(" \u2726", style="bold #FFD700")  # Star
        text.append("\n")
        tab_name = TAB_DISPLAY_NAMES.get(self._current_tab, self._current_tab)
        text.append(f"  {tab_name} Tab", style="#87D7FF")
        return text

    def _build_left_column(self) -> Text:
        """Build the left column content."""
        text = Text()

        # Add saved queries and history sections at the top for CLs tab
        if self._current_tab == "changespecs":
            add_saved_queries_section(text, self._active_query)
            add_query_history_section(text)

        # Get left-side bindings for current tab
        bindings = self._get_bindings_for_tab()
        split_idx = COLUMN_SPLITS.get(self._current_tab, 2)
        left_bindings = bindings[:split_idx]

        for section_name, section_bindings in left_bindings:
            self._add_section(text, section_name, section_bindings)

        return text

    def _build_right_column(self) -> Text:
        """Build the right column content."""
        text = Text()

        # Get right-side bindings for current tab
        bindings = self._get_bindings_for_tab()
        split_idx = COLUMN_SPLITS.get(self._current_tab, 2)
        right_bindings = bindings[split_idx:]

        for section_name, section_bindings in right_bindings:
            self._add_section(text, section_name, section_bindings)

        return text

    def _get_bindings_for_tab(
        self,
    ) -> list[tuple[str, list[tuple[str, str]]]]:
        """Get the keybinding sections for the current tab."""
        if self._current_tab == "changespecs":
            return CLS_BINDINGS
        elif self._current_tab == "agents":
            return AGENTS_BINDINGS
        else:  # axe
            return AXE_BINDINGS

    def _add_section(
        self,
        text: Text,
        section_name: str,
        bindings: list[tuple[str, str]],
    ) -> None:
        """Add a keybinding section to the text.

        Args:
            text: The Text object to append to.
            section_name: The section header name.
            bindings: List of (key, description) tuples.
        """
        # Section header with box drawing
        text.append("\n")
        text.append("  \u250c\u2500 ", style="dim #87D7FF")
        text.append(section_name, style="bold #87D7FF")
        text.append(" ", style="")
        # Fill with box drawing to create visual line
        remaining = 50 - len(section_name)
        text.append("\u2500" * remaining + "\u2510", style="dim #87D7FF")
        text.append("\n")

        # Keybindings
        key_width = 16
        max_desc_width = CONTENT_WIDTH - key_width - 2  # 2 chars min spacing
        for key, description in bindings:
            text.append("  \u2502  ", style="dim #87D7FF")
            # Key in bold teal (matches footer styling)
            text.append(f"{key:<{key_width}}", style="bold #00D7AF")
            # Truncate long descriptions to maintain box alignment
            if len(description) > max_desc_width:
                display_desc = description[: max_desc_width - 3] + "..."
            else:
                display_desc = description
            text.append(display_desc, style="")
            # Right border
            padding = CONTENT_WIDTH - key_width - len(display_desc)
            if padding > 0:
                text.append(" " * padding, style="")
            text.append(" \u2502", style="dim #87D7FF")
            text.append("\n")

        # Section footer
        text.append("  \u2514", style="dim #87D7FF")
        text.append("\u2500" * 53, style="dim #87D7FF")
        text.append("\u2518", style="dim #87D7FF")
        text.append("\n")

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(None)

    def action_scroll_down(self) -> None:
        """Scroll the help content down by half a page."""
        scroll = self.query_one("#help-content-scroll", VerticalScroll)
        height = scroll.scrollable_content_region.height
        scroll.scroll_relative(y=height // 2, animate=False)

    def action_scroll_up(self) -> None:
        """Scroll the help content up by half a page."""
        scroll = self.query_one("#help-content-scroll", VerticalScroll)
        height = scroll.scrollable_content_region.height
        scroll.scroll_relative(y=-(height // 2), animate=False)

    # --- Saved query actions (CLs tab only) ---
    # These are generated using a factory to reduce repetition
    action_load_query_0 = _create_load_query_action("0")
    action_load_query_1 = _create_load_query_action("1")
    action_load_query_2 = _create_load_query_action("2")
    action_load_query_3 = _create_load_query_action("3")
    action_load_query_4 = _create_load_query_action("4")
    action_load_query_5 = _create_load_query_action("5")
    action_load_query_6 = _create_load_query_action("6")
    action_load_query_7 = _create_load_query_action("7")
    action_load_query_8 = _create_load_query_action("8")
    action_load_query_9 = _create_load_query_action("9")

    # --- Query history navigation actions (CLs tab only) ---

    def action_go_prev_query(self) -> None:
        """Navigate to previous query and close modal."""
        if self._current_tab != "changespecs":
            return
        self.dismiss(None)
        cast("AceApp", self.app).action_prev_query()

    def action_go_next_query(self) -> None:
        """Navigate to next query and close modal."""
        if self._current_tab != "changespecs":
            return
        self.dismiss(None)
        cast("AceApp", self.app).action_next_query()
