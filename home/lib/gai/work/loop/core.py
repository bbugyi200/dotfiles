"""Core LoopWorkflow class for continuously checking ChangeSpec status updates."""

import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from status_state_machine import remove_workspace_suffix, transition_changespec_status

from ..changespec import (
    ChangeSpec,
    HookEntry,
    HookStatusLine,
    find_all_changespecs,
)
from ..cl_status import (
    SYNCABLE_STATUSES,
    has_pending_comments,
    is_cl_submitted,
    is_parent_submitted,
)
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
)
from ..sync_cache import clear_cache_entry, should_check, update_last_checked
from .hooks_runner import (
    release_entry_workspaces,
    start_stale_hooks,
)

# Interval in seconds between zombie/stale suffix checks (60 seconds)
ZOMBIE_CHECK_INTERVAL_SECONDS = 60


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
        """Check CL submission and comment status for a ChangeSpec.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            Update message if status was updated, None otherwise.
        """
        # Update the last_checked timestamp
        update_last_checked(changespec.name)

        # Check if submitted (applies to both Mailed and Changes Requested)
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

        # If not submitted and status is "Mailed", check for comments
        if (
            changespec.status == "Mailed"
            and is_parent_submitted(changespec)
            and has_pending_comments(changespec)
        ):
            success, old_status, _ = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "Changes Requested",
                validate=False,
            )

            if success:
                return f"Status changed {old_status} -> Changes Requested"

        # If status is "Changes Requested", check if comments have been cleared
        if changespec.status == "Changes Requested" and not has_pending_comments(
            changespec
        ):
            success, old_status, _ = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "Mailed",
                validate=False,
            )

            if success:
                return f"Status changed {old_status} -> Mailed"

        return None

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

        # Check if we should run zombie/stale suffix checks (60-second throttle)
        # This is separate from hook completion checks, which run every cycle
        zombie_cache_key = f"zombie:{changespec.name}"
        should_check_zombie = should_check(
            zombie_cache_key, min_interval=ZOMBIE_CHECK_INTERVAL_SECONDS
        )
        if should_check_zombie:
            update_last_checked(zombie_cache_key)

        # Phase 1: Check completion status of RUNNING hooks (no workspace needed)
        updated_hooks: list[HookEntry] = []
        has_stale_hooks = False

        for hook in changespec.hooks:
            # Check for stale fix-hook suffix (>1h old timestamp) - only every 60s
            if should_check_zombie:
                sl = hook.latest_status_line
                if sl is not None and is_suffix_stale(sl.suffix):
                    # Mark stale fix-hook as failed by setting suffix to "!"
                    set_hook_suffix(
                        changespec.file_path,
                        changespec.name,
                        hook.command,
                        "!",
                        changespec.hooks,
                    )
                    updates.append(
                        f"Hook '{hook.display_command}' stale fix-hook marked as failed"
                    )
                    # Continue processing this hook normally
                    # (the suffix update is written to disk immediately)

            # Check if this hook is a zombie - only every 60s
            if should_check_zombie and is_hook_zombie(hook):
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

    def _run_hooks_cycle(self) -> int:
        """Run a hooks cycle - check completion and start new hooks.

        This runs on the frequent hook interval (default 10s).

        Returns:
            Number of hook state changes detected.
        """
        all_changespecs = find_all_changespecs()
        update_count = 0

        for changespec in all_changespecs:
            # Skip if no hooks
            if not changespec.hooks:
                continue

            updates = self._check_hooks(changespec)
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
        """Run one full check cycle across all ChangeSpecs (status only).

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

            # Run status checks (hooks handled separately)
            updates: list[str] = []

            should_check_stat, _ = self._should_check_status(changespec, bypass_cache)
            if should_check_stat:
                status_update = self._check_status(changespec)
                if status_update:
                    updates.append(status_update)

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
