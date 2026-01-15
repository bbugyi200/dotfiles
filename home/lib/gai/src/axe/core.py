"""Core AxeScheduler class for schedule-based ChangeSpec monitoring.

This module provides the main scheduler that uses the `schedule` library
to run checks at different intervals, replacing the nested loop structure
of gai loop.
"""

import os
import signal
import sys
import time
import traceback
from collections.abc import Callable
from datetime import datetime

import schedule
from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ace.changespec import (
    ChangeSpec,
    find_all_changespecs,
    get_base_status,
)
from ace.cl_status import is_parent_submitted
from ace.comments import is_timestamp_suffix
from ace.constants import DEFAULT_ZOMBIE_TIMEOUT_SECONDS
from ace.loop.checks_runner import (
    CHECK_TYPE_AUTHOR_COMMENTS,
    CHECK_TYPE_CL_SUBMITTED,
    CHECK_TYPE_REVIEWER_COMMENTS,
    check_pending_checks,
    has_pending_check,
    start_author_comments_check,
    start_cl_submitted_check,
    start_reviewer_comments_check,
)
from ace.loop.comments_handler import check_comment_zombies
from ace.loop.core import cleanup_orphaned_workspace_claims
from ace.loop.hook_checks import check_hooks
from ace.loop.mentor_checks import check_mentors
from ace.loop.suffix_transforms import (
    acknowledge_terminal_status_markers,
    check_ready_to_mail,
    strip_old_entry_error_markers,
    transform_old_proposal_suffixes,
)
from ace.loop.workflows_runner import (
    check_and_complete_workflows,
    start_stale_workflows,
)
from ace.query import QueryExpr, evaluate_query, parse_query
from ace.sync_cache import should_check, update_last_checked
from gai_utils import EASTERN_TZ
from running_field import get_workspace_directory

from .runner_pool import RunnerPool
from .state import (
    AxeMetrics,
    AxeStatus,
    CycleResult,
    append_error,
    get_timestamp,
    remove_pid_file,
    write_cycle_result,
    write_metrics,
    write_pid_file,
    write_status,
)

# Type alias for log callback
LogCallback = Callable[[str, str | None], None]


