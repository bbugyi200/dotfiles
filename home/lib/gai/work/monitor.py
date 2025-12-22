"""Monitor workflow for continuously checking ChangeSpec status updates."""

import os
import sys
import time
from datetime import datetime

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import remove_workspace_suffix, transition_changespec_status

from .changespec import ChangeSpec, find_all_changespecs
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
from .sync_cache import clear_cache_entry, should_check, update_last_checked


class MonitorWorkflow:
    """Continuously monitors all ChangeSpecs for status updates."""

    def __init__(self, interval_seconds: int = 300, verbose: bool = False) -> None:
        """Initialize the monitor workflow.

        Args:
            interval_seconds: Polling interval in seconds (default: 300 = 5 minutes)
            verbose: If True, show skipped ChangeSpecs in output (default: False)
        """
        self.interval_seconds = interval_seconds
        self.verbose = verbose
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

            if will_check_types:
                # Log BEFORE running checks
                checked_count += 1
                checked_str = ", ".join(will_check_types)
                self._log(f"Checking {changespec.name} ({checked_str})...", style="dim")

                # Now run the actual checks
                updates = []
                if should_check_stat:
                    status_update = self._check_status(changespec)
                    if status_update:
                        updates.append(status_update)
                if should_check_pre:
                    presubmit_update = self._check_presubmit(changespec)
                    if presubmit_update:
                        updates.append(presubmit_update)

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

        Returns:
            True if exited normally, False on error.
        """
        # Print startup info
        interval_str = (
            f"{self.interval_seconds // 60} minutes"
            if self.interval_seconds >= 60
            else f"{self.interval_seconds} seconds"
        )
        self._log(
            f"GAI Monitor started - checking every {interval_str} (Ctrl+C to exit)"
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
                    self._log("--- Next check cycle ---", style="dim")

                self._run_check_cycle(first_cycle=first_cycle)
                first_cycle = False

                # Sleep until next cycle
                time.sleep(self.interval_seconds)

        except KeyboardInterrupt:
            self._log("Monitor stopped by user")
            return True
