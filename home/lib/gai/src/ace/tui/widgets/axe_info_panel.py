"""Axe info panel widget for the ace TUI."""

from typing import Any

from rich.text import Text
from textual.widgets import Static


class AxeInfoPanel(Static):
    """Top bar showing axe running status and auto-refresh countdown."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the info panel."""
        super().__init__(**kwargs)
        self._is_running = False
        self._countdown = 0
        self._interval = 0

    def update_status(self, is_running: bool) -> None:
        """Update the running status display.

        Args:
            is_running: Whether axe daemon is currently running.
        """
        self._is_running = is_running
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
        text.append("Axe: ", style="bold #FF5F5F")
        if self._is_running:
            text.append("RUNNING", style="bold #00D787")
        else:
            text.append("STOPPED", style="bold #FF5F5F")
        if self._interval > 0:
            text.append("   ", style="")
            text.append("(auto-refresh in ", style="dim")
            text.append(f"{self._countdown}s", style="bold #FFD700")
            text.append(")", style="dim")
        self.update(text)
