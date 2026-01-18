"""Axe info panel widget for the ace TUI."""

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.widgets import Static

if TYPE_CHECKING:
    from ..bgcmd import BackgroundCommandInfo


class AxeInfoPanel(Static):
    """Top bar showing axe running status and auto-refresh countdown."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the info panel."""
        super().__init__(**kwargs)
        self._is_running = False
        self._countdown = 0
        self._interval = 0
        self._bgcmd_mode = False
        self._bgcmd_slot: int | None = None
        self._bgcmd_info: BackgroundCommandInfo | None = None
        self._bgcmd_running = False

    def update_status(self, is_running: bool) -> None:
        """Update the running status display for axe daemon.

        Args:
            is_running: Whether axe daemon is currently running.
        """
        self._is_running = is_running
        self._bgcmd_mode = False
        self._update_display()

    def update_bgcmd_status(
        self,
        slot: int,
        info: "BackgroundCommandInfo | None",
        is_running: bool,
    ) -> None:
        """Update the status display for a background command.

        Args:
            slot: Slot number (1-9).
            info: Background command info.
            is_running: Whether the command is still running.
        """
        self._bgcmd_mode = True
        self._bgcmd_slot = slot
        self._bgcmd_info = info
        self._bgcmd_running = is_running
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

        if self._bgcmd_mode:
            # Show bgcmd info (just project name)
            if self._bgcmd_info:
                text.append(self._bgcmd_info.project, style="#87D7FF")
            text.append("  ", style="")
        else:
            # Show axe info (just the countdown for now)
            pass

        if self._interval > 0:
            text.append("(auto-refresh in ", style="dim")
            text.append(f"{self._countdown}s", style="bold #FFD700")
            text.append(")", style="dim")

        self.update(text)
