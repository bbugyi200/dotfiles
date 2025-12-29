"""Core LoopWorkflow class for continuously checking ChangeSpec status updates."""

import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from history_utils import update_history_entry_suffix
from running_field import get_workspace_directory
from status_state_machine import (
    add_ready_to_mail_suffix,
    remove_ready_to_mail_suffix,
    remove_workspace_suffix,
    transition_changespec_status,
)

from ..changespec import (
    ChangeSpec,
    HookEntry,
    HookStatusLine,
    all_hooks_passed_for_entries,
    find_all_changespecs,
    get_base_status,
    get_current_and_proposal_entry_ids,
    has_any_error_suffix,
    has_ready_to_mail_suffix,
    is_parent_ready_for_mail,
)
from ..cl_status import (
    SYNCABLE_STATUSES,
    is_cl_submitted,
    is_parent_submitted,
)
from ..comments import is_timestamp_suffix, update_comment_suffix_type
from ..hooks import (
    check_hook_completion,
    get_last_history_entry_id,
    has_running_hooks,
    hook_has_any_running_status,
    hook_needs_run,
    is_hook_zombie,
    is_suffix_stale,
    set_hook_suffix,
    update_changespec_hooks_field,
    update_hook_status_line_suffix_type,
)
from ..sync_cache import clear_cache_entry, should_check, update_last_checked
from .checks_runner import (
    CHECK_TYPE_AUTHOR_COMMENTS,
    CHECK_TYPE_CL_SUBMITTED,
    CHECK_TYPE_REVIEWER_COMMENTS,
    check_pending_checks,
    has_pending_check,
    start_author_comments_check,
    start_cl_submitted_check,
    start_reviewer_comments_check,
)
from .comments_handler import check_comment_zombies
from .hooks_runner import (
    release_entry_workspaces,
    start_stale_hooks,
)
from .workflows_runner import (
    check_and_complete_workflows,
    start_stale_workflows,
)


