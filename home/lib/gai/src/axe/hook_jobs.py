"""Hook job runner for short-interval hook cycle jobs.

This module handles the 1-second interval hook cycle jobs that check
completions, start hooks/mentors/workflows, and perform cleanup tasks.
"""

from collections.abc import Callable
from datetime import datetime

from ace.changespec import ChangeSpec
from ace.scheduler.checks_runner import check_pending_checks
from ace.scheduler.comments_handler import check_comment_zombies
from ace.scheduler.hook_checks import check_hooks
from ace.scheduler.mentor_checks import check_mentors
from ace.scheduler.orphan_cleanup import cleanup_orphaned_workspace_claims
from ace.scheduler.stale_running_cleanup import cleanup_stale_running_entries
from ace.scheduler.suffix_transforms import (
    acknowledge_terminal_status_markers,
    check_ready_to_mail,
    strip_old_entry_error_markers,
    transform_old_proposal_suffixes,
)
from ace.scheduler.workflows_runner import (
    check_and_complete_workflows,
    start_stale_workflows,
)
from gai_utils import EASTERN_TZ

from .runner_pool import RunnerPool
from .state import AxeMetrics

# Type alias for log callback
LogCallback = Callable[[str, str | None], None]


class HookJobRunner:
    """Runner for hook cycle jobs.

    Handles the short-interval (1 second) jobs that:
    - Check hook/mentor/workflow completions and start new ones
    - Poll for pending check results
    - Handle zombie comment entries
    - Run suffix transformations
    - Clean up orphaned workspace claims
    - Clean up stale RUNNING entries
    """

    def __init__(
        self,
        runner_pool: RunnerPool,
        metrics: AxeMetrics,
        zombie_timeout_seconds: int,
        max_runners: int,
        log_callback: LogCallback,
    ) -> None:
        """Initialize the hook job runner.

        Args:
            runner_pool: The runner pool for concurrency management.
            metrics: Metrics object for tracking statistics.
            zombie_timeout_seconds: Timeout in seconds for zombie detection.
            max_runners: Maximum concurrent runners allowed.
            log_callback: Callback function for logging messages.
        """
        self.runner_pool = runner_pool
        self.metrics = metrics
        self.zombie_timeout_seconds = zombie_timeout_seconds
        self.max_runners = max_runners
        self._log = log_callback

    def run_hook_checks(self, filtered_changespecs: list[ChangeSpec]) -> None:
        """Run hook completion and startup checks.

        Args:
            filtered_changespecs: List of changespecs to check.
        """
        self.runner_pool.reset_tick()

        for changespec in filtered_changespecs:
            if not changespec.hooks:
                continue

            hook_updates, hooks_started = check_hooks(
                changespec,
                self._log,
                self.zombie_timeout_seconds,
                self.max_runners,
                self.runner_pool.get_started_this_tick(),
            )

            self.runner_pool.add_started(hooks_started)
            self.metrics.hooks_started += hooks_started
            self.metrics.total_updates += len(hook_updates)

            for update in hook_updates:
                self._log(f"* {changespec.name}: {update}", "green bold")

    def run_mentor_checks(self, filtered_changespecs: list[ChangeSpec]) -> None:
        """Run mentor completion and startup checks.

        Args:
            filtered_changespecs: List of changespecs to check.
        """
        for changespec in filtered_changespecs:
            mentor_updates, mentors_started = check_mentors(
                changespec,
                self._log,
                self.zombie_timeout_seconds,
                self.max_runners,
                self.runner_pool.get_started_this_tick(),
            )

            self.runner_pool.add_started(mentors_started)
            self.metrics.mentors_started += mentors_started
            self.metrics.total_updates += len(mentor_updates)

            for update in mentor_updates:
                self._log(f"* {changespec.name}: {update}", "green bold")

    def run_workflow_checks(self, filtered_changespecs: list[ChangeSpec]) -> None:
        """Run CRS/fix-hook workflow checks.

        Args:
            filtered_changespecs: List of changespecs to check.
        """
        for changespec in filtered_changespecs:
            # Check completion of running workflows
            completion_updates = check_and_complete_workflows(changespec, self._log)
            self.metrics.total_updates += len(completion_updates)

            for update in completion_updates:
                self._log(f"* {changespec.name}: {update}", "green bold")

            # Start stale workflows
            start_updates, started, _ = start_stale_workflows(
                changespec,
                self._log,
                self.max_runners,
                self.runner_pool.get_started_this_tick(),
            )

            self.runner_pool.add_started(started)
            self.metrics.workflows_started += started
            self.metrics.total_updates += len(start_updates)

            for update in start_updates:
                self._log(f"* {changespec.name}: {update}", "green bold")

    def run_pending_checks_poll(self, filtered_changespecs: list[ChangeSpec]) -> None:
        """Poll for completed background checks.

        Args:
            filtered_changespecs: List of changespecs to check.
        """
        for changespec in filtered_changespecs:
            updates = check_pending_checks(changespec, self._log)
            self.metrics.total_updates += len(updates)

            for update in updates:
                self._log(f"* {changespec.name}: {update}", "green bold")

    def run_comment_zombie_checks(self, filtered_changespecs: list[ChangeSpec]) -> None:
        """Check for zombie comment entries.

        Args:
            filtered_changespecs: List of changespecs to check.
        """
        for changespec in filtered_changespecs:
            updates = check_comment_zombies(changespec, self.zombie_timeout_seconds)
            if updates:
                self.metrics.zombies_detected += len(updates)
                self.metrics.total_updates += len(updates)

                for update in updates:
                    self._log(f"* {changespec.name}: {update}", "yellow")

    def run_suffix_transforms(
        self, all_changespecs: list[ChangeSpec], filtered_changespecs: list[ChangeSpec]
    ) -> datetime:
        """Run suffix transformation checks.

        Args:
            all_changespecs: All changespecs (for ready-to-mail check).
            filtered_changespecs: List of filtered changespecs to transform.

        Returns:
            Timestamp of when the hook cycle completed.
        """
        for changespec in filtered_changespecs:
            updates: list[str] = []

            # Transform old proposal suffixes (!: -> ~:)
            updates.extend(transform_old_proposal_suffixes(changespec))

            # Strip error markers from old commit entry hooks
            updates.extend(strip_old_entry_error_markers(changespec))

            # Acknowledge terminal status attention markers
            updates.extend(acknowledge_terminal_status_markers(changespec))

            # Check if ChangeSpec is ready to mail
            updates.extend(check_ready_to_mail(changespec, all_changespecs))

            self.metrics.total_updates += len(updates)

            for update in updates:
                self._log(f"* {changespec.name}: {update}", "green bold")

        return datetime.now(EASTERN_TZ)

    def run_orphan_cleanup(self, all_changespecs: list[ChangeSpec]) -> None:
        """Clean up orphaned workspace claims for reverted CLs.

        Args:
            all_changespecs: All changespecs to check for orphans.
        """
        released = cleanup_orphaned_workspace_claims(all_changespecs, self._log)
        if released > 0:
            self.metrics.total_updates += released

    def run_stale_running_cleanup(self) -> None:
        """Clean up stale RUNNING entries for dead processes."""
        released = cleanup_stale_running_entries(self._log)
        if released > 0:
            self.metrics.stale_running_cleaned += released
            self.metrics.total_updates += released
