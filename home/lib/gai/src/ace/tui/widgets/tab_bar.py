"""Tab bar widget for switching between views."""

from typing import Any, Literal

from rich.text import Text
from textual.events import Click
from textual.message import Message
from textual.widgets import Static

TabName = Literal["changespecs", "agents", "axe"]


class TabBar(Static):
    """Horizontal tab bar showing available tabs with selection indicator."""

    class TabClicked(Message):
        """Message sent when a tab is clicked."""

        def __init__(self, tab: TabName) -> None:
            super().__init__()
            self.tab = tab

    def __init__(self, **kwargs: Any) -> None:
        self._current_tab: TabName = "changespecs"
        # Store positions for click detection
        self._cl_tab_range: tuple[int, int] = (0, 0)
        self._agents_tab_range: tuple[int, int] = (0, 0)
        self._axe_tab_range: tuple[int, int] = (0, 0)
        # Initialize with content so tabline shows immediately
        super().__init__(self._build_content(), **kwargs)

    def update_tab(self, tab: TabName) -> None:
        """Update the displayed active tab.

        Args:
            tab: The tab to mark as active.
        """
        self._current_tab = tab
        self._refresh_content()

    def _build_content(self) -> Text:
        """Build the tab bar content."""
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

        text.append(" | ", style="dim #808080")

        # Axe tab
        axe_start = len(text.plain)
        if self._current_tab == "axe":
            text.append(" AXE ", style="bold reverse #FF5F5F")
        else:
            text.append(" AXE ", style="dim")
        axe_end = len(text.plain)
        self._axe_tab_range = (axe_start, axe_end)

        return text

    def _refresh_content(self) -> None:
        """Refresh the tab bar display."""
        # Only update if mounted (avoid errors in unit tests)
        if self.is_mounted:
            self.update(self._build_content())

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
        elif self._axe_tab_range[0] <= x < self._axe_tab_range[1]:
            if self._current_tab != "axe":
                self.post_message(self.TabClicked("axe"))
