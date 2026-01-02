"""Hint-based action methods for the ace TUI app."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ...changespec import ChangeSpec, HookEntry
from ...hint_types import EditHooksResult, ViewFilesResult
from ...hints import (
    build_editor_args,
    is_rerun_input,
    parse_edit_hooks_input,
    parse_test_targets,
    parse_view_input,
)
from ..widgets import ChangeSpecDetail, HintInputBar

if TYPE_CHECKING:
    pass


class HintActionsMixin:
    """Mixin providing hint-based actions (edit hooks, view files)."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    _hint_mode_active: bool
    _hint_mode_hints_for: str | None
    _hint_mappings: dict[int, str]
    _hook_hint_to_idx: dict[int, int]
    _hint_changespec_name: str

    # --- Edit Hooks Action ---

    def action_edit_hooks(self) -> None:
        """Edit hooks for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Re-render detail with hints for hooks_latest_only
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)  # type: ignore[attr-defined]
        query_str = self.canonical_query_string  # type: ignore[attr-defined]
        hint_mappings, hook_hint_to_idx = detail_widget.update_display_with_hints(
            changespec,
            query_str,
            hints_for="hooks_latest_only",
            hooks_collapsed=self.hooks_collapsed,  # type: ignore[attr-defined]
        )

        # Store state for later processing
        self._hint_mode_active = True
        self._hint_mode_hints_for = "hooks_latest_only"
        self._hint_mappings = hint_mappings
        self._hook_hint_to_idx = hook_hint_to_idx
        self._hint_changespec_name = changespec.name

        # Mount the hint input bar
        detail_container = self.query_one("#detail-container")  # type: ignore[attr-defined]
        hint_bar = HintInputBar(mode="hooks", id="hint-input-bar")
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
        from ...hooks import (
            get_last_history_entry_id,
            kill_running_processes_for_hooks,
            update_changespec_hooks_field,
        )

        if not hook_hint_to_idx:
            self.notify("No hooks with status lines to rerun", severity="warning")  # type: ignore[attr-defined]
            return False

        last_history_entry_id = get_last_history_entry_id(changespec)
        if last_history_entry_id is None:
            self.notify("No HISTORY entries found", severity="warning")  # type: ignore[attr-defined]
            return False

        # Get the hook indices for each action
        hook_indices_to_rerun = {hook_hint_to_idx[h] for h in result.hints_to_rerun}
        hook_indices_to_delete = {hook_hint_to_idx[h] for h in result.hints_to_delete}

        # Kill any running processes/agents for hooks being rerun or deleted
        all_affected_indices = hook_indices_to_rerun | hook_indices_to_delete
        killed_count = kill_running_processes_for_hooks(
            changespec.hooks, all_affected_indices
        )
        if killed_count > 0:
            self.notify(f"Killed {killed_count} running process(es)")  # type: ignore[attr-defined]

        # Create updated hooks list
        updated_hooks: list[HookEntry] = []
        for i, hook in enumerate(changespec.hooks or []):
            if i in hook_indices_to_delete:
                continue  # Skip (delete)
            elif i in hook_indices_to_rerun:
                if hook.status_lines:
                    remaining_status_lines = [
                        sl
                        for sl in hook.status_lines
                        if sl.commit_entry_num != last_history_entry_id
                    ]
                    updated_hooks.append(
                        HookEntry(
                            command=hook.command,
                            status_lines=(
                                remaining_status_lines
                                if remaining_status_lines
                                else None
                            ),
                        )
                    )
                else:
                    updated_hooks.append(hook)
            else:
                updated_hooks.append(hook)

        success = update_changespec_hooks_field(
            changespec.file_path, changespec.name, updated_hooks
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
        from ...hooks import add_test_target_hooks_to_changespec

        # Use add_test_target_hooks_to_changespec which handles multiple targets
        # correctly by adding all hooks in a single write operation
        success = add_test_target_hooks_to_changespec(
            changespec.file_path,
            changespec.name,
            test_targets,
            changespec.hooks,
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
        from ...hooks import add_hook_to_changespec

        if not hook_command:
            return False

        success = add_hook_to_changespec(
            changespec.file_path,
            changespec.name,
            hook_command,
            changespec.hooks,
        )

        if success:
            self.notify(f"Added hook: {hook_command}")  # type: ignore[attr-defined]
        else:
            self.notify("Error adding hook", severity="error")  # type: ignore[attr-defined]

        return success

    # --- View Files Action ---

    def action_view_files(self) -> None:
        """View files for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Re-render detail with hints
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)  # type: ignore[attr-defined]
        query_str = self.canonical_query_string  # type: ignore[attr-defined]
        hint_mappings, _ = detail_widget.update_display_with_hints(
            changespec,
            query_str,
            hints_for=None,
            hooks_collapsed=self.hooks_collapsed,  # type: ignore[attr-defined]
        )

        if len(hint_mappings) <= 1:  # Only hint 0 (project file)
            self.notify("No files available to view", severity="warning")  # type: ignore[attr-defined]
            self._refresh_display()  # type: ignore[attr-defined]
            return

        # Store state for later processing
        self._hint_mode_active = True
        self._hint_mode_hints_for = None  # "all" hints
        self._hint_mappings = hint_mappings
        self._hint_changespec_name = changespec.name

        # Mount the hint input bar
        detail_container = self.query_one("#detail-container")  # type: ignore[attr-defined]
        hint_bar = HintInputBar(mode="view", id="hint-input-bar")
        detail_container.mount(hint_bar)

    def _open_files_in_editor(self, result: ViewFilesResult) -> None:
        """Open files in $EDITOR (requires suspend)."""
        import subprocess

        def run_editor() -> None:
            editor = os.environ.get("EDITOR", "vi")
            editor_args = build_editor_args(
                editor, result.user_input, result.changespec_name, result.files
            )
            subprocess.run(editor_args, check=False)

        with self.suspend():  # type: ignore[attr-defined]
            run_editor()

    def _view_files_with_pager(self, files: list[str]) -> None:
        """View files using bat/cat with less (requires suspend)."""
        import shlex
        import shutil
        import subprocess

        def run_viewer() -> None:
            viewer = "bat" if shutil.which("bat") else "cat"
            quoted_files = " ".join(shlex.quote(f) for f in files)
            if viewer == "bat":
                cmd = f"bat --color=always {quoted_files} | less -R"
            else:
                cmd = f"cat {quoted_files} | less"
            subprocess.run(cmd, shell=True, check=False)

        with self.suspend():  # type: ignore[attr-defined]
            run_viewer()

    # --- Hint Input Bar Event Handlers ---

    def on_hint_input_bar_submitted(self, event: HintInputBar.Submitted) -> None:
        """Handle hint input submission."""
        self._remove_hint_input_bar()

        if event.mode == "view":
            self._process_view_input(event.value)
        else:
            self._process_hooks_input(event.value)

    def on_hint_input_bar_cancelled(self, event: HintInputBar.Cancelled) -> None:
        """Handle hint input cancellation."""
        self._remove_hint_input_bar()

    def _remove_hint_input_bar(self) -> None:
        """Remove the hint input bar and restore normal display."""
        # Clear hint mode state first
        self._hint_mode_active = False
        self._hint_mode_hints_for = None

        try:
            hint_bar = self.query_one("#hint-input-bar", HintInputBar)  # type: ignore[attr-defined]
            hint_bar.remove()
        except Exception:
            pass
        self._refresh_display()  # type: ignore[attr-defined]

    def _process_view_input(self, user_input: str) -> None:
        """Process view files input."""
        if not user_input:
            return

        files, open_in_editor, invalid_hints = parse_view_input(
            user_input, self._hint_mappings
        )

        if invalid_hints:
            self.notify(  # type: ignore[attr-defined]
                f"Invalid hints: {', '.join(str(h) for h in invalid_hints)}",
                severity="warning",
            )
            return

        if not files:
            self.notify("No valid files selected", severity="warning")  # type: ignore[attr-defined]
            return

        if open_in_editor:
            result = ViewFilesResult(
                files=files,
                open_in_editor=True,
                user_input=user_input,
                changespec_name=self._hint_changespec_name,
            )
            self._open_files_in_editor(result)
        else:
            self._view_files_with_pager(files)

    def _process_hooks_input(self, user_input: str) -> None:
        """Process edit hooks input."""
        if not user_input:
            return

        changespec = self.changespecs[self.current_idx]

        if is_rerun_input(user_input):
            # Rerun/delete hooks
            hints_to_rerun, hints_to_delete, invalid_hints = parse_edit_hooks_input(
                user_input, self._hint_mappings
            )

            if invalid_hints:
                self.notify(  # type: ignore[attr-defined]
                    f"Invalid hints: {', '.join(str(h) for h in invalid_hints)}",
                    severity="warning",
                )
                return

            if not hints_to_rerun and not hints_to_delete:
                self.notify("No valid hooks selected", severity="warning")  # type: ignore[attr-defined]
                return

            result = EditHooksResult(
                action_type="rerun_delete",
                hints_to_rerun=hints_to_rerun,
                hints_to_delete=hints_to_delete,
            )
            success = self._apply_hook_changes(
                changespec, result, self._hook_hint_to_idx
            )
            if success:
                self._reload_and_reposition()  # type: ignore[attr-defined]

        elif user_input.startswith("//"):
            # Test targets
            targets = parse_test_targets(user_input)
            if not targets:
                self.notify("No test targets provided", severity="warning")  # type: ignore[attr-defined]
                return

            result = EditHooksResult(
                action_type="test_targets",
                test_targets=targets,
            )
            success = self._apply_hook_changes(
                changespec, result, self._hook_hint_to_idx
            )
            if success:
                self._reload_and_reposition()  # type: ignore[attr-defined]

        else:
            # Custom hook command
            result = EditHooksResult(
                action_type="custom_hook",
                hook_command=user_input,
            )
            success = self._apply_hook_changes(
                changespec, result, self._hook_hint_to_idx
            )
            if success:
                self._reload_and_reposition()  # type: ignore[attr-defined]
