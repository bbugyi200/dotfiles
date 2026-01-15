"""Axe dashboard widget for the ace TUI."""

from typing import Any

from axe.state import AxeStatus
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static


class _AxeStatusSection(Static):
    """Compact status bar showing PID, uptime, and cycles."""

    def update_display(
        self, status: AxeStatus | None, is_running: bool, full_cycles: int
    ) -> None:
        """Update the compact status section.

        Args:
            status: Current axe status, or None if not available.
            is_running: Whether axe daemon is currently running.
            full_cycles: Number of full cycles run.
        """
        text = Text()

        if status and is_running:
            # PID
            text.append("PID: ", style="bold #87D7FF")
            text.append(f"{status.pid}", style="#FF87D7 bold")

            # Uptime
            text.append("  │  ", style="dim")
            text.append("Uptime: ", style="bold #87D7FF")
            uptime_str = _format_uptime(status.uptime_seconds)
            text.append(f"{uptime_str}", style="#00D7AF")

            # Cycles
            text.append("  │  ", style="dim")
            text.append("Cycles: ", style="bold #87D7FF")
            text.append(f"{full_cycles}", style="#00D7AF bold")

        self.update(text)


class _AxeOutputSection(Static):
    """Section showing live axe output log."""

    def update_display(self, output: str) -> None:
        """Update the output section with log content.

        Args:
            output: Raw output with ANSI codes.
        """
        if not output:
            text = Text("No output yet. Start axe with ", style="dim italic")
            text.append("X", style="bold #FFD700")
            text.append(" to see live output.", style="dim italic")
            self.update(text)
            return

        # Convert ANSI codes to Rich Text for proper rendering
        text = Text.from_ansi(output)
        self.update(text)


class AxeDashboard(Static):
    """Main dashboard widget combining status bar and output log."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the dashboard."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose the dashboard sections."""
        yield _AxeStatusSection(id="axe-status-section")
        with VerticalScroll(id="axe-output-scroll"):
            yield _AxeOutputSection(id="axe-output-section")

    def update_display(
        self,
        is_running: bool,
        status: AxeStatus | None,
        output: str,
        full_cycles: int = 0,
    ) -> None:
        """Update all dashboard sections with current data.

        Args:
            is_running: Whether axe daemon is currently running.
            status: Current axe status, or None if not available.
            output: Raw output log with ANSI codes.
            full_cycles: Number of full cycles run.
        """
        status_section = self.query_one("#axe-status-section", _AxeStatusSection)
        output_section = self.query_one("#axe-output-section", _AxeOutputSection)

        status_section.update_display(status, is_running, full_cycles)
        output_section.update_display(output)

    def show_empty(self) -> None:
        """Show empty/stopped state."""
        self.update_display(
            is_running=False,
            status=None,
            output="",
            full_cycles=0,
        )


def _format_uptime(seconds: int) -> str:
    """Format uptime seconds into human-readable string.

    Args:
        seconds: Total uptime in seconds.

    Returns:
        Formatted string like "2h 34m 12s".
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)
