"""Axe dashboard widget for the ace TUI."""

from typing import Any

from axe.state import AxeMetrics, AxeStatus
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static


class _AxeStatusSection(Static):
    """Section showing axe running status, PID, and uptime."""

    def update_display(self, status: AxeStatus | None, is_running: bool) -> None:
        """Update the status section.

        Args:
            status: Current axe status, or None if not available.
            is_running: Whether axe daemon is currently running.
        """
        text = Text()
        text.append("STATUS\n", style="bold #D7AF5F underline")
        text.append("\n")

        if not is_running:
            text.append("Status:  ", style="bold #87D7FF")
            text.append("STOPPED", style="bold #FF5F5F")
            text.append("\n\n")
            text.append("Axe scheduler is not running.\n", style="dim italic")
            text.append("Press ", style="dim")
            text.append("X", style="bold #FFD700")
            text.append(" to start the axe scheduler.", style="dim")
            self.update(text)
            return

        text.append("Status:  ", style="bold #87D7FF")
        text.append("RUNNING", style="bold #00D787")

        if status:
            text.append("                  ", style="")
            text.append("PID: ", style="bold #87D7FF")
            text.append(f"{status.pid}\n", style="#FF87D7 bold")

            # Uptime
            uptime_str = _format_uptime(status.uptime_seconds)
            text.append("Uptime:  ", style="bold #87D7FF")
            text.append(f"{uptime_str}\n", style="#00D7AF")

            # Started at
            text.append("Started: ", style="bold #87D7FF")
            started_display = _format_timestamp(status.started_at)
            text.append(f"{started_display}\n", style="#5FD7FF")
        else:
            text.append("\n")
            text.append("Initializing...\n", style="dim italic")

        self.update(text)


class _AxeConfigSection(Static):
    """Section showing axe configuration."""

    def update_display(self, status: AxeStatus | None) -> None:
        """Update the configuration section.

        Args:
            status: Current axe status, or None if not available.
        """
        text = Text()
        text.append("CONFIGURATION\n", style="bold #D7AF5F underline")
        text.append("\n")

        if not status:
            text.append("No configuration data available.\n", style="dim italic")
            self.update(text)
            return

        # Row 1: Intervals
        text.append("Full Check Interval:  ", style="bold #87D7FF")
        text.append(f"{status.full_check_interval}s", style="#00D7AF")
        text.append("      ", style="")
        text.append("Hook Interval: ", style="bold #87D7FF")
        text.append(f"{status.hook_interval}s\n", style="#00D7AF")

        # Row 2: Runners and timeout
        text.append("Max Runners:          ", style="bold #87D7FF")
        text.append(f"{status.max_runners}", style="#00D7AF")
        text.append("         ", style="")
        text.append("Zombie Timeout: ", style="bold #87D7FF")
        text.append(f"{status.zombie_timeout}s\n", style="#00D7AF")

        # Row 3: Current runners and changespecs
        text.append("Current Runners:      ", style="bold #87D7FF")
        text.append(f"{status.current_runners}", style="#FF87D7 bold")
        text.append("         ", style="")
        text.append("Changespecs: ", style="bold #87D7FF")
        text.append(f"{status.filtered_changespecs}", style="#00D7AF")
        text.append("/", style="dim")
        text.append(f"{status.total_changespecs}\n", style="#00D7AF")

        # Row 4: Query
        if status.query:
            text.append("Query:                ", style="bold #87D7FF")
            query_display = (
                status.query if len(status.query) <= 50 else status.query[:47] + "..."
            )
            text.append(f'"{query_display}"\n', style="#AF87D7")

        self.update(text)


class _AxeMetricsSection(Static):
    """Section showing axe metrics."""

    def update_display(self, metrics: AxeMetrics | None) -> None:
        """Update the metrics section.

        Args:
            metrics: Current axe metrics, or None if not available.
        """
        text = Text()
        text.append("METRICS\n", style="bold #D7AF5F underline")
        text.append("\n")

        if not metrics:
            text.append("No metrics data available.\n", style="dim italic")
            self.update(text)
            return

        # Row 1: Cycle counts
        text.append("Full Cycles:  ", style="bold #87D7FF")
        text.append(f"{metrics.full_cycles_run:,}", style="#00D7AF bold")
        text.append("        ", style="")
        text.append("Hook Cycles: ", style="bold #87D7FF")
        text.append(f"{metrics.hook_cycles_run:,}\n", style="#00D7AF bold")

        # Row 2: Started/Completed pairs
        text.append("Hooks:        ", style="bold #87D7FF")
        text.append(f"{metrics.hooks_started}", style="#00D7AF")
        text.append("/", style="dim")
        text.append(f"{metrics.hooks_completed}", style="#00D7AF")
        text.append("         ", style="")
        text.append("Mentors: ", style="bold #87D7FF")
        text.append(f"{metrics.mentors_started}", style="#00D7AF")
        text.append("/", style="dim")
        text.append(f"{metrics.mentors_completed}\n", style="#00D7AF")

        # Row 3: Workflows and zombies
        text.append("Workflows:    ", style="bold #87D7FF")
        text.append(f"{metrics.workflows_started}", style="#00D7AF")
        text.append("/", style="dim")
        text.append(f"{metrics.workflows_completed}", style="#00D7AF")
        text.append("         ", style="")
        text.append("Zombies: ", style="bold #87D7FF")
        if metrics.zombies_detected > 0:
            text.append(f"{metrics.zombies_detected}\n", style="#FF8787 bold")
        else:
            text.append("0\n", style="#00D7AF")

        # Row 4: Updates and errors
        text.append("Total Updates: ", style="bold #87D7FF")
        text.append(f"{metrics.total_updates:,}", style="#00D7AF bold")
        text.append("       ", style="")
        text.append("Errors: ", style="bold #87D7FF")
        if metrics.errors_encountered > 0:
            text.append(f"{metrics.errors_encountered}\n", style="#FF8787 bold")
        else:
            text.append("0\n", style="#00D7AF")

        self.update(text)