class AxeScheduler:
    """Schedule-based daemon for continuous ChangeSpec monitoring.

    Uses the `schedule` library to run checks at different intervals:
    - Full check cycle: Starts pending CL/comment checks (default: 5 minutes)
    - Hook cycle jobs: Check completions, start hooks/mentors/workflows (default: 1 second)
    - Status update: Write status to disk for TUI visibility (every 5 seconds)
    """

    def __init__(
        self,
        full_check_interval: int = 300,
        hook_interval: int = 1,
        zombie_timeout_seconds: int = DEFAULT_ZOMBIE_TIMEOUT_SECONDS,
        max_runners: int = 5,
        query: str = "",
    ) -> None:
        """Initialize the axe scheduler.

        Args:
            full_check_interval: Full check interval in seconds (default: 300 = 5 minutes).
            hook_interval: Hook check interval in seconds (default: 1).
            zombie_timeout_seconds: Zombie detection timeout in seconds (default: 2 hours).
            max_runners: Maximum concurrent runners globally (default: 5).
            query: Query string for filtering ChangeSpecs (empty = all ChangeSpecs).

        Raises:
            QueryParseError: If the query string is invalid.
        """
        self.full_check_interval = full_check_interval
        self.hook_interval = hook_interval
        self.zombie_timeout_seconds = zombie_timeout_seconds
        self.max_runners = max_runners
        self.query = query
        self.parsed_query: QueryExpr | None = None
        if query:
            self.parsed_query = parse_query(query)

        self.console = Console()
        self.scheduler = schedule.Scheduler()
        self.runner_pool = RunnerPool(max_runners)

        self._start_time = datetime.now(EASTERN_TZ)
        self._last_full_cycle: datetime | None = None
        self._last_hook_cycle: datetime | None = None
        self._first_cycle = True
        self._running = True

        # Metrics tracking
        self._metrics = AxeMetrics()

    def _log(self, message: str, style: str | None = None) -> None:
        """Print a timestamped log message.

        Args:
            message: The message to print.
            style: Optional rich style to apply (e.g., "dim", "green", "yellow").
        """
        timestamp = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{timestamp}] {message}"

        if style:
            self.console.print(f"[{style}]{full_message}[/{style}]")
        else:
            self.console.print(full_message)

    def _get_all_changespecs(self) -> list[ChangeSpec]:
        """Get all changespecs (unfiltered)."""
        return find_all_changespecs()

    def _get_filtered_changespecs(
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

    def _setup_jobs(self) -> None:
        """Configure all scheduled jobs."""
        # Full cycle (status checks) - runs at full_check_interval
        self.scheduler.every(self.full_check_interval).seconds.do(
            self._safe_run_job, self._run_full_check_cycle, "full_cycle"
        ).tag("full_cycle")

        # Hook cycle jobs - all run at hook_interval
        self.scheduler.every(self.hook_interval).seconds.do(
            self._safe_run_job, self._run_hook_checks, "hooks"
        ).tag("hook_cycle", "hooks")

        self.scheduler.every(self.hook_interval).seconds.do(
            self._safe_run_job, self._run_mentor_checks, "mentors"
        ).tag("hook_cycle", "mentors")

        self.scheduler.every(self.hook_interval).seconds.do(
            self._safe_run_job, self._run_workflow_checks, "workflows"
        ).tag("hook_cycle", "workflows")

        self.scheduler.every(self.hook_interval).seconds.do(
            self._safe_run_job, self._run_pending_checks_poll, "pending_checks"
        ).tag("hook_cycle", "pending_checks")

        self.scheduler.every(self.hook_interval).seconds.do(
            self._safe_run_job, self._run_comment_zombie_checks, "comments"
        ).tag("hook_cycle", "comments")

        self.scheduler.every(self.hook_interval).seconds.do(
            self._safe_run_job, self._run_suffix_transforms, "transforms"
        ).tag("hook_cycle", "transforms")

        self.scheduler.every(self.hook_interval).seconds.do(
            self._safe_run_job, self._run_orphan_cleanup, "orphan_cleanup"
        ).tag("hook_cycle", "orphan_cleanup")

        # Status update job (every 5s)
        self.scheduler.every(5).seconds.do(
            self._safe_run_job, self._update_status_file, "status_update"
        ).tag("status")

        # Metrics update job (every 30s)
        self.scheduler.every(30).seconds.do(
            self._safe_run_job, self._update_metrics_file, "metrics_update"
        ).tag("metrics")

    def _safe_run_job(self, job_func: Callable[[], None], job_name: str) -> None:
        """Wrap job execution with error handling.

        Args:
            job_func: The job function to run.
            job_name: Name of the job for logging.
        """
        try:
            job_func()
        except Exception as e:
            self._handle_job_error(job_name, e)

    def _handle_job_error(self, job_name: str, error: Exception) -> None:
        """Handle errors in scheduled jobs.

        Args:
            job_name: Name of the job that failed.
            error: The exception that was raised.
        """
        self._log(f"Error in {job_name}: {error}", style="red")
        self._metrics.errors_encountered += 1

        # Write error to state for TUI visibility
        error_info = {
            "timestamp": get_timestamp(),
            "job": job_name,
            "error": str(error),
            "traceback": traceback.format_exc(),
        }
        append_error(error_info)

    def _is_leaf_cl(self, changespec: ChangeSpec) -> bool:
        """Check if a ChangeSpec is a leaf CL (no parent or parent is submitted)."""
        return is_parent_submitted(changespec)

    def _should_check_status(
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

    def _run_full_check_cycle(self) -> None:
        """Run full status check cycle - starts pending CL/comment checks."""
        start = time.time()
        all_changespecs = self._get_all_changespecs()
        filtered_changespecs = self._get_filtered_changespecs(all_changespecs)
        updates: list[dict] = []

        for changespec in filtered_changespecs:
            # On first cycle, bypass cache for leaf CLs
            bypass_cache = self._first_cycle and self._is_leaf_cl(changespec)

            # Start pending checks
            check_updates = self._start_pending_checks(changespec, bypass_cache)
            for update in check_updates:
                updates.append({"changespec": changespec.name, "message": update})
                self._log(f"* {changespec.name}: {update}", style="green bold")

        self._last_full_cycle = datetime.now(EASTERN_TZ)
        self._first_cycle = False
        self._metrics.full_cycles_run += 1
        self._metrics.total_updates += len(updates)

        # Write cycle result
        duration_ms = int((time.time() - start) * 1000)
        result = CycleResult(
            timestamp=self._last_full_cycle.isoformat(),
            cycle_type="full",
            duration_ms=duration_ms,
            changespecs_processed=len(filtered_changespecs),
            updates=updates,
            errors=[],
        )
        write_cycle_result(result)

        if updates:
            self._log(f"Full cycle complete: {len(updates)} update(s)", style="green")

    def _start_pending_checks(
        self, changespec: ChangeSpec, bypass_cache: bool = False
    ) -> list[str]:
        """Start background checks for a ChangeSpec (non-blocking).

        Args:
            changespec: The ChangeSpec to check.
            bypass_cache: If True, skip the cache check.

        Returns:
            List of update messages for checks that were started.
        """
        updates: list[str] = []

        # Get workspace directory (needed for all checks)
        try:
            workspace_dir = get_workspace_directory(changespec.project_basename)
        except RuntimeError:
            workspace_dir = None

        # Check if we should run status checks
        if not self._should_check_status(changespec, bypass_cache):
            return updates

        # Update cache when starting checks
        update_last_checked(changespec.name)

        # Start CL submitted check if not already pending
        if not has_pending_check(changespec, CHECK_TYPE_CL_SUBMITTED):
            if is_parent_submitted(changespec) and changespec.cl:
                update = start_cl_submitted_check(changespec, workspace_dir, self._log)
                if update:
                    updates.append(update)

        # Start reviewer comments check if conditions are met
        if not has_pending_check(changespec, CHECK_TYPE_REVIEWER_COMMENTS):
            if (
                is_parent_submitted(changespec)
                and get_base_status(changespec.status) == "Mailed"
                and workspace_dir
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

        # Start author comments check if conditions are met
        if not has_pending_check(changespec, CHECK_TYPE_AUTHOR_COMMENTS):
            if (
                get_base_status(changespec.status) in ("Drafted", "Mailed")
                and workspace_dir
            ):
                # Skip if any [critique] entry exists
                has_reviewer = False
                if changespec.comments:
                    for entry in changespec.comments:
                        if entry.reviewer == "critique":
                            has_reviewer = True
                            break
                if not has_reviewer:
                    # Check if we need to start
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

    def _run_hook_checks(self) -> None:
        """Run hook completion and startup checks."""
        self.runner_pool.reset_tick()
        all_changespecs = self._get_all_changespecs()
        filtered_changespecs = self._get_filtered_changespecs(all_changespecs)

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
            self._metrics.hooks_started += hooks_started
            self._metrics.total_updates += len(hook_updates)

            for update in hook_updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")

    def _run_mentor_checks(self) -> None:
        """Run mentor completion and startup checks."""
        all_changespecs = self._get_all_changespecs()
        filtered_changespecs = self._get_filtered_changespecs(all_changespecs)

        for changespec in filtered_changespecs:
            mentor_updates, mentors_started = check_mentors(
                changespec,
                self._log,
                self.zombie_timeout_seconds,
                self.max_runners,
                self.runner_pool.get_started_this_tick(),
            )

            self.runner_pool.add_started(mentors_started)
            self._metrics.mentors_started += mentors_started
            self._metrics.total_updates += len(mentor_updates)

            for update in mentor_updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")

    def _run_workflow_checks(self) -> None:
        """Run CRS/fix-hook workflow checks."""
        all_changespecs = self._get_all_changespecs()
        filtered_changespecs = self._get_filtered_changespecs(all_changespecs)

        for changespec in filtered_changespecs:
            # Check completion of running workflows
            completion_updates = check_and_complete_workflows(changespec, self._log)
            self._metrics.total_updates += len(completion_updates)

            for update in completion_updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")

            # Start stale workflows
            start_updates, started, _ = start_stale_workflows(
                changespec,
                self._log,
                self.max_runners,
                self.runner_pool.get_started_this_tick(),
            )

            self.runner_pool.add_started(started)
            self._metrics.workflows_started += started
            self._metrics.total_updates += len(start_updates)

            for update in start_updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")

    def _run_pending_checks_poll(self) -> None:
        """Poll for completed background checks."""
        all_changespecs = self._get_all_changespecs()
        filtered_changespecs = self._get_filtered_changespecs(all_changespecs)

        for changespec in filtered_changespecs:
            updates = check_pending_checks(changespec, self._log)
            self._metrics.total_updates += len(updates)

            for update in updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")

    def _run_comment_zombie_checks(self) -> None:
        """Check for zombie comment entries."""
        all_changespecs = self._get_all_changespecs()
        filtered_changespecs = self._get_filtered_changespecs(all_changespecs)

        for changespec in filtered_changespecs:
            updates = check_comment_zombies(changespec, self.zombie_timeout_seconds)
            if updates:
                self._metrics.zombies_detected += len(updates)
                self._metrics.total_updates += len(updates)

                for update in updates:
                    self._log(f"* {changespec.name}: {update}", style="yellow")

    def _run_suffix_transforms(self) -> None:
        """Run suffix transformation checks."""
        all_changespecs = self._get_all_changespecs()
        filtered_changespecs = self._get_filtered_changespecs(all_changespecs)

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

            self._metrics.total_updates += len(updates)

            for update in updates:
                self._log(f"* {changespec.name}: {update}", style="green bold")

        self._last_hook_cycle = datetime.now(EASTERN_TZ)
        self._metrics.hook_cycles_run += 1

    def _run_orphan_cleanup(self) -> None:
        """Clean up orphaned workspace claims for reverted CLs."""
        all_changespecs = self._get_all_changespecs()
        released = cleanup_orphaned_workspace_claims(all_changespecs, self._log)
        if released > 0:
            self._metrics.total_updates += released

    def _update_status_file(self) -> None:
        """Update status file for TUI visibility."""
        now = datetime.now(EASTERN_TZ)
        uptime = int((now - self._start_time).total_seconds())
        all_cs = self._get_all_changespecs()
        filtered_cs = self._get_filtered_changespecs(all_cs)

        next_full = None
        if self._last_full_cycle:
            next_time = self._last_full_cycle.timestamp() + self.full_check_interval
            next_full = datetime.fromtimestamp(next_time, EASTERN_TZ).isoformat()

        status = AxeStatus(
            pid=os.getpid(),
            started_at=self._start_time.isoformat(),
            status="running",
            full_check_interval=self.full_check_interval,
            hook_interval=self.hook_interval,
            max_runners=self.max_runners,
            query=self.query,
            zombie_timeout=self.zombie_timeout_seconds,
            current_runners=self.runner_pool.get_current_runners(),
            last_full_cycle=(
                self._last_full_cycle.isoformat() if self._last_full_cycle else None
            ),
            last_hook_cycle=(
                self._last_hook_cycle.isoformat() if self._last_hook_cycle else None
            ),
            next_full_cycle=next_full,
            total_changespecs=len(all_cs),
            filtered_changespecs=len(filtered_cs),
            uptime_seconds=uptime,
        )
        write_status(status)

    def _update_metrics_file(self) -> None:
        """Update metrics file for TUI visibility."""
        write_metrics(self._metrics)

    def _handle_shutdown(self, _signum: int, _frame: object) -> None:
        """Handle shutdown signal (SIGTERM)."""
        self._log("Received shutdown signal, stopping...")
        self._running = False

    def run(self) -> bool:
        """Run the scheduler main loop.

        Returns:
            True if exited normally, False on error.
        """
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        # Write PID file
        write_pid_file()

        # Set up jobs
        self._setup_jobs()

        # Log startup
        self._log(f"gai axe started (PID: {os.getpid()})")
        interval_str = (
            f"{self.full_check_interval // 60} minutes"
            if self.full_check_interval >= 60
            else f"{self.full_check_interval} seconds"
        )
        hook_str = f"{self.hook_interval} second(s)"
        self._log(
            f"Full cycle: {interval_str}, Hook cycle: {hook_str}, "
            f"Max runners: {self.max_runners}"
        )
        if self.query:
            self._log(f"Query filter: {self.query}")

        # Count initial changespecs
        initial = self._get_all_changespecs()
        filtered = self._get_filtered_changespecs(initial)
        self._log(f"Monitoring {len(filtered)} ChangeSpecs")

        # Write initial status
        self._update_status_file()

        # Run first full cycle immediately
        self._run_full_check_cycle()

        try:
            while self._running:
                self.scheduler.run_pending()
                time.sleep(0.1)  # 100ms polling interval
        except KeyboardInterrupt:
            self._log("Shutting down...")
        finally:
            remove_pid_file()
            self._log("gai axe stopped")

        return True
