"""Hook editing methods for the ace TUI app."""

from __future__ import annotations

from ....changespec import ChangeSpec
from ....hint_types import EditHooksResult
from ....hooks import get_failed_hooks_file_path
from ...widgets import ChangeSpecDetail, HintInputBar
from ._types import HintMixinBase


class HookEditingMixin(HintMixinBase):
    """Mixin providing hook editing actions."""

    def action_edit_hooks(self) -> None:
        """Edit hooks for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Re-render detail with hints for hooks_latest_only
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)  # type: ignore[attr-defined]
        query_str = self.canonical_query_string  # type: ignore[attr-defined]
        hint_mappings, hook_hint_to_idx, hint_to_entry_id = (
            detail_widget.update_display_with_hints(
                changespec,
                query_str,
                hints_for="hooks_latest_only",
                hooks_collapsed=self.hooks_collapsed,  # type: ignore[attr-defined]
                commits_collapsed=self.commits_collapsed,  # type: ignore[attr-defined]
                mentors_collapsed=self.mentors_collapsed,  # type: ignore[attr-defined]
            )
        )

        # Store state for later processing
        self._hint_mode_active = True
        self._hint_mode_hints_for = "hooks_latest_only"
        self._hint_mappings = hint_mappings
        self._hook_hint_to_idx = hook_hint_to_idx
        self._hint_to_entry_id = hint_to_entry_id
        self._hint_changespec_name = changespec.name

        # Mount the hint input bar
        detail_container = self.query_one("#detail-container")  # type: ignore[attr-defined]
        hint_bar = HintInputBar(mode="hooks", id="hint-input-bar")
        detail_container.mount(hint_bar)

    def action_hooks_from_failed(self) -> None:
        """Add hooks from a failed targets file (from TAP metahook)."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Get the failed hooks file path
        file_path = get_failed_hooks_file_path(changespec)
        if not file_path:
            self.notify("No failed hooks file found", severity="warning")  # type: ignore[attr-defined]
            return

        # Read and parse the file
        try:
            with open(file_path) as f:
                lines = f.readlines()
        except OSError as e:
            self.notify(f"Cannot read file: {e}", severity="error")  # type: ignore[attr-defined]
            return

        # Extract lines starting with // (test targets)
        targets: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("//"):
                targets.append(stripped)

        if not targets:
            self.notify("No test targets found in file", severity="warning")  # type: ignore[attr-defined]
            return

        # Store state for later processing
        self._failed_hooks_targets = targets
        self._failed_hooks_file_path = file_path
        self._hint_mode_active = True
        self._hint_changespec_name = changespec.name

        # Update detail panel to show numbered targets
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)  # type: ignore[attr-defined]
        detail_widget.show_failed_hooks_targets(targets, file_path)

        # Mount the hint input bar
        detail_container = self.query_one("#detail-container")  # type: ignore[attr-defined]
        hint_bar = HintInputBar(mode="failed_hooks", id="hint-input-bar")
        detail_container.mount(hint_bar)

    def _apply_hook_changes(
        self,
        changespec: ChangeSpec,
        result: EditHooksResult,
        hook_hint_to_idx: dict[int, int],
    ) -> bool:
        """Apply hook changes based on modal result."""
        if result.action_type == "rerun_delete":
            return self._handle_rerun_delete_hooks(changespec, result, hook_hint_to_idx)
        elif result.action_type == "test_targets":
            return self._add_test_target_hooks(changespec, result.test_targets)
        else:
            return self._add_custom_hook(changespec, result.hook_command)

    def _handle_rerun_delete_hooks(
        self,
        changespec: ChangeSpec,
        result: EditHooksResult,
        hook_hint_to_idx: dict[int, int],
    ) -> bool:
        """Handle rerun/delete hook commands based on hint numbers."""
        from ....hooks import (
            kill_running_processes_for_hooks,
            rerun_delete_hooks_by_command,
        )

        if not hook_hint_to_idx:
            self.notify("No hooks with status lines to rerun", severity="warning")  # type: ignore[attr-defined]
            return False

        # Get the hook indices for each action
        hook_indices_to_rerun = {hook_hint_to_idx[h] for h in result.hints_to_rerun}
        hook_indices_to_delete = {hook_hint_to_idx[h] for h in result.hints_to_delete}

        # Collect the specific entry IDs to clear for rerun hints
        entry_ids_to_clear = {self._hint_to_entry_id[h] for h in result.hints_to_rerun}

        # Kill any running processes/agents for hooks being rerun or deleted
        all_affected_indices = hook_indices_to_rerun | hook_indices_to_delete
        killed_count = kill_running_processes_for_hooks(
            changespec.hooks, all_affected_indices
        )
        if killed_count > 0:
            self.notify(f"Killed {killed_count} running process(es)")  # type: ignore[attr-defined]

        # Extract command strings from in-memory hooks (may be stale, but just
        # using for identification - actual hooks will be re-read from disk)
        hooks_list = changespec.hooks or []
        commands_to_rerun: set[str] = set()
        commands_to_delete: set[str] = set()
        for idx in hook_indices_to_rerun:
            if idx < len(hooks_list):
                commands_to_rerun.add(hooks_list[idx].command)
        for idx in hook_indices_to_delete:
            if idx < len(hooks_list):
                commands_to_delete.add(hooks_list[idx].command)

        # Use the new function that re-reads fresh state from disk
        success = rerun_delete_hooks_by_command(
            changespec.file_path,
            changespec.name,
            commands_to_rerun,
            commands_to_delete,
            entry_ids_to_clear,
        )

        if success:
            messages = []
            if result.hints_to_rerun:
                messages.append(
                    f"Cleared status for {len(result.hints_to_rerun)} hook(s)"
                )
            if result.hints_to_delete:
                messages.append(f"Deleted {len(result.hints_to_delete)} hook(s)")
            self.notify("; ".join(messages))  # type: ignore[attr-defined]
        else:
            self.notify("Error updating hooks", severity="error")  # type: ignore[attr-defined]

        return success

    def _add_test_target_hooks(
        self, changespec: ChangeSpec, test_targets: list[str]
    ) -> bool:
        """Add bb_rabbit_test hooks for each test target."""
        from ....hooks import add_test_target_hooks_to_changespec

        # Use add_test_target_hooks_to_changespec which handles multiple targets
        # correctly by adding all hooks in a single write operation
        success = add_test_target_hooks_to_changespec(
            changespec.file_path,
            changespec.name,
            test_targets,
            None,  # Re-read fresh from disk to avoid overwriting concurrent changes
        )

        if success:
            self.notify(f"Added {len(test_targets)} test hook(s)")  # type: ignore[attr-defined]
            return True
        else:
            self.notify("Error adding hooks", severity="error")  # type: ignore[attr-defined]
            return False

    def _add_custom_hook(
        self, changespec: ChangeSpec, hook_command: str | None
    ) -> bool:
        """Add a custom hook command."""
        from ....hooks import add_hook_to_changespec

        if not hook_command:
            return False

        success = add_hook_to_changespec(
            changespec.file_path,
            changespec.name,
            hook_command,
            None,  # Re-read fresh from disk to avoid overwriting concurrent changes
        )

        if success:
            self.notify(f"Added hook: {hook_command}")  # type: ignore[attr-defined]
        else:
            self.notify("Error adding hook", severity="error")  # type: ignore[attr-defined]

        return success