class LoopWorkflow:
    """Continuously loops through all ChangeSpecs for status updates."""

    def __init__(
        self,
        interval_seconds: int = 300,
        verbose: bool = False,
        hook_interval_seconds: int = 10,
    ) -> None:
        """Initialize the loop workflow.

        Args:
            interval_seconds: Polling interval in seconds (default: 300 = 5 minutes)
            verbose: If True, show skipped ChangeSpecs in output (default: False)
            hook_interval_seconds: Hook check interval in seconds (default: 10)
        """
        self.interval_seconds = interval_seconds
        self.verbose = verbose
        self.hook_interval_seconds = hook_interval_seconds
        self.console = Console()

    def _is_leaf_cl(self, changespec: ChangeSpec) -> bool:
        """Check if a ChangeSpec is a leaf CL (no parent or parent is submitted).

        Leaf CLs are checked on the first cycle regardless of cache state.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            True if this is a leaf CL, False otherwise.
        """
        return is_parent_submitted(changespec)

    def _log(self, message: str, style: str | None = None) -> None:
        """Print a timestamped log message.

        Args:
            message: The message to print.
            style: Optional rich style to apply (e.g., "dim", "green", "yellow").
        """
        timestamp = datetime.now(ZoneInfo("America/New_York")).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        if style:
            self.console.print(f"[{style}][{timestamp}] {message}[/{style}]")
        else:
            self.console.print(f"[{timestamp}] {message}")

    def _should_check_status(
        self, changespec: ChangeSpec, bypass_cache: bool = False
    ) -> tuple[bool, str | None]:
        """Determine if a ChangeSpec's CL status should be checked.

        Args:
            changespec: The ChangeSpec to check.
            bypass_cache: If True, skip the cache check (used for first cycle).

        Returns:
            Tuple of (should_check, skip_reason). skip_reason is None if should_check.
        """
        base_status = remove_workspace_suffix(changespec.status)
        if base_status not in SYNCABLE_STATUSES:
            return False, f"status '{changespec.status}' not syncable"

        if not bypass_cache:
            if not should_check(changespec.name):
                return False, "recently checked"

        return True, None

    def _check_status(self, changespec: ChangeSpec) -> str | None:
        """Check CL submission status for a ChangeSpec.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            Update message if status was updated, None otherwise.
        """
        # Update the last_checked timestamp
        update_last_checked(changespec.name)

        # Check if submitted
        if is_parent_submitted(changespec) and is_cl_submitted(changespec):
            success, old_status, _ = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "Submitted",
                validate=False,
            )

            if success:
                clear_cache_entry(changespec.name)
                return f"Status changed {old_status} -> Submitted"

        return None

    def _start_pending_checks(
        self, changespec: ChangeSpec, bypass_cache: bool = False
    ) -> list[str]:
        """Start background checks that are due for this changespec.

        This is the non-blocking version of the status/comments checks.
        Checks are started in the background and polled for completion
        in _run_hooks_cycle().

        Args:
            changespec: The ChangeSpec to check.
            bypass_cache: If True, skip the cache check.

        Returns:
            List of update messages for checks that were started.
        """
        updates: list[str] = []

        # Get workspace directory (needed for all checks)
        project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]
        try:
            workspace_dir = get_workspace_directory(project_basename)
        except RuntimeError:
            workspace_dir = None

        # Check if we should run status checks
        should_check_stat, _ = self._should_check_status(changespec, bypass_cache)

        if should_check_stat:
            # Start CL submitted check if not already pending
            if not has_pending_check(changespec, CHECK_TYPE_CL_SUBMITTED):
                if is_parent_submitted(changespec) and changespec.cl:
                    update = start_cl_submitted_check(
                        changespec, workspace_dir, self._log
                    )
                    if update:
                        updates.append(update)

            # Start reviewer comments check if conditions are met
            if not has_pending_check(changespec, CHECK_TYPE_REVIEWER_COMMENTS):
                if (
                    is_parent_submitted(changespec)
                    and changespec.status == "Mailed"
                    and workspace_dir
                ):
                    # Check if we need to start - start if:
                    # 1. No existing reviewer entry, OR
                    # 2. Existing entry has error suffix (not a timestamp = CRS not running)
                    existing_reviewer_entry = None
                    if changespec.comments:
                        for entry in changespec.comments:
                            if entry.reviewer == "critique":
                                existing_reviewer_entry = entry
                                break
                    should_start = existing_reviewer_entry is None or (
                        existing_reviewer_entry.suffix is not None
                        and not is_timestamp_suffix(existing_reviewer_entry.suffix)
                    )
                    if should_start:
                        update = start_reviewer_comments_check(
                            changespec, workspace_dir, self._log
                        )
                        if update:
                            updates.append(update)

        # Start author comments check if conditions are met
        if not has_pending_check(changespec, CHECK_TYPE_AUTHOR_COMMENTS):
            if changespec.status in ("Drafted", "Mailed") and workspace_dir:
                # Skip if any [critique] entry exists
                has_reviewer = False
                if changespec.comments:
                    for entry in changespec.comments:
                        if entry.reviewer == "critique":
                            has_reviewer = True
                            break
                if not has_reviewer:
                    # Check if we need to start - start if:
                    # 1. No existing critique:me entry, OR
                    # 2. Existing entry has error suffix (not a timestamp = CRS not running)
                    existing_author_entry = None
                    if changespec.comments:
                        for entry in changespec.comments:
                            if entry.reviewer == "critique:me":
                                existing_author_entry = entry
                                break
                    should_start = existing_author_entry is None or (
                        existing_author_entry.suffix is not None
                        and not is_timestamp_suffix(existing_author_entry.suffix)
                    )
                    if should_start:
                        update = start_author_comments_check(
                            changespec, workspace_dir, self._log
                        )
                        if update:
                            updates.append(update)

        return updates

    def _should_check_hooks(
        self, changespec: ChangeSpec, bypass_cache: bool = False
    ) -> tuple[bool, str | None]:
        """Determine if a ChangeSpec's hooks should be checked.

        Unlike status checks, hooks run even for ChangeSpecs with children.
        Returns True if there are:
        - Stale hooks that need to be started
        - Running hooks that need completion checks
        - Zombie hooks that need to be marked

        Args:
            changespec: The ChangeSpec to check.
            bypass_cache: If True, skip the cache check (used for first cycle).

        Returns:
            Tuple of (should_check, skip_reason). skip_reason is None if should_check.
        """
        # Check if there are any hooks defined
        if not changespec.hooks:
            return False, "no hooks defined"

        # Get last HISTORY entry ID to compare against (e.g., "1", "1a")
        last_history_entry_id = get_last_history_entry_id(changespec)

        # Check if any hook needs action:
        # - Stale hooks need to be started
        # - Running hooks need completion checks (check ALL status lines, not just latest)
        # - Zombie hooks need to be marked
        has_stale_hooks = False
        has_hooks_running = False
        has_zombie_hooks = False
        for hook in changespec.hooks:
            if hook_needs_run(hook, last_history_entry_id):
                has_stale_hooks = True
            elif hook_has_any_running_status(hook):
                # Check ALL status lines for RUNNING, not just the latest
                if is_hook_zombie(hook):
                    has_zombie_hooks = True
                else:
                    has_hooks_running = True

        if not has_stale_hooks and not has_hooks_running and not has_zombie_hooks:
            return False, "all hooks up to date"

        # Check cache (unless bypassing)
        if not bypass_cache:
            cache_key = f"hooks:{changespec.name}"
            if not should_check(cache_key):
                return False, "recently checked"

        return True, None

    def _check_hooks(self, changespec: ChangeSpec) -> list[str]:
        """Check and run hooks for a ChangeSpec.

        This method handles hooks in two phases:
        1. Check completion status of any RUNNING hooks (no workspace needed)
        2. Start any stale hooks in background (needs workspace)

        Hooks run in the background and their completion is checked in subsequent
        cycles via the output file's exit code marker.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            List of update messages.
        """
        updates: list[str] = []

        # Hooks should exist at this point since we checked in _should_check_hooks
        if not changespec.hooks:
            return updates

        # For terminal statuses (Reverted, Submitted), we still check completion
        # of RUNNING hooks, but we don't start new hooks
        is_terminal_status = changespec.status in ("Reverted", "Submitted")

        # Get last HISTORY entry ID for comparison (e.g., "1", "1a")
        last_history_entry_id = get_last_history_entry_id(changespec)

        # Phase 1: Check completion status of RUNNING hooks (no workspace needed)
        updated_hooks: list[HookEntry] = []
        has_stale_hooks = False

        for hook in changespec.hooks:
            # Check for stale fix-hook suffix (>2h old timestamp)
            sl = hook.latest_status_line
            if sl is not None and is_suffix_stale(sl.suffix):
                # Mark stale fix-hook as ZOMBIE by setting suffix to "ZOMBIE"
                set_hook_suffix(
                    changespec.file_path,
                    changespec.name,
                    hook.command,
                    "ZOMBIE",
                    changespec.hooks,
                )
                updates.append(
                    f"Hook '{hook.display_command}' stale fix-hook marked as ZOMBIE"
                )
                # Continue processing this hook normally
                # (the suffix update is written to disk immediately)

            # Check if this hook is a zombie
            if is_hook_zombie(hook):
                # Mark the RUNNING status line as ZOMBIE
                if hook.status_lines:
                    updated_status_lines = []
                    for sl in hook.status_lines:
                        if sl.status == "RUNNING":
                            # Update RUNNING to ZOMBIE
                            updated_status_lines.append(
                                HookStatusLine(
                                    history_entry_num=sl.history_entry_num,
                                    timestamp=sl.timestamp,
                                    status="ZOMBIE",
                                    duration=sl.duration,
                                )
                            )
                        else:
                            updated_status_lines.append(sl)
                    zombie_hook = HookEntry(
                        command=hook.command,
                        status_lines=updated_status_lines,
                    )
                    updated_hooks.append(zombie_hook)
                    updates.append(f"Hook '{hook.command}' marked as ZOMBIE")
                else:
                    updated_hooks.append(hook)
                continue

            # Check if hook has any RUNNING status (not just the latest)
            # This catches RUNNING hooks from older history entries
            if hook_has_any_running_status(hook):
                # Check if it has completed
                completed_hook = check_hook_completion(changespec, hook)
                if completed_hook:
                    updated_hooks.append(completed_hook)
                    status_msg = completed_hook.status or "UNKNOWN"
                    duration_msg = (
                        f" ({completed_hook.duration})"
                        if completed_hook.duration
                        else ""
                    )
                    updates.append(
                        f"Hook '{hook.command}' -> {status_msg}{duration_msg}"
                    )
                else:
                    # Still running, keep as is
                    updated_hooks.append(hook)
                continue

            # Check if hook needs to run (no status line for current history entry)
            # Don't mark as stale for terminal statuses - we won't start new hooks
            if not is_terminal_status and hook_needs_run(hook, last_history_entry_id):
                has_stale_hooks = True
                # Add placeholder - will be replaced after starting
                updated_hooks.append(hook)
            else:
                # Hook is up to date, keep as is
                updated_hooks.append(hook)

        # Phase 2: Start stale hooks in background (needs workspace)
        # Skip for terminal statuses - don't start new hooks for Reverted/Submitted
        if has_stale_hooks and not is_terminal_status:
            stale_updates, stale_hooks = start_stale_hooks(
                changespec, last_history_entry_id, self._log
            )
            updates.extend(stale_updates)

            # Merge stale hooks into updated_hooks
            # Replace any stale hooks with their started versions
            if stale_hooks:
                stale_by_command = {h.command: h for h in stale_hooks}
                for i, hook in enumerate(updated_hooks):
                    if hook.command in stale_by_command:
                        updated_hooks[i] = stale_by_command[hook.command]

        # Deduplicate hooks by command (handles files with duplicate entries)
        updated_hooks = list({h.command: h for h in updated_hooks}.values())

        # Update the HOOKS field in the file only if there were actual changes
        if updates:
            update_changespec_hooks_field(
                changespec.file_path,
                changespec.name,
                updated_hooks,
            )

        # Release workspace if all hooks have completed (no longer RUNNING)
        # All entry-specific workspaces (loop(hooks)-*) are released by this method
        if not has_running_hooks(updated_hooks):
            release_entry_workspaces(changespec, self._log)

        return updates

    def _check_workflows(self, changespec: ChangeSpec) -> list[str]:
        """Check and run CRS/fix-hook workflows for a ChangeSpec.

        This handles:
        1. Checking completion of running workflows
        2. Auto-accepting completed proposals
        3. Starting new workflows for stale entries

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            List of update messages.
        """
        updates: list[str] = []

        # Phase 1: Check completion of running workflows and auto-accept
        completion_updates = check_and_complete_workflows(changespec, self._log)
        updates.extend(completion_updates)

        # Phase 2: Start stale workflows
        start_updates, _ = start_stale_workflows(changespec, self._log)
        updates.extend(start_updates)

        return updates

    def _transform_old_proposal_suffixes(self, changespec: ChangeSpec) -> list[str]:
        """Remove suffixes from old proposal HISTORY entries.

        An "old proposal" is a proposed entry (Na) where N < the latest regular
        entry number. For example, if HISTORY has (3), then (2a), (2b) are old.

        This affects:
        - HISTORY entry lines with error suffixes (suffix is removed)
        - Hook status lines for those entry IDs (handled separately, transformed)

        Args:
            changespec: The ChangeSpec to process.

        Returns:
            List of update messages.
        """
        updates: list[str] = []

        if not changespec.history:
            return updates

        # Get the last regular (non-proposed) history number
        last_regular_num = 0
        for entry in changespec.history:
            if entry.proposal_letter is None:
                last_regular_num = max(last_regular_num, entry.number)

        # If no regular entries, nothing is "old"
        if last_regular_num == 0:
            return updates

        # Find old proposals with error suffixes that need removal
        for entry in changespec.history:
            if entry.proposal_letter is not None:  # Is a proposal
                if entry.number < last_regular_num:  # Is "old"
                    if entry.suffix_type == "error":  # Has error suffix
                        # Remove HISTORY entry suffix
                        success = update_history_entry_suffix(
                            changespec.file_path,
                            changespec.name,
                            entry.display_number,
                            "remove",
                        )
                        if success:
                            updates.append(
                                f"Cleared suffix from old proposal ({entry.display_number})"
                            )

        # Transform hook status line suffixes for old proposal entry IDs
        # (hook suffixes are handled separately by the hooks formatting code)

        return updates

    def _acknowledge_terminal_status_markers(self, changespec: ChangeSpec) -> list[str]:
        """Transform error suffixes to acknowledged for terminal status ChangeSpecs.

        For ChangeSpecs with STATUS = "Reverted" or "Submitted", transforms all
        `- (!: MSG)` suffixes to `- (~: MSG)` across HISTORY, HOOKS, and COMMENTS.

        Args:
            changespec: The ChangeSpec to process.

        Returns:
            List of update messages.
        """
        updates: list[str] = []

        # Only process terminal statuses
        if changespec.status not in ("Reverted", "Submitted"):
            return updates

        # Process HISTORY entries with error suffix
        if changespec.history:
            for entry in changespec.history:
                if entry.suffix_type == "error":
                    success = update_history_entry_suffix(
                        changespec.file_path,
                        changespec.name,
                        entry.display_number,
                        "acknowledged",
                    )
                    if success:
                        updates.append(
                            f"Acknowledged HISTORY ({entry.display_number}) "
                            f"suffix: {entry.suffix}"
                        )

        # Process HOOKS entries with error suffix_type
        if changespec.hooks:
            for hook in changespec.hooks:
                if hook.status_lines:
                    for sl in hook.status_lines:
                        if sl.suffix and sl.suffix_type == "error":
                            success = update_hook_status_line_suffix_type(
                                changespec.file_path,
                                changespec.name,
                                hook.command,
                                sl.history_entry_num,
                                "acknowledged",
                                changespec.hooks,
                            )
                            if success:
                                updates.append(
                                    f"Acknowledged HOOK '{hook.display_command}' "
                                    f"({sl.history_entry_num}) suffix: {sl.suffix}"
                                )

        # Process COMMENTS entries with error suffix_type
        if changespec.comments:
            for comment in changespec.comments:
                if comment.suffix and comment.suffix_type == "error":
                    success = update_comment_suffix_type(
                        changespec.file_path,
                        changespec.name,
                        comment.reviewer,
                        "acknowledged",
                        changespec.comments,
                    )
                    if success:
                        updates.append(
                            f"Acknowledged COMMENT [{comment.reviewer}] "
                            f"suffix: {comment.suffix}"
                        )

        return updates

    def _check_ready_to_mail(
        self, changespec: ChangeSpec, all_changespecs: list[ChangeSpec]
    ) -> list[str]:
        """Check if a ChangeSpec is ready to mail and add/remove suffix accordingly.

        A ChangeSpec is ready to mail if:
        - STATUS is "Drafted" (base status)
        - No error suffixes exist in HISTORY/HOOKS/COMMENTS
        - Parent is ready (no parent, Submitted, or Mailed)
        - All hooks have PASSED for current history entry and its proposals

        If a ChangeSpec has the READY TO MAIL suffix but conditions are no longer
        met, the suffix will be removed.

        Args:
            changespec: The ChangeSpec to check.
            all_changespecs: All changespecs (for parent lookup).

        Returns:
            List of update messages.
        """
        updates: list[str] = []

        # Get base status (strip any existing suffix)
        base_status = get_base_status(changespec.status)

        # Only applies to Drafted status
        if base_status != "Drafted":
            return updates

        already_has_suffix = has_ready_to_mail_suffix(changespec.status)
        has_errors = has_any_error_suffix(changespec)
        parent_ready = is_parent_ready_for_mail(changespec, all_changespecs)

        # Check if all hooks have PASSED for current entry and proposals
        entry_ids = get_current_and_proposal_entry_ids(changespec)
        hooks_passed = all_hooks_passed_for_entries(changespec, entry_ids)

        # Determine if conditions are met
        conditions_met = not has_errors and parent_ready and hooks_passed

        if conditions_met and not already_has_suffix:
            # Add the suffix
            success = add_ready_to_mail_suffix(changespec.file_path, changespec.name)
            if success:
                updates.append("Added READY TO MAIL suffix")
        elif not conditions_met and already_has_suffix:
            # Remove the suffix - conditions no longer met
            success = remove_ready_to_mail_suffix(changespec.file_path, changespec.name)
            if success:
                if has_errors:
                    updates.append(
                        "Removed READY TO MAIL suffix (error suffix appeared)"
                    )
                elif not parent_ready:
                    updates.append(
                        "Removed READY TO MAIL suffix (parent no longer ready)"
                    )
                else:
                    updates.append(
                        "Removed READY TO MAIL suffix (hooks not all passed)"
                    )

        return updates

    def _run_hooks_cycle(self) -> int:
        """Run a hooks cycle - check completion, start new hooks, and detect zombies.

        This runs on the frequent hook interval (default 10s).

        Returns:
            Number of hook/comment state changes detected.
        """
        all_changespecs = find_all_changespecs()
        update_count = 0

        for changespec in all_changespecs:
            updates: list[str] = []

            # Poll for completed background checks (cl_submitted, comments)
            check_updates = check_pending_checks(changespec, self._log)
            updates.extend(check_updates)

            # Check hooks if any are defined
            if changespec.hooks:
                hook_updates = self._check_hooks(changespec)
                updates.extend(hook_updates)

            # Check for stale comment entries (ZOMBIE detection)
            zombie_updates = check_comment_zombies(changespec)
            updates.extend(zombie_updates)

            # Check and run CRS/fix-hook workflows
            workflow_updates = self._check_workflows(changespec)
            updates.extend(workflow_updates)

            # Transform old proposal suffixes (!: -> ~:)
            transform_updates = self._transform_old_proposal_suffixes(changespec)
            updates.extend(transform_updates)

            # Acknowledge terminal status attention markers (!: -> ~:)
            acknowledge_updates = self._acknowledge_terminal_status_markers(changespec)
            updates.extend(acknowledge_updates)

            # Check if ChangeSpec is ready to mail and add suffix
            ready_to_mail_updates = self._check_ready_to_mail(
                changespec, all_changespecs
            )
            updates.extend(ready_to_mail_updates)

            for update in updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")
                update_count += 1

        return update_count

    def _check_single_changespec(
        self, changespec: ChangeSpec, bypass_cache: bool = False
    ) -> tuple[list[str], list[str], list[str]]:
        """Check a single ChangeSpec for updates.

        Args:
            changespec: The ChangeSpec to check.
            bypass_cache: If True, skip the cache check (used for first cycle leaf CLs).

        Returns:
            Tuple of (updates, checked_types, skip_reasons).
            - updates: List of update messages (e.g., "Status changed Mailed -> Submitted")
            - checked_types: List of what was checked (e.g., ["status"])
            - skip_reasons: List of skip reasons (e.g., ["status: not syncable"])
        """
        updates = []
        checked_types = []
        skip_reasons = []

        # Check status (submission/comments)
        should_check_stat, stat_skip_reason = self._should_check_status(
            changespec, bypass_cache
        )
        if should_check_stat:
            checked_types.append("status")
            status_update = self._check_status(changespec)
            if status_update:
                updates.append(status_update)
        elif stat_skip_reason:
            skip_reasons.append(f"status: {stat_skip_reason}")

        return updates, checked_types, skip_reasons

    def _run_check_cycle(self, first_cycle: bool = False) -> int:
        """Run one full check cycle across all ChangeSpecs (status and comments).

        Hooks are checked separately via _run_hooks_cycle at a faster interval.

        Args:
            first_cycle: If True, bypass cache for leaf CLs (CLs with no parent
                or submitted parents).

        Returns:
            Number of ChangeSpecs that were updated.
        """
        all_changespecs = find_all_changespecs()
        update_count = 0

        for changespec in all_changespecs:
            # On first cycle, bypass cache for leaf CLs
            bypass_cache = first_cycle and self._is_leaf_cl(changespec)

            # Start background checks (non-blocking)
            # Results are polled in _run_hooks_cycle()
            updates = self._start_pending_checks(changespec, bypass_cache)

            for update in updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")
                update_count += 1

        # Only show cycle complete message if there were updates
        if update_count > 0:
            self._log(f"Full cycle complete: {update_count} update(s)", style="green")

        return update_count

    def _count_projects(self, changespecs: list[ChangeSpec]) -> int:
        """Count unique projects from a list of ChangeSpecs.

        Args:
            changespecs: List of ChangeSpecs.

        Returns:
            Number of unique projects.
        """
        projects = set()
        for cs in changespecs:
            # Extract project name from file path
            project_basename = os.path.splitext(os.path.basename(cs.file_path))[0]
            projects.add(project_basename)
        return len(projects)

    def run(self) -> bool:
        """Run the continuous loop.

        Full checks (status, hooks) run at interval_seconds (default 5m).
        Hook status checks run at hook_interval_seconds (default 10s).

        Returns:
            True if exited normally, False on error.
        """
        # Print startup info
        interval_str = (
            f"{self.interval_seconds // 60} minutes"
            if self.interval_seconds >= 60
            else f"{self.interval_seconds} seconds"
        )
        hook_interval_str = (
            f"{self.hook_interval_seconds // 60} minutes"
            if self.hook_interval_seconds >= 60
            else f"{self.hook_interval_seconds} seconds"
        )
        self._log(
            f"GAI Loop started - full checks every {interval_str}, "
            f"hook checks every {hook_interval_str} (Ctrl+C to exit)"
        )

        # Count initial changespecs
        initial_changespecs = find_all_changespecs()
        project_count = self._count_projects(initial_changespecs)
        self._log(
            f"Looping through {len(initial_changespecs)} ChangeSpecs "
            f"across {project_count} project(s)"
        )

        try:
            first_cycle = True
            while True:
                self._run_check_cycle(first_cycle=first_cycle)
                first_cycle = False

                # Between full cycles, run frequent hooks checks
                elapsed = 0
                while elapsed < self.interval_seconds:
                    time.sleep(self.hook_interval_seconds)
                    elapsed += self.hook_interval_seconds

                    # Check if we've reached the next full cycle
                    if elapsed >= self.interval_seconds:
                        break

                    # Run hooks cycle (check completion and start new hooks)
                    self._run_hooks_cycle()

        except KeyboardInterrupt:
            self._log("Loop stopped by user")
            return True
