"""Axe control mixin for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from axe.process import (
    get_axe_status,
    is_axe_running,
    start_axe_daemon,
    stop_axe_daemon,
)
from axe.state import AxeMetrics, AxeStatus, read_metrics, read_output_log_tail

if TYPE_CHECKING:
    from ...changespec import ChangeSpec

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]


class AxeMixin:
    """Mixin providing axe daemon control and display methods."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    refresh_interval: int
    axe_running: bool
    _countdown_remaining: int
    _axe_status: AxeStatus | None
    _axe_metrics: AxeMetrics | None
    _axe_output: str

    def action_toggle_axe(self) -> None:
        """Toggle the axe daemon on or off."""
        if self.axe_running:
            self._stop_axe()
        else:
            self._start_axe()

    def action_stop_axe_and_quit(self) -> None:
        """Stop the axe daemon and quit the application."""
        if self.axe_running:
            self._stop_axe()
        self.exit()  # type: ignore[attr-defined]

    def _start_axe(self) -> None:
        """Start the axe daemon."""
        try:
            self._set_axe_starting(True)
            start_axe_daemon()
            self.notify("Starting axe scheduler...")  # type: ignore[attr-defined]
            # Give it a moment to initialize, then refresh
            self._load_axe_status()
        except Exception as e:
            self._set_axe_starting(False)
            self.notify(f"Failed to start axe: {e}", severity="error")  # type: ignore[attr-defined]

    def _stop_axe(self) -> None:
        """Stop the axe daemon."""
        try:
            if stop_axe_daemon():
                self.notify("Axe scheduler stopped")  # type: ignore[attr-defined]
            else:
                self.notify("Axe scheduler not running", severity="warning")  # type: ignore[attr-defined]
            self._load_axe_status()
        except Exception as e:
            self.notify(f"Failed to stop axe: {e}", severity="error")  # type: ignore[attr-defined]

    def _load_axe_status(self) -> None:
        """Load axe status from disk and update display."""
        # Check if axe is running
        self.axe_running = is_axe_running()

        # Clear starting state once confirmed running
        if self.axe_running:
            self._set_axe_starting(False)

        # Load status data
        if self.axe_running:
            status_dict = get_axe_status()
            if status_dict:
                try:
                    self._axe_status = AxeStatus(**status_dict)
                except TypeError:
                    self._axe_status = None
            else:
                self._axe_status = None
            self._axe_metrics = read_metrics()
        else:
            self._axe_status = None
            self._axe_metrics = None

        # Load output log (always, for display even when stopped)
        self._axe_output = read_output_log_tail(1000)

        # Update display if on axe tab
        if self.current_tab == "axe":
            self._refresh_axe_display()

        # Update keybinding footer for all tabs (X binding changes label)
        self._update_axe_keybinding()

    def _refresh_axe_display(self) -> None:
        """Refresh the axe dashboard display."""
        from ..widgets import AxeDashboard, AxeInfoPanel, KeybindingFooter

        try:
            axe_info = self.query_one("#axe-info-panel", AxeInfoPanel)  # type: ignore[attr-defined]
            axe_dashboard = self.query_one("#axe-dashboard", AxeDashboard)  # type: ignore[attr-defined]
            footer = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]

            axe_info.update_status(self.axe_running)
            axe_info.update_countdown(self._countdown_remaining, self.refresh_interval)

            # Get full cycles from metrics if available
            full_cycles = 0
            if self._axe_metrics:
                full_cycles = self._axe_metrics.full_cycles_run

            axe_dashboard.update_display(
                is_running=self.axe_running,
                status=self._axe_status,
                output=self._axe_output,
                full_cycles=full_cycles,
            )
            footer.set_axe_running(self.axe_running)
            footer.update_axe_bindings()
        except Exception:
            # Widget not found, possibly not on axe tab
            pass

    def _update_axe_info_panel(self) -> None:
        """Update the axe info panel with countdown."""
        from ..widgets import AxeInfoPanel

        try:
            axe_info = self.query_one("#axe-info-panel", AxeInfoPanel)  # type: ignore[attr-defined]
            axe_info.update_status(self.axe_running)
            axe_info.update_countdown(self._countdown_remaining, self.refresh_interval)
        except Exception:
            pass

    def _update_axe_keybinding(self) -> None:
        """Update the keybinding footer with current axe state."""
        from ..widgets import KeybindingFooter

        try:
            footer = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]
            footer.set_axe_running(self.axe_running)
        except Exception:
            pass

    def _set_axe_starting(self, starting: bool) -> None:
        """Set axe starting state and update footer.

        Args:
            starting: Whether axe is currently starting up.
        """
        from ..widgets import KeybindingFooter

        try:
            footer = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]
            footer.set_axe_starting(starting)
        except Exception:
            pass
