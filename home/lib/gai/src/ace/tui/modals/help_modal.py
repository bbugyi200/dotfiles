"""Beautiful help modal for the ace TUI."""

from typing import TYPE_CHECKING, Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

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


class HelpModal(ModalScreen[None]):
    """Beautiful help modal showing all keybindings and saved queries."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
        ("question_mark", "close", "Close"),
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
                yield Static(self._build_content(), id="help-content")
            yield Static(
                "Press ? / q / Esc to close",
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

    def _build_content(self) -> Text:
        """Build the main content with keybinding sections."""
        text = Text()

        # Get bindings for current tab
        bindings = self._get_bindings_for_tab()

        for section_name, section_bindings in bindings:
            self._add_section(text, section_name, section_bindings)

        # Add saved queries section for CLs tab
        if self._current_tab == "changespecs":
            self._add_saved_queries_section(text)

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
        text.append("\u2500" * 54, style="dim #87D7FF")
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
            text.append(" " * 38, style="")
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
                        padding = max_query_len - len(display_query) - 8
                        if padding > 0:
                            text.append(" " * padding, style="")
                        text.append(" \u25cf active", style="bold #00FF00")
                    else:
                        padding = max_query_len - len(display_query) + 1
                        if padding > 0:
                            text.append(" " * padding, style="")

                    text.append(" \u2502", style="dim #FFD700")
                    text.append("\n")

        # Section footer
        text.append("  \u2514", style="dim #FFD700")
        text.append("\u2500" * 54, style="dim #FFD700")
        text.append("\u2518", style="dim #FFD700")
        text.append("\n")

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(None)
