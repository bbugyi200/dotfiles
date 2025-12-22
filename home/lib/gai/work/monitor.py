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

    def __init__(self, interval_seconds: int = 300) -> None:
        """Initialize the monitor workflow.

        Args:
            interval_seconds: Polling interval in seconds (default: 300 = 5 minutes)
        """
        self.interval_seconds = interval_seconds
        self.console = Console()

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

    def _check_presubmit(self, changespec: ChangeSpec) -> str | None:
        """Check presubmit status for a ChangeSpec.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            Update message if presubmit was updated, None otherwise.
        """
        # Only check if presubmit needs checking
        if not presubmit_needs_check(changespec.presubmit):
            return None

        # Check if enough time has passed
        cache_key = f"presubmit:{changespec.name}"
        if not should_check(cache_key):
            return None

        # Update the last_checked timestamp
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

    def _check_status(self, changespec: ChangeSpec) -> str | None:
        """Check CL submission and comment status for a ChangeSpec.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            Update message if status was updated, None otherwise.
        """
        # Only check syncable statuses
        base_status = remove_workspace_suffix(changespec.status)
        if base_status not in SYNCABLE_STATUSES:
            return None

        # Check if enough time has passed
        if not should_check(changespec.name):
            return None

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

    def _check_single_changespec(self, changespec: ChangeSpec) -> list[str]:
        """Check a single ChangeSpec for updates.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            List of update messages (empty if no updates).
        """
        updates = []

        # Check status (submission/comments)
        status_update = self._check_status(changespec)
        if status_update:
            updates.append(status_update)

        # Check presubmit status
        presubmit_update = self._check_presubmit(changespec)
        if presubmit_update:
            updates.append(presubmit_update)

        return updates

    def _run_check_cycle(self) -> int:
        """Run one check cycle across all ChangeSpecs.

        Returns:
            Number of ChangeSpecs that were updated.
        """
        all_changespecs = find_all_changespecs()
        update_count = 0

        for changespec in all_changespecs:
            self._log(f"Checking {changespec.name}...", style="dim")

            updates = self._check_single_changespec(changespec)
            for update in updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")
                update_count += 1

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
                first_cycle = False

                update_count = self._run_check_cycle()

                if update_count > 0:
                    self._log(
                        f"Cycle complete: {update_count} update(s)", style="green"
                    )
                else:
                    self._log("Cycle complete: no updates", style="dim")

                # Sleep until next cycle
                time.sleep(self.interval_seconds)

        except KeyboardInterrupt:
            self._log("Monitor stopped by user")
            return True
