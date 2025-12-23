"""Monitor workflow for continuously checking ChangeSpec status updates."""

import os
import subprocess
import sys
import time
from datetime import datetime

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from running_field import (
    claim_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from status_state_machine import remove_workspace_suffix, transition_changespec_status

from .changespec import ChangeSpec, HookEntry, find_all_changespecs
from .cl_status import (
    PRESUBMIT_ZOMBIE_THRESHOLD_SECONDS,
    SYNCABLE_STATUSES,
    check_presubmit_status,
    get_presubmit_file_age_seconds,
    get_presubmit_file_path,
    has_pending_comments,
    is_cl_submitted,
    is_parent_submitted,
    presubmit_needs_check,
    update_changespec_presubmit_tag,
)
from .hooks import (
    check_hook_completion,
    get_last_history_diff_timestamp,
    hook_needs_run,
    is_hook_zombie,
    start_hook_background,
    update_changespec_hooks_field,
)
from .sync_cache import clear_cache_entry, should_check, update_last_checked


class MonitorWorkflow:
    """Continuously monitors all ChangeSpecs for status updates."""

    def __init__(
        self,
        interval_seconds: int = 300,
        verbose: bool = False,
        hook_interval_seconds: int = 10,
    ) -> None:
        """Initialize the monitor workflow.

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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if style:
            self.console.print(f"[{style}][{timestamp}] {message}[/{style}]")
        else:
            self.console.print(f"[{timestamp}] {message}")

    def _should_check_presubmit(
        self, changespec: ChangeSpec, bypass_cache: bool = False
    ) -> tuple[bool, str | None]:
        """Determine if a ChangeSpec's presubmit status should be checked.

        Args:
            changespec: The ChangeSpec to check.
            bypass_cache: If True, skip the cache check (used for first cycle).

        Returns:
            Tuple of (should_check, skip_reason). skip_reason is None if should_check.
        """
        if not presubmit_needs_check(changespec.presubmit):
            return False, "no presubmit to check"

        if not bypass_cache:
            cache_key = f"presubmit:{changespec.name}"
            if not should_check(cache_key):
                return False, "recently checked"

        return True, None

    def _check_presubmit(self, changespec: ChangeSpec) -> str | None:
        """Check presubmit status for a ChangeSpec.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            Update message if presubmit was updated, None otherwise.
        """
        # Update the last_checked timestamp
        cache_key = f"presubmit:{changespec.name}"
        update_last_checked(cache_key)

        # Get the presubmit value
        presubmit_value = changespec.presubmit
        if not presubmit_value:
            return None

        # Get the presubmit file path
        presubmit_path = get_presubmit_file_path(presubmit_value)
        if not presubmit_path:
            return None

        # Check if presubmit is a zombie (running > 24h)
        file_age = get_presubmit_file_age_seconds(presubmit_path)
        if file_age is not None and file_age > PRESUBMIT_ZOMBIE_THRESHOLD_SECONDS:
            new_value = f"{presubmit_value} (ZOMBIE)"
            if update_changespec_presubmit_tag(
                changespec.file_path, changespec.name, new_value
            ):
                return "Presubmit marked as ZOMBIE (running > 24h)"
            return None

        # Check presubmit completion status
        presubmit_result = check_presubmit_status(changespec)

        if presubmit_result == 0:
            # Presubmit succeeded
            new_value = f"{presubmit_value} (PASSED)"
            if update_changespec_presubmit_tag(
                changespec.file_path, changespec.name, new_value
            ):
                clear_cache_entry(cache_key)
                return "Presubmit completed (PASSED)"

        elif presubmit_result == 1:
            # Presubmit failed
            new_value = f"{presubmit_value} (FAILED)"
            if update_changespec_presubmit_tag(
                changespec.file_path, changespec.name, new_value
            ):
                return "Presubmit completed (FAILED)"

        return None

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

        Unlike status/presubmit checks, hooks run even for ChangeSpecs with children.
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

        # Get last DIFF timestamp to compare against
        last_diff_timestamp = get_last_history_diff_timestamp(changespec)

        # Check if any hook needs action:
        # - Stale hooks need to be started
        # - Running hooks need completion checks
        # - Zombie hooks need to be marked
        has_stale_hooks = False
        has_running_hooks = False
        has_zombie_hooks = False
        for hook in changespec.hooks:
            if hook_needs_run(hook, last_diff_timestamp):
                has_stale_hooks = True
            elif hook.status == "RUNNING":
                if is_hook_zombie(hook):
                    has_zombie_hooks = True
                else:
                    has_running_hooks = True

        if not has_stale_hooks and not has_running_hooks and not has_zombie_hooks:
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

        # Update the last_checked timestamp
        cache_key = f"hooks:{changespec.name}"
        update_last_checked(cache_key)

        # Hooks should exist at this point since we checked in _should_check_hooks
        if not changespec.hooks:
            return updates

        # Get last DIFF timestamp for comparison
        last_diff_timestamp = get_last_history_diff_timestamp(changespec)

        # Phase 1: Check completion status of RUNNING hooks (no workspace needed)
        updated_hooks: list[HookEntry] = []
        has_stale_hooks = False

        for hook in changespec.hooks:
            # Check if this hook is a zombie
            if is_hook_zombie(hook):
                # Mark as zombie
                zombie_hook = HookEntry(
                    command=hook.command,
                    timestamp=hook.timestamp,
                    status="ZOMBIE",
                    duration=hook.duration,
                )
                updated_hooks.append(zombie_hook)
                updates.append(f"Hook '{hook.command}' marked as ZOMBIE")
                continue

            # Check if hook is currently running
            if hook.status == "RUNNING" and hook.timestamp:
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

            # Check if hook needs to run (never run or stale)
            if hook_needs_run(hook, last_diff_timestamp):
                has_stale_hooks = True
                # Add placeholder - will be replaced after starting
                updated_hooks.append(hook)
            else:
                # Hook is up to date, keep as is
                updated_hooks.append(hook)

        # Phase 2: Start stale hooks in background (needs workspace)
        if has_stale_hooks:
            stale_updates, stale_hooks = self._start_stale_hooks(
                changespec, last_diff_timestamp
            )
            updates.extend(stale_updates)

            # Merge stale hooks into updated_hooks
            # Replace any stale hooks with their started versions
            if stale_hooks:
                stale_by_command = {h.command: h for h in stale_hooks}
                for i, hook in enumerate(updated_hooks):
                    if hook.command in stale_by_command:
                        updated_hooks[i] = stale_by_command[hook.command]

        # Update the HOOKS field in the file
        if updated_hooks:
            update_changespec_hooks_field(
                changespec.file_path,
                changespec.name,
                updated_hooks,
            )

        return updates

    def _check_hook_status_only(self, changespec: ChangeSpec) -> list[str]:
        """Check completion status of RUNNING hooks only (no starting new hooks).

        This is a lightweight check for the frequent hook interval that only
        checks if RUNNING hooks have completed, without claiming workspaces
        or starting new hooks.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            List of update messages for hooks that changed state.
        """
        updates: list[str] = []

        if not changespec.hooks:
            return updates

        # Don't check hooks for terminal statuses
        if changespec.status in ("Reverted", "Submitted"):
            return updates

        # Check completion status of RUNNING hooks only
        updated_hooks: list[HookEntry] = []
        hooks_changed = False

        for hook in changespec.hooks:
            # Check if this hook is a zombie
            if hook.status == "RUNNING" and is_hook_zombie(hook):
                # Mark as zombie
                zombie_hook = HookEntry(
                    command=hook.command,
                    timestamp=hook.timestamp,
                    status="ZOMBIE",
                    duration=hook.duration,
                )
                updated_hooks.append(zombie_hook)
                updates.append(f"Hook '{hook.command}' -> ZOMBIE")
                hooks_changed = True
                continue

            # Check if hook is currently running
            if hook.status == "RUNNING" and hook.timestamp:
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
                    hooks_changed = True
                else:
                    # Still running, keep as is
                    updated_hooks.append(hook)
                continue

            # Keep non-running hooks as is
            updated_hooks.append(hook)

        # Update the HOOKS field in the file only if something changed
        if hooks_changed:
            update_changespec_hooks_field(
                changespec.file_path,
                changespec.name,
                updated_hooks,
            )

        return updates

    def _run_hook_status_cycle(self) -> int:
        """Run a quick hook status check cycle (no starting new hooks).

        Only checks if RUNNING hooks have completed.

        Returns:
            Number of hook state changes detected.
        """
        all_changespecs = find_all_changespecs()
        update_count = 0

        for changespec in all_changespecs:
            updates = self._check_hook_status_only(changespec)
            for update in updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")
                update_count += 1

        return update_count

    def _start_stale_hooks(
        self, changespec: ChangeSpec, last_diff_timestamp: str | None
    ) -> tuple[list[str], list[HookEntry]]:
        """Start stale hooks in background.

        Claims a workspace, runs bb_hg_update, starts hooks, and releases workspace.

        Args:
            changespec: The ChangeSpec to start hooks for.
            last_diff_timestamp: Timestamp to compare hooks against.

        Returns:
            Tuple of (update messages, list of started HookEntry objects).
        """
        updates: list[str] = []
        started_hooks: list[HookEntry] = []

        if not changespec.hooks:
            return updates, started_hooks

        # Don't run hooks for terminal statuses
        if changespec.status in ("Reverted", "Submitted"):
            return updates, started_hooks

        # Get project info
        project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

        # Always use workspace 100 for monitor hooks
        workspace_num = 100

        # Claim the workspace
        if not claim_workspace(
            changespec.file_path,
            workspace_num,
            "monitor(hooks)",
            changespec.name,
        ):
            self._log(
                f"Warning: Failed to claim workspace for hooks on {changespec.name}",
                style="yellow",
            )
            return updates, started_hooks

        try:
            # Get workspace directory
            workspace_dir, _ = get_workspace_directory_for_num(
                workspace_num, project_basename
            )

            if not os.path.isdir(workspace_dir):
                self._log(
                    f"Warning: Workspace directory not found: {workspace_dir}",
                    style="yellow",
                )
                return updates, started_hooks

            # Run bb_hg_update to switch to the ChangeSpec's branch
            try:
                result = subprocess.run(
                    ["bb_hg_update", changespec.name],
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )
                if result.returncode != 0:
                    self._log(
                        f"Warning: bb_hg_update failed for {changespec.name}: "
                        f"{result.stderr.strip()}",
                        style="yellow",
                    )
                    return updates, started_hooks
            except subprocess.TimeoutExpired:
                self._log(
                    f"Warning: bb_hg_update timed out for {changespec.name}",
                    style="yellow",
                )
                return updates, started_hooks
            except FileNotFoundError:
                self._log(
                    "Warning: bb_hg_update command not found",
                    style="yellow",
                )
                return updates, started_hooks

            # Start stale hooks in background
            for hook in changespec.hooks:
                # Only start hooks that need to run
                if not hook_needs_run(hook, last_diff_timestamp):
                    continue

                # Sleep 1 second between hooks to ensure unique timestamps
                if started_hooks:
                    time.sleep(1)

                # Start the hook in background
                updated_hook, _ = start_hook_background(changespec, hook, workspace_dir)
                started_hooks.append(updated_hook)

                updates.append(f"Hook '{hook.command}' -> RUNNING (started)")

        finally:
            # Always release the workspace
            release_workspace(
                changespec.file_path,
                workspace_num,
                "monitor(hooks)",
                changespec.name,
            )

        return updates, started_hooks

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
            - checked_types: List of what was checked (e.g., ["status", "presubmit"])
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

        # Check presubmit status
        should_check_pre, pre_skip_reason = self._should_check_presubmit(
            changespec, bypass_cache
        )
        if should_check_pre:
            checked_types.append("presubmit")
            presubmit_update = self._check_presubmit(changespec)
            if presubmit_update:
                updates.append(presubmit_update)
        elif pre_skip_reason:
            skip_reasons.append(f"presubmit: {pre_skip_reason}")

        return updates, checked_types, skip_reasons

    def _run_check_cycle(self, first_cycle: bool = False) -> int:
        """Run one check cycle across all ChangeSpecs.

        Args:
            first_cycle: If True, bypass cache for leaf CLs (CLs with no parent
                or submitted parents).

        Returns:
            Number of ChangeSpecs that were updated.
        """
        all_changespecs = find_all_changespecs()
        update_count = 0
        checked_count = 0
        skipped_count = 0

        for changespec in all_changespecs:
            # On first cycle, bypass cache for leaf CLs
            bypass_cache = first_cycle and self._is_leaf_cl(changespec)
            # For hooks, bypass cache on first cycle for ALL ChangeSpecs
            hooks_bypass_cache = first_cycle

            # First, determine what will be checked (before running checks)
            will_check_types = []
            skip_reasons = []

            should_check_stat, stat_skip_reason = self._should_check_status(
                changespec, bypass_cache
            )
            if should_check_stat:
                will_check_types.append("status")
            elif stat_skip_reason:
                skip_reasons.append(f"status: {stat_skip_reason}")

            should_check_pre, pre_skip_reason = self._should_check_presubmit(
                changespec, bypass_cache
            )
            if should_check_pre:
                will_check_types.append("presubmit")
            elif pre_skip_reason:
                skip_reasons.append(f"presubmit: {pre_skip_reason}")

            # Check if hooks need to run (runs for ALL ChangeSpecs, not just leaf CLs)
            should_check_hks, hks_skip_reason = self._should_check_hooks(
                changespec, hooks_bypass_cache
            )
            if should_check_hks:
                will_check_types.append("hooks")
            elif hks_skip_reason:
                skip_reasons.append(f"hooks: {hks_skip_reason}")

            if will_check_types:
                # Log BEFORE running checks
                checked_count += 1
                checked_str = ", ".join(will_check_types)
                self._log(f"Checking {changespec.name} ({checked_str})...", style="dim")

                # Now run the actual checks
                updates: list[str] = []
                if should_check_stat:
                    status_update = self._check_status(changespec)
                    if status_update:
                        updates.append(status_update)
                if should_check_pre:
                    presubmit_update = self._check_presubmit(changespec)
                    if presubmit_update:
                        updates.append(presubmit_update)
                if should_check_hks:
                    hook_updates = self._check_hooks(changespec)
                    updates.extend(hook_updates)

                for update in updates:
                    self._log(f"* {changespec.name}: {update}", style="green bold")
                    update_count += 1
            else:
                # Everything was skipped
                skipped_count += 1
                if self.verbose:
                    skip_str = "; ".join(skip_reasons)
                    self._log(f"Skipped {changespec.name} ({skip_str})", style="dim")

        self._log(
            f"Cycle complete: {checked_count} checked, {skipped_count} skipped, "
            f"{update_count} update(s)",
            style="green" if update_count > 0 else "dim",
        )

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
        """Run the continuous monitoring loop.

        Full checks (status, presubmit, hooks) run at interval_seconds (default 5m).
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
            f"GAI Monitor started - full checks every {interval_str}, "
            f"hook checks every {hook_interval_str} (Ctrl+C to exit)"
        )

        # Count initial changespecs
        initial_changespecs = find_all_changespecs()
        project_count = self._count_projects(initial_changespecs)
        self._log(
            f"Monitoring {len(initial_changespecs)} ChangeSpecs "
            f"across {project_count} project(s)"
        )

        try:
            first_cycle = True
            while True:
                if not first_cycle:
                    self._log("--- Full check cycle ---", style="dim")

                self._run_check_cycle(first_cycle=first_cycle)
                first_cycle = False

                # Between full cycles, run frequent hook status checks
                elapsed = 0
                while elapsed < self.interval_seconds:
                    time.sleep(self.hook_interval_seconds)
                    elapsed += self.hook_interval_seconds

                    # Check if we've reached the next full cycle
                    if elapsed >= self.interval_seconds:
                        break

                    # Run quick hook status check (only logs on state changes)
                    self._run_hook_status_cycle()

        except KeyboardInterrupt:
            self._log("Monitor stopped by user")
            return True
