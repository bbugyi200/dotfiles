"""Tab bar widget for switching between views."""

from typing import Any, Literal

from rich.text import Text
from textual.events import Click
from textual.message import Message
from textual.widgets import Static

TabName = Literal["changespecs", "agents"]


class TabBar(Static):
    """Horizontal tab bar showing available tabs with selection indicator."""

    class TabClicked(Message):
        """Message sent when a tab is clicked."""

        def __init__(self, tab: TabName) -> None:
            super().__init__()
            self.tab = tab

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_tab: TabName = "changespecs"
        # Store positions for click detection
        self._cl_tab_range: tuple[int, int] = (0, 0)
        self._agents_tab_range: tuple[int, int] = (0, 0)

    def update_tab(self, tab: TabName) -> None:
        """Update the displayed active tab.

        Args:
            tab: The tab to mark as active.
        """
        self._current_tab = tab
        self._refresh_content()

    def _refresh_content(self) -> None:
        """Refresh the tab bar display."""
        text = Text()

        # CLs tab
        cl_start = 0
        if self._current_tab == "changespecs":
            text.append(" CLs ", style="bold reverse #00D7AF")
        else:
            text.append(" CLs ", style="dim")
        cl_end = len(text.plain)
        self._cl_tab_range = (cl_start, cl_end)

        text.append(" | ", style="dim #808080")

        # Agents tab
        agents_start = len(text.plain)
        if self._current_tab == "agents":
            text.append(" Agents ", style="bold reverse #87D7FF")
        else:
            text.append(" Agents ", style="dim")
        agents_end = len(text.plain)
        self._agents_tab_range = (agents_start, agents_end)

        # Add hint about TAB key
        text.append("   ", style="")
        text.append("[Tab]", style="dim italic")
        text.append(" switch", style="dim")

        # Only update if mounted (avoid errors in unit tests)
        if self.is_mounted:
            self.update(text)

    def on_mount(self) -> None:
        """Initialize display on mount."""
        self._refresh_content()

    def on_click(self, event: Click) -> None:
        """Handle click events to switch tabs."""
        # Get the x coordinate of the click
        x = event.x

        if self._cl_tab_range[0] <= x < self._cl_tab_range[1]:
            if self._current_tab != "changespecs":
                self.post_message(self.TabClicked("changespecs"))
        elif self._agents_tab_range[0] <= x < self._agents_tab_range[1]:
            if self._current_tab != "agents":
                self.post_message(self.TabClicked("agents"))