class _AxeErrorsSection(Static):
    """Section showing recent errors."""

    def update_display(self, errors: list[dict]) -> None:
        """Update the errors section.

        Args:
            errors: List of recent error dictionaries.
        """
        text = Text()
        text.append(f"RECENT ERRORS ({len(errors)})\n", style="bold #D7AF5F underline")
        text.append("\n")

        if not errors:
            text.append("No recent errors.\n", style="dim italic")
            self.update(text)
            return

        # Show last 10 errors (most recent first)
        for error_dict in reversed(errors[-10:]):
            timestamp = error_dict.get("timestamp", "")
            # Extract just time portion from ISO timestamp
            time_display = _format_time_from_iso(timestamp)
            job = error_dict.get("job", "unknown")
            error_msg = error_dict.get("error", "Unknown error")

            text.append(f"[{time_display}] ", style="#87D7FF")
            text.append(f"{job}: ", style="bold #FF8787")
            # Truncate long error messages
            if len(error_msg) > 60:
                error_msg = error_msg[:57] + "..."
            text.append(f"{error_msg}\n", style="#FF8787")

        self.update(text)


class AxeDashboard(Static):
    """Main dashboard widget combining all axe status sections."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the dashboard."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Compose the dashboard sections."""
        yield _AxeStatusSection(id="axe-status-section", classes="axe-section")
        yield _AxeConfigSection(id="axe-config-section", classes="axe-section")
        yield _AxeMetricsSection(id="axe-metrics-section", classes="axe-section")
        with VerticalScroll(id="axe-errors-scroll"):
            yield _AxeErrorsSection(id="axe-errors-section", classes="axe-section")

    def update_display(
        self,
        is_running: bool,
        status: AxeStatus | None,
        metrics: AxeMetrics | None,
        errors: list[dict],
    ) -> None:
        """Update all dashboard sections with current data.

        Args:
            is_running: Whether axe daemon is currently running.
            status: Current axe status, or None if not available.
            metrics: Current axe metrics, or None if not available.
            errors: List of recent error dictionaries.
        """
        status_section = self.query_one("#axe-status-section", _AxeStatusSection)
        config_section = self.query_one("#axe-config-section", _AxeConfigSection)
        metrics_section = self.query_one("#axe-metrics-section", _AxeMetricsSection)
        errors_section = self.query_one("#axe-errors-section", _AxeErrorsSection)

        status_section.update_display(status, is_running)
        config_section.update_display(status)
        metrics_section.update_display(metrics)
        errors_section.update_display(errors)

    def show_empty(self) -> None:
        """Show empty/stopped state."""
        self.update_display(
            is_running=False,
            status=None,
            metrics=None,
            errors=[],
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


def _format_timestamp(iso_timestamp: str) -> str:
    """Format ISO timestamp for display.

    Args:
        iso_timestamp: ISO format timestamp string.

    Returns:
        Formatted string like "2024-01-14 10:30:45 EST".
    """
    # Parse and format the timestamp
    # Input format: 2025-01-15T10:00:00-05:00
    try:
        # Just clean up the format for display
        if "T" in iso_timestamp:
            date_part, time_part = iso_timestamp.split("T")
            # Remove timezone offset for cleaner display
            if "+" in time_part:
                time_part = time_part.split("+")[0]
            elif time_part.count("-") > 0:
                # Handle negative offset
                parts = time_part.rsplit("-", 1)
                if len(parts) == 2 and ":" in parts[1]:
                    time_part = parts[0]
            return f"{date_part} {time_part}"
        return iso_timestamp
    except Exception:
        return iso_timestamp


def _format_time_from_iso(iso_timestamp: str) -> str:
    """Extract just the time portion from an ISO timestamp.

    Args:
        iso_timestamp: ISO format timestamp string.

    Returns:
        Time portion like "10:30:45".
    """
    try:
        if "T" in iso_timestamp:
            time_part = iso_timestamp.split("T")[1]
            # Remove timezone offset
            if "+" in time_part:
                time_part = time_part.split("+")[0]
            elif time_part.count("-") > 0:
                parts = time_part.rsplit("-", 1)
                if len(parts) == 2 and ":" in parts[1]:
                    time_part = parts[0]
            # Return just HH:MM:SS
            return time_part.split(".")[0]
        return iso_timestamp
    except Exception:
        return iso_timestamp
