"""Core LoopWorkflow class for continuously checking ChangeSpec status updates."""

import os
import sys
import time
from datetime import datetime

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from gai_utils import EASTERN_TZ
from rich_utils import format_countdown
from running_field import get_workspace_directory
from status_state_machine import (
    remove_workspace_suffix,
    transition_changespec_status,
)

from ..changespec import (
    ChangeSpec,
    find_all_changespecs,
)
from ..cl_status import (
    SYNCABLE_STATUSES,
    is_cl_submitted,
    is_parent_submitted,
)
from ..comments import is_timestamp_suffix
from ..constants import DEFAULT_ZOMBIE_TIMEOUT_SECONDS
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
from .hook_checks import check_hooks
from .suffix_transforms import (
    acknowledge_terminal_status_markers,
    check_ready_to_mail,
    strip_old_entry_error_markers,
    transform_old_proposal_suffixes,
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
        hook_interval_seconds: int = 1,
        zombie_timeout_seconds: int = DEFAULT_ZOMBIE_TIMEOUT_SECONDS,
        max_concurrent_hooks: int = 5,
        max_concurrent_agents: int = 5,
    ) -> None:
        """Initialize the loop workflow.

        Args:
            interval_seconds: Polling interval in seconds (default: 300 = 5 minutes)
            verbose: If True, show skipped ChangeSpecs in output (default: False)
            hook_interval_seconds: Hook check interval in seconds (default: 1)
            zombie_timeout_seconds: Zombie detection timeout in seconds (default: 2 hours)
            max_concurrent_hooks: Max concurrent hook processes globally (default: 5)
            max_concurrent_agents: Max concurrent agent workflows globally (default: 5)
        """
        self.interval_seconds = interval_seconds
        self.verbose = verbose
        self.hook_interval_seconds = hook_interval_seconds
        self.zombie_timeout_seconds = zombie_timeout_seconds
        self.max_concurrent_hooks = max_concurrent_hooks
        self.max_concurrent_agents = max_concurrent_agents
        self.console = Console()
        self._countdown_showing = False

    def _is_leaf_cl(self, changespec: ChangeSpec) -> bool:
        """Check if a ChangeSpec is a leaf CL (no parent or parent is submitted).

        Leaf CLs are checked on the first cycle regardless of cache state.

        Args:
            changespec: The ChangeSpec to check.

        Returns:
            True if this is a leaf CL, False otherwise.
        """
        return is_parent_submitted(changespec)

    def _print_countdown(self, seconds_remaining: int) -> None:
        """Print countdown timer, overwriting the current line.

        Args:
            seconds_remaining: Number of seconds until next full check.
        """
        # Add blank line before countdown if this is the first one after other output
        if not self._countdown_showing:
            sys.stdout.write("\n")

        # Use format_countdown for styled output similar to gemini_timer
        countdown_text = format_countdown(seconds_remaining)
        sys.stdout.write(f"\r{countdown_text}  ")
        sys.stdout.flush()
        self._countdown_showing = True

    def _log(self, message: str, style: str | None = None) -> None:
        """Print a timestamped log message.

        Args:
            message: The message to print.
            style: Optional rich style to apply (e.g., "dim", "green", "yellow").
        """
        # Clear countdown line if it's currently showing
        if self._countdown_showing:
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()
            self._countdown_showing = False

        timestamp = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S")
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
        try:
            workspace_dir = get_workspace_directory(changespec.project_basename)
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
        start_updates, _ = start_stale_workflows(
            changespec, self._log, self.max_concurrent_agents
        )
        updates.extend(start_updates)

        return updates

    def _run_hooks_cycle(self) -> int:
        """Run a hooks cycle - check completion, start new hooks, and detect zombies.

        This runs on the frequent hook interval (default 1s).

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
                hook_updates = check_hooks(
                    changespec,
                    self._log,
                    self.zombie_timeout_seconds,
                    self.max_concurrent_hooks,
                )
                updates.extend(hook_updates)

            # Check for stale comment entries (ZOMBIE detection)
            zombie_updates = check_comment_zombies(
                changespec, self.zombie_timeout_seconds
            )
            updates.extend(zombie_updates)

            # Check and run CRS/fix-hook workflows
            workflow_updates = self._check_workflows(changespec)
            updates.extend(workflow_updates)

            # Transform old proposal suffixes (!: -> ~:)
            transform_updates = transform_old_proposal_suffixes(changespec)
            updates.extend(transform_updates)

            # Strip error markers from old commit entry hooks (!: -> plain)
            strip_updates = strip_old_entry_error_markers(changespec)
            updates.extend(strip_updates)

            # Acknowledge terminal status attention markers (!: -> ~:)
            acknowledge_updates = acknowledge_terminal_status_markers(changespec)
            updates.extend(acknowledge_updates)

            # Check if ChangeSpec is ready to mail and add suffix
            ready_to_mail_updates = check_ready_to_mail(changespec, all_changespecs)
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
            projects.add(cs.project_basename)
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
                    # Show countdown timer
                    remaining = self.interval_seconds - elapsed
                    self._print_countdown(remaining)

                    time.sleep(self.hook_interval_seconds)
                    elapsed += self.hook_interval_seconds

                    # Check if we've reached the next full cycle
                    if elapsed >= self.interval_seconds:
                        break

                    # Run hooks cycle (check completion and start new hooks)
                    self._run_hooks_cycle()

                # Clear countdown line before next full cycle
                if self._countdown_showing:
                    sys.stdout.write("\r" + " " * 50 + "\r")
                    sys.stdout.flush()
                    self._countdown_showing = False

        except KeyboardInterrupt:
            self._log("Loop stopped by user")
            return True
