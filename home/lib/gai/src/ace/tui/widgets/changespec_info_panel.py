"""ChangeSpec info panel showing count and refresh countdown."""

from typing import Any

from rich.text import Text
from textual.widgets import Static


class ChangeSpecInfoPanel(Static):
    """Panel showing ChangeSpec position and auto-refresh countdown."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_position: int = 0  # 1-based position
        self._total_count: int = 0
        self._seconds_remaining: int = 0
        self._refresh_interval: int = 0

    def update_position(self, position: int, total: int) -> None:
        """Update the current position and total count.

        Args:
            position: 1-based position (e.g., 2 means viewing #2)
            total: Total number of filtered changespecs
        """
        self._current_position = position
        self._total_count = total
        self._refresh_content()

    def update_countdown(self, remaining: int, interval: int) -> None:
        """Update the countdown timer.

        Args:
            remaining: Seconds remaining until refresh
            interval: Total refresh interval in seconds
        """
        self._seconds_remaining = remaining
        self._refresh_interval = interval
        self._refresh_content()

    def _refresh_content(self) -> None:
        """Refresh the panel content."""
        text = Text()
        text.append("ChangeSpec: ", style="bold")
        text.append(f"{self._current_position}/{self._total_count}", style="#00D7AF")

        if self._refresh_interval > 0:
            text.append("   (auto-refresh in ", style="dim")
            text.append(f"{self._seconds_remaining}s", style="#87AFFF")
            text.append(")", style="dim")

        self.update(text)
