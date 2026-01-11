"""Agent info panel widget for the ace TUI."""

from typing import Any

from rich.text import Text
from textual.widgets import Static


class AgentInfoPanel(Static):
    """Top bar showing agent count and auto-refresh countdown."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the info panel."""
        super().__init__(**kwargs)
        self._position = 0
        self._total = 0
        self._countdown = 0
        self._interval = 0

    def update_position(self, position: int, total: int) -> None:
        """Update the position display.

        Args:
            position: Current position (1-based for display).
            total: Total number of agents.
        """
        self._position = position
        self._total = total
        self._update_display()

    def update_countdown(self, countdown: int, interval: int) -> None:
        """Update the countdown display.

        Args:
            countdown: Seconds remaining until auto-refresh.
            interval: Total refresh interval in seconds.
        """
        self._countdown = countdown
        self._interval = interval
        self._update_display()

    def _update_display(self) -> None:
        """Refresh the displayed text."""
        text = Text()
        text.append("Agents: ", style="bold #87D7FF")
        text.append(f"{self._position}/{self._total}", style="#00D7AF")
        if self._interval > 0:
            text.append("   ", style="")
            text.append("(auto-refresh in ", style="dim")
            text.append(f"{self._countdown}s", style="bold #FFD700")
            text.append(")", style="dim")
        self.update(text)
