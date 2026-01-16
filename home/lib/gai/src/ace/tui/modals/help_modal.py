"""Beautiful help modal for the ace TUI."""

from typing import TYPE_CHECKING, Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ...query_history import load_query_history
from ...saved_queries import KEY_ORDER, load_saved_queries
from ..widgets.changespec_detail import build_query_text

if TYPE_CHECKING:
    TabName = Literal["changespecs", "agents", "axe"]


# Keybinding definitions for each tab
# Each section is (section_name, list of (key, description) tuples)
_CLS_BINDINGS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Navigation",
        [
            ("j / k", "Move to next / previous CL"),
            ("Ctrl+D / U", "Scroll detail panel down / up"),
        ],
    ),
    (
        "CL Actions",
        [
            ("a", "Accept proposal"),
            ("b", "Rebase CL onto parent"),
            ("d", "Show diff"),
            ("f", "Find reviewers"),
            ("h", "Edit hooks"),
            ("m", "Mail CL"),
            ("s", "Change status"),
            ("v", "View files"),
            ("w", "Reword CL description"),
            ("@", "Edit spec file"),
        ],
    ),
    (
        "Fold Mode",
        [
            ("z c", "Toggle commits section"),
            ("z h", "Toggle hooks section"),
            ("z m", "Toggle mentors section"),
            ("z z", "Toggle all sections"),
        ],
    ),
    (
        "Workflows & Agents",
        [
            ("r", "Run workflow"),
            ("<space>", "Run custom agent"),
        ],
    ),
    (
        "Queries",
        [
            ("/", "Edit search query"),
            ("0-9", "Load saved query"),
            ("^", "Previous query"),
            ("_", "Next query"),
        ],
    ),
    (
        "Axe Control",
        [
            ("X", "Start / stop axe daemon"),
            ("Q", "Stop axe and quit"),
        ],
    ),
    (
        "General",
        [
            ("Tab / Shift+Tab", "Switch tabs"),
            ("%", "Copy to clipboard"),
            ("y", "Refresh"),
            ("q", "Quit"),
            ("?", "Show this help"),
        ],
    ),
]

_AGENTS_BINDINGS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Navigation",
        [
            ("j / k", "Move to next / previous agent"),
            ("Ctrl+D / U", "Scroll diff panel down / up"),
            ("Ctrl+F / B", "Scroll prompt panel down / up"),
        ],
    ),
    (
        "Agent Actions",
        [
            ("<space>", "Run custom agent"),
            ("x", "Kill running / dismiss completed agent"),
            ("@", "Edit chat in editor"),
            ("l", "Toggle diff/prompt layout priority"),
        ],
    ),
    (
        "Clipboard",
        [
            ("%", "Copy chat to clipboard"),
        ],
    ),
    (
        "Axe Control",
        [
            ("X", "Start / stop axe daemon"),
            ("Q", "Stop axe and quit"),
        ],
    ),
    (
        "General",
        [
            ("Tab / Shift+Tab", "Switch tabs"),
            ("y", "Refresh"),
            ("q", "Quit"),
            ("?", "Show this help"),
        ],
    ),
]

_AXE_BINDINGS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Navigation",
        [
            ("g", "Scroll to top"),
            ("G", "Scroll to bottom"),
        ],
    ),
    (
        "Axe Control",
        [
            ("X", "Start / stop axe daemon"),
            ("Q", "Stop axe and quit"),
        ],
    ),
    (
        "Clipboard",
        [
            ("%", "Copy axe output to clipboard"),
        ],
    ),
    (
        "General",
        [
            ("Tab / Shift+Tab", "Switch tabs"),
            ("y", "Refresh"),
            ("q", "Quit"),
            ("?", "Show this help"),
        ],
    ),
]

_TAB_DISPLAY_NAMES = {
    "changespecs": "CLs",
    "agents": "Agents",
    "axe": "Axe",
}

# Column split indices for each tab (left column gets indices < split, right gets >= split)
_COLUMN_SPLITS = {
    "changespecs": 2,  # Left: Navigation, CL Actions; Right: rest
    "agents": 2,  # Left: Navigation, Agent Actions; Right: rest
    "axe": 2,  # Left: Navigation, Axe Control; Right: rest
}


