"""Check cycle runner for full and comment check cycles.

This module handles the longer-interval check cycles (1-5 minutes) that
start CL submitted checks and comment checks for ChangeSpecs.
"""

import time
from collections.abc import Callable
from datetime import datetime

from ace.changespec import (
    ChangeSpec,
    find_all_changespecs,
    get_base_status,
)
from ace.cl_status import is_parent_submitted
from ace.comments import is_timestamp_suffix
from ace.query import QueryExpr, evaluate_query
from ace.scheduler.checks_runner import (
    CHECK_TYPE_CL_SUBMITTED,
    CHECK_TYPE_REVIEWER_COMMENTS,
    has_pending_check,
    start_cl_submitted_check,
    start_reviewer_comments_check,
)
from ace.sync_cache import should_check, update_last_checked
from gai_utils import EASTERN_TZ
from running_field import get_workspace_directory

from .state import CycleResult, write_cycle_result

# Type alias for log callback
LogCallback = Callable[[str, str | None], None]


class CheckCycleRunner:
    """Runner for full and comment check cycles.

    Handles the longer-interval check cycles that:
    - Start CL submitted checks (full cycle)
    - Start reviewer/author comment checks (comment cycle)
    """

    def __init__(
        self,
        parsed_query: QueryExpr | None,
        log_callback: LogCallback,
    ) -> None:
        """Initialize the check cycle runner.

        Args:
            parsed_query: Parsed query for filtering ChangeSpecs (or None for all).
            log_callback: Callback function for logging messages.
        """
        self.parsed_query = parsed_query
        self._log = log_callback
        self._first_cycle = True

    def set_first_cycle_done(self) -> None:
        """Mark the first cycle as completed."""
        self._first_cycle = False

    def is_first_cycle(self) -> bool:
        """Check if this is still the first cycle."""
        return self._first_cycle

    def get_all_changespecs(self) -> list[ChangeSpec]:
        """Get all changespecs (unfiltered)."""
        return find_all_changespecs()

    def get_filtered_changespecs(
        self, all_changespecs: list[ChangeSpec] | None = None
    ) -> list[ChangeSpec]:
        """Get all changespecs filtered by query.

        Args:
            all_changespecs: Optional pre-fetched list of all changespecs.

        Returns:
            List of changespecs matching the query filter.
        """
        if all_changespecs is None:
            all_changespecs = find_all_changespecs()

        if not self.parsed_query:
            return all_changespecs

        return [
            cs
            for cs in all_changespecs
            if evaluate_query(self.parsed_query, cs, all_changespecs)
        ]

    def is_leaf_cl(self, changespec: ChangeSpec) -> bool:
        """Check if a ChangeSpec is a leaf CL (no parent or parent is submitted)."""
        return is_parent_submitted(changespec)

    def should_check_status(
        self, changespec: ChangeSpec, bypass_cache: bool = False
    ) -> bool:
        """Determine if a ChangeSpec's status should be checked.

        Uses sync_cache to throttle checks to minimum 5-minute intervals.

        Args:
            changespec: The ChangeSpec to check.
            bypass_cache: If True, skip the cache check.

        Returns:
            True if the ChangeSpec should be checked, False otherwise.
        """
        if bypass_cache:
            return True
        return should_check(changespec.name)

    def run_full_check_cycle(self) -> tuple[datetime, int, list[dict]]:
        """Run full status check cycle - starts CL submitted checks only.

        Returns:
            Tuple of (cycle_timestamp, changespecs_processed, updates_list).
        """
        start = time.time()
        all_changespecs = self.get_all_changespecs()
        filtered_changespecs = self.get_filtered_changespecs(all_changespecs)
        updates: list[dict] = []

        for changespec in filtered_changespecs:
            # On first cycle, bypass cache for leaf CLs
            bypass_cache = self._first_cycle and self.is_leaf_cl(changespec)

            # Start CL submitted checks only
            check_updates = self._start_cl_submitted_check(changespec, bypass_cache)
            for update in check_updates:
                updates.append({"changespec": changespec.name, "message": update})
                self._log(f"* {changespec.name}: {update}", "green bold")

        cycle_timestamp = datetime.now(EASTERN_TZ)
        self._first_cycle = False

        # Write cycle result
        duration_ms = int((time.time() - start) * 1000)
        result = CycleResult(
            timestamp=cycle_timestamp.isoformat(),
            cycle_type="full",
            duration_ms=duration_ms,
            changespecs_processed=len(filtered_changespecs),
            updates=updates,
            errors=[],
        )
        write_cycle_result(result)

        if updates:
            self._log(f"Full cycle complete: {len(updates)} update(s)", "green")

        return cycle_timestamp, len(filtered_changespecs), updates

    def run_comment_check_cycle(self) -> tuple[datetime, int, list[dict]]:
        """Run comment check cycle - starts reviewer/author comment checks.

        Returns:
            Tuple of (cycle_timestamp, changespecs_processed, updates_list).
        """
        start = time.time()
        all_changespecs = self.get_all_changespecs()
        filtered_changespecs = self.get_filtered_changespecs(all_changespecs)
        updates: list[dict] = []

        for changespec in filtered_changespecs:
            # Start comment checks (no cache throttling - has its own interval)
            check_updates = self._start_comment_checks(changespec)
            for update in check_updates:
                updates.append({"changespec": changespec.name, "message": update})
                self._log(f"* {changespec.name}: {update}", "green bold")

        cycle_timestamp = datetime.now(EASTERN_TZ)

        # Write cycle result
        duration_ms = int((time.time() - start) * 1000)
        result = CycleResult(
            timestamp=cycle_timestamp.isoformat(),
            cycle_type="comment",
            duration_ms=duration_ms,
            changespecs_processed=len(filtered_changespecs),
            updates=updates,
            errors=[],
        )
        write_cycle_result(result)

        if updates:
            self._log(f"Comment cycle complete: {len(updates)} update(s)", "green")

        return cycle_timestamp, len(filtered_changespecs), updates

    def _start_cl_submitted_check(
        self, changespec: ChangeSpec, bypass_cache: bool = False
    ) -> list[str]:
        """Start CL submitted check for a ChangeSpec (non-blocking).

        Args:
            changespec: The ChangeSpec to check.
            bypass_cache: If True, skip the cache check.

        Returns:
            List of update messages for checks that were started.
        """
        updates: list[str] = []

        # Get workspace directory
        try:
            workspace_dir = get_workspace_directory(changespec.project_basename)
        except RuntimeError:
            workspace_dir = None

        # Check if we should run status checks
        if not self.should_check_status(changespec, bypass_cache):
            return updates

        # Update cache when starting checks
        update_last_checked(changespec.name)

        # Start CL submitted check if not already pending
        if not has_pending_check(changespec, CHECK_TYPE_CL_SUBMITTED):
            if is_parent_submitted(changespec) and changespec.cl:
                update = start_cl_submitted_check(changespec, workspace_dir, self._log)
                if update:
                    updates.append(update)

        return updates

    def _start_comment_checks(self, changespec: ChangeSpec) -> list[str]:
        """Start reviewer comment checks for a ChangeSpec (non-blocking).

        Comment checks bypass the sync_cache since they have their own interval.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            List of update messages for checks that were started.
        """
        updates: list[str] = []

        # Get workspace directory
        try:
            workspace_dir = get_workspace_directory(changespec.project_basename)
        except RuntimeError:
            workspace_dir = None

        if not workspace_dir:
            return updates

        # Start reviewer comments check if conditions are met
        if not has_pending_check(changespec, CHECK_TYPE_REVIEWER_COMMENTS):
            if (
                is_parent_submitted(changespec)
                and get_base_status(changespec.status) == "Mailed"
            ):
                # Check if we need to start
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

        return updates
