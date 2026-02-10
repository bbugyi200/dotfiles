"""Core AxeScheduler class for schedule-based ChangeSpec monitoring.

This module provides the main scheduler that uses the `schedule` library
to run checks at different intervals for automatic hook execution, CL status
updates, and workflow management.
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

from ace.constants import DEFAULT_ZOMBIE_TIMEOUT_SECONDS
from ace.query import QueryExpr, parse_query
from gai_utils import EASTERN_TZ

from .check_cycles import CheckCycleRunner
from .hook_jobs import HookJobRunner
from .runner_pool import RunnerPool
from .state import (
    AXE_STATE_DIR,
    AxeMetrics,
    AxeStatus,
    append_error,
    get_timestamp,
    remove_pid_file,
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
        comment_check_interval: int = 60,
    ) -> None:
        """Initialize the axe scheduler.

        Args:
            full_check_interval: Full check interval in seconds (default: 300 = 5 minutes).
            hook_interval: Hook check interval in seconds (default: 1).
            zombie_timeout_seconds: Zombie detection timeout in seconds (default: 2 hours).
            max_runners: Maximum concurrent runners globally (default: 5).
            query: Query string for filtering ChangeSpecs (empty = all ChangeSpecs).
            comment_check_interval: Comment check interval in seconds (default: 60 = 1 minute).

        Raises:
            QueryParseError: If the query string is invalid.
        """
        self.full_check_interval = full_check_interval
        self.hook_interval = hook_interval
        self.comment_check_interval = comment_check_interval
        self.zombie_timeout_seconds = zombie_timeout_seconds
        self.max_runners = max_runners
        self.query = query
        self.parsed_query: QueryExpr | None = None
        if query:
            self.parsed_query = parse_query(query)

        # Use record=True and force_terminal=True to capture styled output
        self.console = Console(record=True, force_terminal=True)
        self.scheduler = schedule.Scheduler()
        self.runner_pool = RunnerPool(max_runners)

        # Output log file for TUI display
        self._log_file_path = AXE_STATE_DIR / "logs" / "output.log"

        self._start_time = datetime.now(EASTERN_TZ)
        self._last_full_cycle: datetime | None = None
        self._last_hook_cycle: datetime | None = None
        self._last_comment_cycle: datetime | None = None
        self._running = True

        # Metrics tracking
        self._metrics = AxeMetrics()

        # Create helper instances for delegation
        self._check_runner = CheckCycleRunner(self.parsed_query, self._log)
        self._hook_runner = HookJobRunner(
            self.runner_pool,
            self._metrics,
            self.zombie_timeout_seconds,
            self.max_runners,
            self._log,
        )

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

        # Flush recorded output to log file
        self._flush_log_to_file()

    def _flush_log_to_file(self) -> None:
        """Append recorded console output to log file with ANSI codes."""
        text = self.console.export_text(styles=True, clear=True)
        if not text.strip():
            return

        # Ensure log directory exists
        self._log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to log file
        with open(self._log_file_path, "a") as f:
            f.write(text)

    def _setup_jobs(self) -> None:
        """Configure all scheduled jobs."""
        # Full cycle (CL submitted checks) - runs at full_check_interval
        self.scheduler.every(self.full_check_interval).seconds.do(
            self._safe_run_job, self._run_full_check_cycle, "full_cycle"
        ).tag("full_cycle")

        # Comment cycle (reviewer/author comment checks) - runs at comment_check_interval
        self.scheduler.every(self.comment_check_interval).seconds.do(
            self._safe_run_job, self._run_comment_check_cycle, "comment_cycle"
        ).tag("comment_cycle")

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

        # Stale RUNNING entry cleanup (every full_check_interval)
        self.scheduler.every(self.full_check_interval).seconds.do(
            self._safe_run_job, self._run_stale_running_cleanup, "stale_running_cleanup"
        ).tag("full_cycle", "stale_running_cleanup")

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

    def _run_full_check_cycle(self) -> None:
        """Run full status check cycle - starts CL submitted checks only."""
        cycle_timestamp, _, updates = self._check_runner.run_full_check_cycle()
        self._last_full_cycle = cycle_timestamp
        self._metrics.full_cycles_run += 1
        self._metrics.total_updates += len(updates)

    def _run_comment_check_cycle(self) -> None:
        """Run comment check cycle - starts reviewer/author comment checks."""
        cycle_timestamp, _, updates = self._check_runner.run_comment_check_cycle()
        self._last_comment_cycle = cycle_timestamp
        self._metrics.total_updates += len(updates)

    def _run_hook_checks(self) -> None:
        """Run hook completion and startup checks."""
        all_changespecs = self._check_runner.get_all_changespecs()
        filtered_changespecs = self._check_runner.get_filtered_changespecs(
            all_changespecs
        )
        self._hook_runner.run_hook_checks(filtered_changespecs)

    def _run_mentor_checks(self) -> None:
        """Run mentor completion and startup checks."""
        all_changespecs = self._check_runner.get_all_changespecs()
        filtered_changespecs = self._check_runner.get_filtered_changespecs(
            all_changespecs
        )
        self._hook_runner.run_mentor_checks(filtered_changespecs)

    def _run_workflow_checks(self) -> None:
        """Run CRS/fix-hook workflow checks."""
        all_changespecs = self._check_runner.get_all_changespecs()
        filtered_changespecs = self._check_runner.get_filtered_changespecs(
            all_changespecs
        )
        self._hook_runner.run_workflow_checks(filtered_changespecs)

    def _run_pending_checks_poll(self) -> None:
        """Poll for completed background checks."""
        all_changespecs = self._check_runner.get_all_changespecs()
        filtered_changespecs = self._check_runner.get_filtered_changespecs(
            all_changespecs
        )
        self._hook_runner.run_pending_checks_poll(filtered_changespecs)

    def _run_comment_zombie_checks(self) -> None:
        """Check for zombie comment entries."""
        all_changespecs = self._check_runner.get_all_changespecs()
        filtered_changespecs = self._check_runner.get_filtered_changespecs(
            all_changespecs
        )
        self._hook_runner.run_comment_zombie_checks(filtered_changespecs)

    def _run_suffix_transforms(self) -> None:
        """Run suffix transformation checks."""
        all_changespecs = self._check_runner.get_all_changespecs()
        filtered_changespecs = self._check_runner.get_filtered_changespecs(
            all_changespecs
        )
        self._last_hook_cycle = self._hook_runner.run_suffix_transforms(
            all_changespecs, filtered_changespecs
        )
        self._metrics.hook_cycles_run += 1

    def _run_orphan_cleanup(self) -> None:
        """Clean up orphaned workspace claims for reverted CLs."""
        all_changespecs = self._check_runner.get_all_changespecs()
        self._hook_runner.run_orphan_cleanup(all_changespecs)

    def _run_stale_running_cleanup(self) -> None:
        """Clean up stale RUNNING entries for dead processes."""
        self._hook_runner.run_stale_running_cleanup()

    def _update_status_file(self) -> None:
        """Update status file for TUI visibility."""
        now = datetime.now(EASTERN_TZ)
        uptime = int((now - self._start_time).total_seconds())
        all_cs = self._check_runner.get_all_changespecs()
        filtered_cs = self._check_runner.get_filtered_changespecs(all_cs)

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
            queued_runners=self.runner_pool.get_queued_count(),
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
        comment_str = (
            f"{self.comment_check_interval // 60} minute(s)"
            if self.comment_check_interval >= 60
            else f"{self.comment_check_interval} seconds"
        )
        hook_str = f"{self.hook_interval} second(s)"
        self._log(
            f"Full cycle: {interval_str}, Comment cycle: {comment_str}, "
            f"Hook cycle: {hook_str}, Max runners: {self.max_runners}"
        )
        if self.query:
            self._log(f"Query filter: {self.query}")

        # Count initial changespecs
        initial = self._check_runner.get_all_changespecs()
        filtered = self._check_runner.get_filtered_changespecs(initial)
        self._log(f"Monitoring {len(filtered)} ChangeSpecs")

        # Write initial status
        self._update_status_file()

        # Run first full and comment cycles immediately
        self._run_full_check_cycle()
        self._run_comment_check_cycle()

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
