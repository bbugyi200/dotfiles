"""Axe control mixin for the ace TUI app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from axe.process import (
    get_axe_status,
    is_axe_running,
    start_axe_daemon,
    stop_axe_daemon,
)
from axe.state import (
    AxeMetrics,
    AxeStatus,
    clear_output_log,
    read_metrics,
    read_output_log_tail,
)
from running_field import get_workspace_directory

from ..bgcmd import (
    BackgroundCommandInfo,
    clear_slot,
    clear_slot_output,
    find_first_available_slot,
    get_active_slots,
    get_slot_info,
    is_slot_running,
    read_slot_output_tail,
    start_background_command,
    stop_background_command,
)

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..modals.project_select_modal import SelectionItem

# Type alias for tab names
TabName = Literal["changespecs", "agents", "axe"]

# Type alias for axe view: "axe" for daemon view, int for bgcmd slot (1-9)
AxeViewType = Literal["axe"] | int


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
    _axe_pinned_to_bottom: bool

    # Background command state
    _axe_current_view: AxeViewType
    _bgcmd_slots: list[tuple[int, BackgroundCommandInfo]]

    def action_toggle_axe(self) -> None:
        """Toggle the axe daemon on or off.

        When on AXE tab:
          - View 0 (axe): Toggle axe daemon
          - View 1-9 (bgcmd): Show confirm dialog to kill that bgcmd

        When on other tabs:
          - If axe not running and no bgcmd running: Start axe
          - If only axe running: Stop axe
          - If only bgcmd running: Show selector
          - If both running: Show selector
        """
        if self.current_tab == "axe":
            # On AXE tab, behavior depends on current view
            if self._axe_current_view == "axe":
                # Toggle axe daemon
                if self.axe_running:
                    self._stop_axe()
                else:
                    self._start_axe()
            else:
                # Current view is a bgcmd slot - kill or clear
                slot = self._axe_current_view
                self._confirm_kill_bgcmd(slot)
        else:
            # On other tabs - handle based on what's running
            bgcmd_active = len(self._bgcmd_slots) > 0

            if not self.axe_running and not bgcmd_active:
                # Nothing running - start axe
                self._start_axe()
            elif self.axe_running and not bgcmd_active:
                # Only axe running - stop it
                self._stop_axe()
            else:
                # Either only bgcmd or both running - show selector
                self._show_process_selector()

    def action_stop_axe_and_quit(self) -> None:
        """Stop the axe daemon and quit the application."""
        if self.axe_running:
            self._stop_axe()
        self.exit()  # type: ignore[attr-defined]

    def action_clear_axe_output(self) -> None:
        """Clear the output log for the current view."""
        if self.current_tab != "axe":
            return

        if self._axe_current_view == "axe":
            # Clear axe output
            clear_output_log()
            self._axe_output = ""
        else:
            # Clear bgcmd output
            slot = self._axe_current_view
            clear_slot_output(slot)

        self._refresh_axe_display()
        self.notify("Output cleared")  # type: ignore[attr-defined]

    def action_start_bgcmd(self) -> None:
        """Start the background command workflow (! key on all tabs)."""
        # Check for available slot
        slot = find_first_available_slot()
        if slot is None:
            self.notify("All 9 background command slots are in use", severity="error")  # type: ignore[attr-defined]
            return

        # Show project select modal
        from ..modals import ProjectSelectModal

        def on_project_selected(
            result: SelectionItem | str | None,
        ) -> None:
            if result is None:
                return

            # Extract project name
            if isinstance(result, str):
                project = result
            else:
                project = result.project_name

            # Show workspace input modal
            self._show_workspace_input(slot, project)

        self.push_screen(ProjectSelectModal(), on_project_selected)  # type: ignore[attr-defined]

    def _show_workspace_input(self, slot: int, project: str) -> None:
        """Show the workspace input modal.

        Args:
            slot: Slot number to use.
            project: Project name.
        """
        from ..modals import WorkspaceInputModal

        def on_workspace_entered(workspace_num: int | None) -> None:
            if workspace_num is None:
                return
            self._show_command_input(slot, project, workspace_num)

        self.push_screen(WorkspaceInputModal(), on_workspace_entered)  # type: ignore[attr-defined]

    def _show_command_input(self, slot: int, project: str, workspace_num: int) -> None:
        """Show the command input modal.

        Args:
            slot: Slot number to use.
            project: Project name.
            workspace_num: Workspace number.
        """
        from ..modals import CommandInputModal

        def on_command_entered(command: str | None) -> None:
            if command is None:
                return
            self._start_bgcmd(slot, command, project, workspace_num)

        self.push_screen(CommandInputModal(project, workspace_num), on_command_entered)  # type: ignore[attr-defined]

    def _start_bgcmd(
        self, slot: int, command: str, project: str, workspace_num: int
    ) -> None:
        """Start a background command.

        Args:
            slot: Slot number (1-9).
            command: Shell command to run.
            project: Project name.
            workspace_num: Workspace number.
        """
        try:
            workspace_dir = get_workspace_directory(project, workspace_num)
        except RuntimeError as e:
            self.notify(f"Failed to get workspace: {e}", severity="error")  # type: ignore[attr-defined]
            return

        pid = start_background_command(
            slot=slot,
            command=command,
            project=project,
            workspace_num=workspace_num,
            workspace_dir=workspace_dir,
        )

        if pid is None:
            self.notify("Failed to start background command", severity="error")  # type: ignore[attr-defined]
            return

        # Reload state and switch to the new view
        self._load_bgcmd_state()
        self._switch_to_axe_view(slot)
        self.notify(f"Started command in slot {slot}")  # type: ignore[attr-defined]

    def _confirm_kill_bgcmd(self, slot: int) -> None:
        """Kill or clear a background command.

        For running commands: Show confirmation dialog before killing.
        For done commands: Clear immediately without confirmation.

        Args:
            slot: Slot number to kill/clear.
        """
        info = get_slot_info(slot)
        if info is None:
            return

        # Check if the command is still running
        if not is_slot_running(slot):
            # Done command - clear immediately without confirmation
            clear_slot(slot)
            self.notify(f"Cleared slot {slot}")  # type: ignore[attr-defined]
            self._load_bgcmd_state()
            # If no more bgcmds, switch to axe view
            if len(self._bgcmd_slots) == 0:
                self._switch_to_axe_view("axe")
            return

        # Running command - show confirmation dialog
        from ..modals import ConfirmKillModal

        description = f"Slot {slot}: {info.command}\n({info.project}, workspace {info.workspace_num})"

        def on_confirmed(confirmed: bool) -> None:
            if confirmed:
                stop_background_command(slot)
                clear_slot(slot)
                self.notify(f"Stopped and cleared slot {slot}")  # type: ignore[attr-defined]
                self._load_bgcmd_state()
                # If no more bgcmds, switch to axe view
                if len(self._bgcmd_slots) == 0:
                    self._switch_to_axe_view("axe")

        self.push_screen(ConfirmKillModal(description), on_confirmed)  # type: ignore[attr-defined]

    def _show_process_selector(self) -> None:
        """Show the process selector modal (for X on non-AXE tabs)."""
        from ..modals import ProcessSelection, ProcessSelectModal

        def on_selected(selection: ProcessSelection | None) -> None:
            if selection is None:
                return

            if selection.process_type == "start_axe":
                self._start_axe()
            elif selection.process_type == "axe":
                self._stop_axe()
            elif selection.process_type == "dismiss_bgcmd":
                # Done command - just clear it
                slot = selection.slot
                if slot is not None:
                    clear_slot(slot)
                    self.notify(f"Cleared slot {slot}")  # type: ignore[attr-defined]
                    self._load_bgcmd_state()
            else:  # bgcmd (running)
                slot = selection.slot
                if slot is not None:
                    stop_background_command(slot)
                    clear_slot(slot)
                    self.notify(f"Stopped and cleared slot {slot}")  # type: ignore[attr-defined]
                    self._load_bgcmd_state()

        self.push_screen(  # type: ignore[attr-defined]
            ProcessSelectModal(self.axe_running, self._bgcmd_slots),
            on_selected,
        )

    def _switch_to_axe_view(self, view: AxeViewType) -> None:
        """Switch to a different axe view.

        Args:
            view: The view to switch to ("axe" or slot number).
        """
        self._axe_current_view = view
        self._refresh_axe_display()

    def _start_axe(self) -> None:
        """Start the axe daemon."""
        try:
            self._set_axe_starting(True)
            start_axe_daemon()
            self._load_axe_status()
        except Exception as e:
            self._set_axe_starting(False)
            self.notify(f"Failed to start axe: {e}", severity="error")  # type: ignore[attr-defined]

    def _stop_axe(self) -> None:
        """Stop the axe daemon."""
        try:
            self._set_axe_stopping(True)
            stop_axe_daemon()
            self._load_axe_status()
        except Exception as e:
            self._set_axe_stopping(False)
            self.notify(f"Failed to stop axe: {e}", severity="error")  # type: ignore[attr-defined]

    def _load_axe_status(self) -> None:
        """Load axe status from disk and update display."""
        # Check if axe is running
        self.axe_running = is_axe_running()

        # Clear starting state once confirmed running
        if self.axe_running:
            self._set_axe_starting(False)

        # Clear stopping state once confirmed stopped
        if not self.axe_running:
            self._set_axe_stopping(False)

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

        # Also load bgcmd state
        self._load_bgcmd_state()

        # Update display if on axe tab
        if self.current_tab == "axe":
            self._refresh_axe_display()

        # Update keybinding footer for all tabs (X binding changes label)
        self._update_axe_keybinding()

    def _load_bgcmd_state(self) -> None:
        """Load background command state from disk (running + done commands)."""
        active_slots = get_active_slots()
        self._bgcmd_slots = []

        for slot in active_slots:
            info = get_slot_info(slot)
            if info is not None:
                self._bgcmd_slots.append((slot, info))

        # Update footer with bgcmd count
        self._update_bgcmd_count()

        # Update AXE tab layout if needed
        if self.current_tab == "axe":
            self._update_axe_layout()

    def _update_bgcmd_count(self) -> None:
        """Update the keybinding footer with bgcmd count."""
        from ..widgets import KeybindingFooter

        try:
            footer = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]
            footer.set_bgcmd_count(len(self._bgcmd_slots))
        except Exception:
            pass

    def _update_axe_layout(self) -> None:
        """Update AXE tab layout based on whether bgcmds are running."""
        try:
            bgcmd_list_container = self.query_one("#bgcmd-list-container")  # type: ignore[attr-defined]
            has_bgcmds = len(self._bgcmd_slots) > 0

            if has_bgcmds:
                bgcmd_list_container.remove_class("hidden")
            else:
                bgcmd_list_container.add_class("hidden")
                # If current view is a bgcmd that's no longer running, switch to axe
                if self._axe_current_view != "axe":
                    self._axe_current_view = "axe"
        except Exception:
            pass

    def _refresh_axe_display(self) -> None:
        """Refresh the axe dashboard display."""
        from textual.containers import VerticalScroll

        from ..widgets import AxeDashboard, AxeInfoPanel, BgCmdList, KeybindingFooter

        try:
            axe_info = self.query_one("#axe-info-panel", AxeInfoPanel)  # type: ignore[attr-defined]
            axe_dashboard = self.query_one("#axe-dashboard", AxeDashboard)  # type: ignore[attr-defined]
            footer = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]

            # Update countdown
            axe_info.update_countdown(self._countdown_remaining, self.refresh_interval)

            # Update info panel based on current view
            if self._axe_current_view == "axe":
                axe_info.update_status(self.axe_running)

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
            else:
                # Showing a bgcmd view
                slot = self._axe_current_view
                info = get_slot_info(slot)
                running = is_slot_running(slot)
                output = read_slot_output_tail(slot, 1000)

                axe_info.update_bgcmd_status(slot, info, running)
                axe_dashboard.update_bgcmd_display(info, output, running)

            footer.set_axe_running(self.axe_running)
            footer.set_bgcmd_count(len(self._bgcmd_slots))
            footer.update_axe_bindings()

            # Update bgcmd list if visible
            if len(self._bgcmd_slots) > 0:
                try:
                    bgcmd_list = self.query_one("#bgcmd-list-panel", BgCmdList)  # type: ignore[attr-defined]
                    bgcmd_list.update_list(
                        axe_running=self.axe_running,
                        bgcmd_slots=self._bgcmd_slots,
                        current_item=self._axe_current_view,
                    )
                except Exception:
                    pass

            # Auto-scroll to bottom if pinned and on axe view
            if self._axe_pinned_to_bottom and self._axe_current_view == "axe":
                scroll_container = self.query_one("#axe-output-scroll", VerticalScroll)  # type: ignore[attr-defined]
                scroll_container.scroll_end(animate=False)
        except Exception:
            # Widget not found, possibly not on axe tab
            pass

    def _update_axe_info_panel(self) -> None:
        """Update the axe info panel with countdown."""
        from ..widgets import AxeInfoPanel

        try:
            axe_info = self.query_one("#axe-info-panel", AxeInfoPanel)  # type: ignore[attr-defined]
            if self._axe_current_view == "axe":
                axe_info.update_status(self.axe_running)
            else:
                slot = self._axe_current_view
                info = get_slot_info(slot)
                running = is_slot_running(slot)
                axe_info.update_bgcmd_status(slot, info, running)
            axe_info.update_countdown(self._countdown_remaining, self.refresh_interval)
        except Exception:
            pass

    def _update_axe_keybinding(self) -> None:
        """Update the keybinding footer with current axe state."""
        from ..widgets import KeybindingFooter

        try:
            footer = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]
            footer.set_axe_running(self.axe_running)
            footer.set_bgcmd_count(len(self._bgcmd_slots))
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

    def _set_axe_stopping(self, stopping: bool) -> None:
        """Set axe stopping state and update footer.

        Args:
            stopping: Whether axe is currently stopping.
        """
        from ..widgets import KeybindingFooter

        try:
            footer = self.query_one("#keybinding-footer", KeybindingFooter)  # type: ignore[attr-defined]
            footer.set_axe_stopping(stopping)
        except Exception:
            pass
