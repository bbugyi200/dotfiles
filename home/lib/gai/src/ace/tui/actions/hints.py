"""Hint-based action methods for the ace TUI app."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from accept_workflow.parsing import (
    expand_shorthand_proposals,
    parse_proposal_entries,
)

from ...changespec import ChangeSpec
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
    _hint_to_entry_id: dict[int, str]
    _hint_changespec_name: str
    _accept_mode_active: bool
    _accept_last_base: str | None

    # --- Edit Hooks Action ---

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
        from ...hooks import add_test_target_hooks_to_changespec

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
        from ...hooks import add_hook_to_changespec

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

    # --- View Files Action ---

    def action_view_files(self) -> None:
        """View files for the current ChangeSpec."""
        if not self.changespecs:
            return

        changespec = self.changespecs[self.current_idx]

        # Re-render detail with hints
        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)  # type: ignore[attr-defined]
        query_str = self.canonical_query_string  # type: ignore[attr-defined]
        hint_mappings, _, _ = detail_widget.update_display_with_hints(
            changespec,
            query_str,
            hints_for=None,
            hooks_collapsed=self.hooks_collapsed,  # type: ignore[attr-defined]
            commits_collapsed=self.commits_collapsed,  # type: ignore[attr-defined]
            mentors_collapsed=self.mentors_collapsed,  # type: ignore[attr-defined]
        )

        if not hint_mappings:  # No files available
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
            editor_args = build_editor_args(editor, result.files)
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

    def _copy_files_to_clipboard(self, files: list[str]) -> None:
        """Copy file paths to system clipboard."""
        import subprocess
        import sys

        home = str(Path.home())
        shortened_files = [
            f.replace(home, "~", 1) if f.startswith(home) else f for f in files
        ]
        content = " ".join(shortened_files)

        if sys.platform == "darwin":
            clipboard_cmd = ["pbcopy"]
        elif sys.platform.startswith("linux"):
            clipboard_cmd = ["xclip", "-selection", "clipboard"]
        else:
            self.notify(  # type: ignore[attr-defined]
                f"Clipboard not supported on {sys.platform}", severity="error"
            )
            return

        try:
            subprocess.run(clipboard_cmd, input=content, text=True, check=True)
            self.notify(f"Copied {len(files)} path(s) to clipboard")  # type: ignore[attr-defined]
        except subprocess.CalledProcessError as e:
            self.notify(  # type: ignore[attr-defined]
                f"Clipboard command failed: {e}", severity="error"
            )
        except FileNotFoundError:
            self.notify(  # type: ignore[attr-defined]
                f"{clipboard_cmd[0]} not found", severity="error"
            )

    # --- Hint Input Bar Event Handlers ---

    def on_hint_input_bar_submitted(self, event: HintInputBar.Submitted) -> None:
        """Handle hint input submission."""
        self._remove_hint_input_bar()

        if event.mode == "view":
            self._process_view_input(event.value)
        elif event.mode == "hooks":
            self._process_hooks_input(event.value)
        else:  # accept mode
            self._process_accept_input(event.value)

    def on_hint_input_bar_cancelled(self, event: HintInputBar.Cancelled) -> None:
        """Handle hint input cancellation."""
        self._remove_hint_input_bar()

    def _remove_hint_input_bar(self) -> None:
        """Remove the hint input bar and restore normal display."""
        # Clear hint mode state first
        self._hint_mode_active = False
        self._hint_mode_hints_for = None

        # Clear accept mode state
        self._accept_mode_active = False

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

        files, open_in_editor, copy_to_clipboard, invalid_hints = parse_view_input(
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

        if copy_to_clipboard:
            self._copy_files_to_clipboard(files)
        elif open_in_editor:
            result = ViewFilesResult(
                files=files,
                open_in_editor=True,
                copy_to_clipboard=False,
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

    def _process_accept_input(self, user_input: str) -> None:
        """Process accept proposal input.

        Supports the @ suffix for triggering mail after accept:
        - "a b c@" - accept proposals a, b, c and then mail the CL
        - "@" alone - run full mail flow (mail prep first, then mark ready, then mail)
        """
        if not user_input:
            return

        changespec = self.changespecs[self.current_idx]

        # Special case: "@" alone means run full mail flow
        # (mail prep first, then mark ready to mail, then execute mail)
        if user_input.strip() == "@":
            self._handle_at_alone_mail_flow(changespec)
            return

        # Split input into args
        args = user_input.split()

        # Check if the last argument ends with "@" (trigger mail after accept)
        should_mail = False
        if args and args[-1].endswith("@"):
            should_mail = True
            # Strip the "@" suffix from the last argument
            args[-1] = args[-1][:-1]
            # If the last arg is now empty (it was just "@"), remove it
            if not args[-1]:
                args.pop()
            # If no args left after removing "@", that's an error
            if not args:
                self.notify("Invalid format", severity="warning")  # type: ignore[attr-defined]
                return

        # Try to expand shorthand and parse
        expanded = expand_shorthand_proposals(args, self._accept_last_base)
        if expanded is None:
            if self._accept_last_base is None:
                self.notify(  # type: ignore[attr-defined]
                    "No accepted commits - cannot use shorthand (a b c)",
                    severity="warning",
                )
            else:
                self.notify("Invalid format", severity="warning")  # type: ignore[attr-defined]
            return

        entries = parse_proposal_entries(expanded)
        if entries is None:
            self.notify("Invalid proposal format", severity="warning")  # type: ignore[attr-defined]
            return

        # Run the accept workflow (with mark_ready_to_mail flag if @ suffix was used)
        self._run_accept_workflow(  # type: ignore[attr-defined]
            changespec, entries, mark_ready_to_mail=should_mail
        )

        # If should_mail is True, the workflow already marked as ready to mail.
        # Now trigger the mail flow.
        if should_mail:
            self._trigger_mail_after_accept()  # type: ignore[attr-defined]

    def _trigger_mail_after_accept(self) -> None:
        """Trigger the mail flow after a successful accept with @ suffix.

        This reloads the changespec (which now has READY TO MAIL suffix)
        and triggers the mail action.
        """
        # Reload to get updated changespec with READY TO MAIL suffix
        self._reload_and_reposition()  # type: ignore[attr-defined]

        # Now call the mail action (same as pressing 'm')
        self.action_mail()  # type: ignore[attr-defined]

    def _handle_at_alone_mail_flow(self, changespec: ChangeSpec) -> None:
        """Handle the full mail flow when "@" alone is input.

        This runs the mail operations in a specific order:
        1. Run mail prep FIRST (reviewer prompts, description modification, nvim)
        2. Ask user if they want to mail
        3. Run mark_ready_to_mail operations (kill processes, reject proposals)
        4. Set status atomically (to "Mailed" if user confirmed, or READY TO MAIL if not)
        5. Execute hg mail if user confirmed

        Args:
            changespec: The ChangeSpec to process
        """
        from rich.console import Console

        from ...changespec import get_base_status, has_ready_to_mail_suffix
        from ...mail_ops import MailPrepResult, execute_mail, prepare_mail

        # Validate: must be Drafted without READY TO MAIL suffix
        base_status = get_base_status(changespec.status)
        if base_status != "Drafted":
            self.notify("Must be Drafted status", severity="warning")  # type: ignore[attr-defined]
            return
        if has_ready_to_mail_suffix(changespec.status):
            self.notify("Already marked as ready to mail", severity="warning")  # type: ignore[attr-defined]
            return

        # STEP 1: Run mail prep FIRST (prompts for reviewers, modifies description, opens nvim)
        prep_result: MailPrepResult | None = None

        def run_mail_prep() -> MailPrepResult | None:
            console = Console()
            return prepare_mail(changespec, console)

        with self.suspend():  # type: ignore[attr-defined]
            prep_result = run_mail_prep()

        if prep_result is None:
            # User aborted or error occurred
            self._reload_and_reposition()  # type: ignore[attr-defined]
            return

        # STEP 2: Mark ready to mail with appropriate final status
        # If user said "yes" to mail, set status directly to "Mailed"
        # If user said "no", just add READY TO MAIL suffix
        final_status = "Mailed" if prep_result.should_mail else None
        success = self._mark_ready_to_mail_atomic(changespec, final_status)  # type: ignore[attr-defined]

        if not success:
            self.notify("Failed to mark as ready to mail", severity="error")  # type: ignore[attr-defined]
            self._reload_and_reposition()  # type: ignore[attr-defined]
            return

        # STEP 3: Execute mail if user confirmed
        if prep_result.should_mail:

            def run_mail() -> bool:
                console = Console()
                return execute_mail(changespec, prep_result.target_dir, console)

            with self.suspend():  # type: ignore[attr-defined]
                mail_success = run_mail()

            if mail_success:
                self.notify("CL mailed successfully")  # type: ignore[attr-defined]
            else:
                self.notify("Failed to mail CL", severity="error")  # type: ignore[attr-defined]
        else:
            self.notify("Marked as ready to mail")  # type: ignore[attr-defined]

        self._reload_and_reposition()  # type: ignore[attr-defined]