class HelpModal(ModalScreen[None]):
    """Beautiful help modal showing all keybindings and saved queries."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
        ("question_mark", "close", "Close"),
        ("ctrl+d", "scroll_down", "Scroll down"),
        ("ctrl+u", "scroll_up", "Scroll up"),
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
        tab_name = _TAB_DISPLAY_NAMES.get(self._current_tab, self._current_tab)
        text.append(f"  {tab_name} Tab", style="#87D7FF")
        return text

    def _build_left_column(self) -> Text:
        """Build the left column content."""
        text = Text()

        # Add saved queries and history sections at the top for CLs tab
        if self._current_tab == "changespecs":
            self._add_saved_queries_section(text)
            self._add_query_history_section(text)

        # Get left-side bindings for current tab
        bindings = self._get_bindings_for_tab()
        split_idx = _COLUMN_SPLITS.get(self._current_tab, 2)
        left_bindings = bindings[:split_idx]

        for section_name, section_bindings in left_bindings:
            self._add_section(text, section_name, section_bindings)

        return text

    def _build_right_column(self) -> Text:
        """Build the right column content."""
        text = Text()

        # Get right-side bindings for current tab
        bindings = self._get_bindings_for_tab()
        split_idx = _COLUMN_SPLITS.get(self._current_tab, 2)
        right_bindings = bindings[split_idx:]

        for section_name, section_bindings in right_bindings:
            self._add_section(text, section_name, section_bindings)

        return text

    def _get_bindings_for_tab(
        self,
    ) -> list[tuple[str, list[tuple[str, str]]]]:
        """Get the keybinding sections for the current tab."""
        if self._current_tab == "changespecs":
            return _CLS_BINDINGS
        elif self._current_tab == "agents":
            return _AGENTS_BINDINGS
        else:  # axe
            return _AXE_BINDINGS

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
        for key, description in bindings:
            text.append("  \u2502  ", style="dim #87D7FF")
            # Key in bold teal (matches footer styling)
            text.append(f"{key:<16}", style="bold #00D7AF")
            text.append(description, style="")
            # Right border
            padding = 50 - len(key.ljust(16)) - len(description)
            if padding > 0:
                text.append(" " * padding, style="")
            text.append(" \u2502", style="dim #87D7FF")
            text.append("\n")

        # Section footer
        text.append("  \u2514", style="dim #87D7FF")
        text.append("\u2500" * 53, style="dim #87D7FF")
        text.append("\u2518", style="dim #87D7FF")
        text.append("\n")

    def _add_saved_queries_section(self, text: Text) -> None:
        """Add the saved queries section (CLs tab only).

        Args:
            text: The Text object to append to.
        """
        queries = load_saved_queries()

        # Section header
        text.append("\n")
        text.append("  \u250c\u2500 ", style="dim #FFD700")
        text.append("Saved Queries", style="bold #FFD700")
        text.append(" ", style="")
        remaining = 50 - len("Saved Queries")
        text.append("\u2500" * remaining + "\u2510", style="dim #FFD700")
        text.append("\n")

        if not queries:
            text.append("  \u2502  ", style="dim #FFD700")
            text.append("No saved queries", style="dim italic")
            text.append(" " * 34, style="")
            text.append(" \u2502", style="dim #FFD700")
            text.append("\n")
        else:
            for slot in KEY_ORDER:
                if slot in queries:
                    query = queries[slot]
                    is_active = (
                        self._active_query is not None and query == self._active_query
                    )

                    text.append("  \u2502  ", style="dim #FFD700")

                    # Slot number with styling
                    slot_style = "bold #00FF00" if is_active else "#228B22"
                    text.append(f"[{slot}]", style=slot_style)
                    text.append("  ", style="")

                    # Query with syntax highlighting (truncated if needed)
                    max_query_len = 42
                    if len(query) > max_query_len:
                        display_query = query[: max_query_len - 3] + "..."
                    else:
                        display_query = query

                    text.append_text(build_query_text(display_query))

                    # Active indicator
                    if is_active:
                        padding = max_query_len - len(display_query) - 6
                        if padding > 0:
                            text.append(" " * padding, style="")
                        text.append(" \u25cf active", style="bold #00FF00")
                    else:
                        padding = max_query_len - len(display_query) + 3
                        if padding > 0:
                            text.append(" " * padding, style="")

                    text.append(" \u2502", style="dim #FFD700")
                    text.append("\n")

        # Section footer
        text.append("  \u2514", style="dim #FFD700")
        text.append("\u2500" * 53, style="dim #FFD700")
        text.append("\u2518", style="dim #FFD700")
        text.append("\n")

    def _add_query_history_section(self, text: Text) -> None:
        """Add the query history stacks section (CLs tab only).

        Shows last 5 entries from each stack with visual indicators.

        Args:
            text: The Text object to append to.
        """
        stacks = load_query_history()

        # Section header
        text.append("\n")
        text.append("  \u250c\u2500 ", style="dim #FFD700")
        text.append("Query History", style="bold #FFD700")
        text.append(" ", style="")
        remaining = 50 - len("Query History")
        text.append("\u2500" * remaining + "\u2510", style="dim #FFD700")
        text.append("\n")

        # Show last 5 from prev stack (most recent first = reversed)
        max_display = 5
        prev_display = list(reversed(stacks.prev[-max_display:]))
        next_display = list(reversed(stacks.next[-max_display:]))
        prev_total = len(stacks.prev)
        next_total = len(stacks.next)

        if not prev_display and not next_display:
            text.append("  \u2502  ", style="dim #FFD700")
            text.append("No query history", style="dim italic")
            text.append(" " * 34, style="")
            text.append(" \u2502", style="dim #FFD700")
            text.append("\n")
        else:
            # Prev stack section
            if prev_display:
                # Stack header with count
                count_str = f"\u27e8{len(prev_display)}/{prev_total}\u27e9"
                header_text = "\u25c0 PREVIOUS (^)"
                header_padding = 50 - len(header_text) - len(count_str)
                text.append("  \u2502  ", style="dim #FFD700")
                text.append(header_text, style="bold #87D7FF")
                text.append(" " * header_padding, style="")
                text.append(count_str, style="dim #87D7FF")
                text.append(" \u2502", style="dim #FFD700")
                text.append("\n")

                # Dashed separator
                text.append("  \u2502  ", style="dim #FFD700")
                text.append("\u2504" * 50, style="dim #87D7FF")
                text.append(" \u2502", style="dim #FFD700")
                text.append("\n")

                for i, query in enumerate(prev_display):
                    is_first = i == 0
                    dim_level = 0 if i < 2 else (1 if i < 4 else 2)
                    self._add_history_entry(
                        text, query, is_first, "^", dim_level, "#FFD700"
                    )

                # Spacing after prev section if next section follows
                if next_display:
                    text.append("  \u2502", style="dim #FFD700")
                    text.append(" " * 52, style="")
                    text.append(" \u2502", style="dim #FFD700")
                    text.append("\n")

            # Next stack section
            if next_display:
                # Stack header with count
                count_str = f"\u27e8{len(next_display)}/{next_total}\u27e9"
                header_text = "\u25b6 NEXT (_)"
                header_padding = 50 - len(header_text) - len(count_str)
                text.append("  \u2502  ", style="dim #FFD700")
                text.append(header_text, style="bold #87D7FF")
                text.append(" " * header_padding, style="")
                text.append(count_str, style="dim #87D7FF")
                text.append(" \u2502", style="dim #FFD700")
                text.append("\n")

                # Dashed separator
                text.append("  \u2502  ", style="dim #FFD700")
                text.append("\u2504" * 50, style="dim #87D7FF")
                text.append(" \u2502", style="dim #FFD700")
                text.append("\n")

                for i, query in enumerate(next_display):
                    is_first = i == 0
                    dim_level = 0 if i < 2 else (1 if i < 4 else 2)
                    self._add_history_entry(
                        text, query, is_first, "_", dim_level, "#FFD700"
                    )

        # Section footer
        text.append("  \u2514", style="dim #FFD700")
        text.append("\u2500" * 53, style="dim #FFD700")
        text.append("\u2518", style="dim #FFD700")
        text.append("\n")

    def _add_history_entry(
        self,
        text: Text,
        query: str,
        is_first: bool,
        nav_key: str,
        dim_level: int,
        border_color: str,
    ) -> None:
        """Add a single history entry line.

        Args:
            text: The Text object to append to.
            query: The query string.
            is_first: Whether this is the first (most recent) entry in the stack.
            nav_key: The navigation key hint ("^" or "_").
            dim_level: Dimming level (0=bright, 1=slightly dim, 2=dim).
            border_color: Color for the border characters.
        """
        text.append("  \u2502  ", style=f"dim {border_color}")

        # Bullet indicator (green for first/has keymap, white for others)
        if is_first:
            text.append("\u25b8 ", style="bold #00FF00")
        else:
            text.append("\u25b8 ", style="white")

        # Query with syntax highlighting (truncated if needed)
        # Shorter max length for first entry to accommodate nav hint
        nav_hint = f" \u2190 {nav_key}" if is_first else ""
        nav_hint_len = len(nav_hint)
        max_query_len = 48 - nav_hint_len

        if len(query) > max_query_len:
            display_query = query[: max_query_len - 3] + "..."
        else:
            display_query = query

        # Apply dimming based on level
        if dim_level <= 1:
            # Full syntax highlighting for recent entries
            query_text = build_query_text(display_query)
            text.append_text(query_text)
        else:
            # Dim plain text for oldest entries
            text.append(display_query, style="dim #888888")

        # Nav hint for first entry
        if is_first:
            text.append(nav_hint, style="italic #888888")

        # Padding and right border
        padding = 48 - len(display_query) - nav_hint_len
        if padding > 0:
            text.append(" " * padding, style="")
        text.append(" \u2502", style=f"dim {border_color}")
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
