"""Axe dashboard widget for the ace TUI."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from axe.state import AxeStatus
from gai_utils import EASTERN_TZ
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

if TYPE_CHECKING:
    from ..bgcmd import BackgroundCommandInfo


class _AxeStatusSection(Static):
    """Compact status bar showing runtime, PID, cycles, CLs, and runners."""

    def update_display(
        self, status: AxeStatus | None, is_running: bool, full_cycles: int
    ) -> None:
        """Update the compact status section for axe daemon.

        Args:
            status: Current axe status, or None if not available.
            is_running: Whether axe daemon is currently running.
            full_cycles: Number of full cycles run.
        """
        text = Text()

        if is_running:
            # Runtime (always show when running)
            text.append("Runtime: ", style="bold #87D7FF")
            if status and status.started_at:
                runtime_str = _format_runtime(status.started_at)
            else:
                runtime_str = "..."
            text.append(runtime_str, style="#00D7AF")

            # PID
            text.append("  │  ", style="dim")
            text.append("PID: ", style="bold #87D7FF")
            if status:
                text.append(f"{status.pid}", style="#FF87D7 bold")
            else:
                text.append("...", style="#FF87D7 bold")

            # Cycles
            text.append("  │  ", style="dim")
            text.append("Cycles: ", style="bold #87D7FF")
            text.append(f"{full_cycles}", style="#00D7AF bold")

            # CLs (filtered changespecs)
            if status:
                text.append("  │  ", style="dim")
                text.append("CLs: ", style="bold #87D7FF")
                text.append(f"{status.filtered_changespecs}", style="#00D7AF")

            # Runners (current/max)
            if status:
                text.append("  │  ", style="dim")
                text.append("Runners: ", style="bold #87D7FF")
                text.append(
                    f"{status.current_runners}/{status.max_runners}", style="#00D7AF"
                )

        self.update(text)

    def update_bgcmd_display(
        self, info: "BackgroundCommandInfo | None", is_running: bool
    ) -> None:
        """Update the status section for a background command.

        Args:
            info: Background command info, or None if not available.
            is_running: Whether the command is still running.
        """
        text = Text()

        if info:
            # Status indicator
            if is_running:
                text.append("[RUNNING]", style="bold green")
            else:
                text.append("[STOPPED]", style="bold red")

            # Command
            text.append("  │  ", style="dim")
            text.append("Cmd: ", style="bold #87D7FF")
            cmd_display = info.command
            if len(cmd_display) > 40:
                cmd_display = cmd_display[:37] + "..."
            text.append(cmd_display, style="#FF87D7")

            # Project
            text.append("  │  ", style="dim")
            text.append("Project: ", style="bold #87D7FF")
            text.append(info.project, style="#00D7AF")

            # Workspace
            text.append("  │  ", style="dim")
            text.append("WS: ", style="bold #87D7FF")
            text.append(f"{info.workspace_num}", style="#00D7AF")

            # Runtime
            text.append("  │  ", style="dim")
            text.append("Runtime: ", style="bold #87D7FF")
            runtime_str = _format_runtime(info.started_at)
            text.append(runtime_str, style="#00D7AF")

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

    def update_bgcmd_display(
        self,
        info: "BackgroundCommandInfo | None",
        output: str,
        is_running: bool,
    ) -> None:
        """Update the dashboard to show background command info and output.

        Args:
            info: Background command info.
            output: Raw output log with ANSI codes.
            is_running: Whether the command is still running.
        """
        status_section = self.query_one("#axe-status-section", _AxeStatusSection)
        output_section = self.query_one("#axe-output-section", _AxeOutputSection)

        status_section.update_bgcmd_display(info, is_running)

        # Update output section
        if not output:
            text = Text()
            if is_running:
                text.append("Waiting for output...", style="dim italic")
            else:
                text.append("No output.", style="dim italic")
            output_section.update(text)
        else:
            # Convert ANSI codes to Rich Text for proper rendering
            text = Text.from_ansi(output)
            output_section.update(text)


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


def _format_runtime(started_at: str) -> str:
    """Format runtime from ISO timestamp to human-readable string.

    Args:
        started_at: ISO format timestamp string.

    Returns:
        Formatted string like "2h 34m 12s".
    """
    try:
        start_time = datetime.fromisoformat(started_at)
        now = datetime.now(EASTERN_TZ)
        elapsed = now - start_time
        return _format_uptime(int(elapsed.total_seconds()))
    except (ValueError, TypeError):
        return "unknown"
