"""Hook checking logic for the loop workflow.

This module handles determining when hooks need checking and processing
hook completion/zombie detection.
"""

import os
import signal
import time
from collections.abc import Callable

from gai_utils import generate_timestamp

from ..changespec import (
    ChangeSpec,
    HookEntry,
    HookStatusLine,
    count_all_runners_global,
    get_current_and_proposal_entry_ids,
)
from ..constants import DEFAULT_ZOMBIE_TIMEOUT_SECONDS
from ..hooks import (
    check_hook_completion,
    entry_has_running_hooks,
    format_duration,
    get_entries_needing_hook_run,
    get_history_entry_by_id,
    get_hook_age_seconds,
    get_hook_file_age_seconds_from_timestamp,
    has_running_hooks,
    hook_has_any_running_status,
    is_hook_zombie,
    is_process_running,
    is_suffix_stale,
    merge_hook_updates,
    set_hook_suffix,
)
from .hooks_runner import (
    release_entry_workspace,
    release_entry_workspaces,
    start_stale_hooks,
)

# Type alias for logging callback (same as hooks_runner.py)
LogCallback = Callable[[str, str | None], None]

# Constants for race condition handling when detecting dead processes
_COMPLETION_RETRY_DELAY_SECONDS = 0.2  # 200ms delay between retries
_COMPLETION_MAX_RETRIES = 3  # Total wait: ~600ms max
_PENDING_DEAD_TIMEOUT_SECONDS = 60  # Wait 60s before marking as truly DEAD


def _wait_for_completion_marker(
    changespec: ChangeSpec,
    hook: HookEntry,
    status_line: HookStatusLine | None = None,
    max_retries: int = _COMPLETION_MAX_RETRIES,
    retry_delay: float = _COMPLETION_RETRY_DELAY_SECONDS,
) -> HookEntry | None:
    """Wait for completion marker with retries to handle filesystem sync delay.

    When a hook process exits but the completion marker hasn't been synced to disk
    yet, this function retries reading the file a few times before giving up.

    Args:
        changespec: The ChangeSpec the hook belongs to.
        hook: The hook entry to check.
        status_line: Optional specific status line to check. If provided, checks
            this status line's output file instead of the first RUNNING one.
        max_retries: Maximum number of retry attempts.
        retry_delay: Delay in seconds between retries.

    Returns:
        Updated HookEntry if completion marker found, None if still not found.
    """
    for _ in range(max_retries):
        time.sleep(retry_delay)
        completed_hook = check_hook_completion(changespec, hook, status_line)
        if completed_hook:
            return completed_hook
    return None


def check_hooks(
    changespec: ChangeSpec,
    log: LogCallback,
    zombie_timeout_seconds: int = DEFAULT_ZOMBIE_TIMEOUT_SECONDS,
    max_runners: int = 5,
    runners_started_this_cycle: int = 0,
) -> tuple[list[str], int]:
    """Check and run hooks for a ChangeSpec.

    This method handles hooks in two phases:
    1. Check completion status of any RUNNING hooks (no workspace needed)
    2. Start any stale hooks in background (needs workspace)

    Hooks are checked and started for ALL non-historical entries (the latest
    accepted entry + all its proposals).

    Args:
        changespec: The ChangeSpec to check.
        log: Logging callback for status messages.
        zombie_timeout_seconds: Timeout in seconds for zombie detection (default: 2 hours).
        max_runners: Maximum concurrent runners (hooks, agents, mentors) globally (default: 5).
        runners_started_this_cycle: Number of runners already started this cycle (across all
            ChangeSpecs). Added to the global count to avoid exceeding the limit.

    Returns:
        Tuple of (update messages, number of hooks started by this call).
    """
    updates: list[str] = []
    hooks_started = 0

    # Hooks should exist at this point since we checked in should_check_hooks
    if not changespec.hooks:
        return updates, hooks_started

    # For terminal statuses (Reverted, Submitted), we still check completion
    # of RUNNING hooks, but we don't start new hooks
    is_terminal_status = changespec.status in ("Reverted", "Submitted")

    # Get all non-historical entry IDs (current + proposals with same number)
    # e.g., if HISTORY has (1), (2), (3), (3a) -> returns ["3", "3a"]
    entry_ids = get_current_and_proposal_entry_ids(changespec)

    # Phase 1: Check completion status of RUNNING hooks (no workspace needed)
    updated_hooks: list[HookEntry] = []
    # Track hooks that were actually modified (for merge-based write)
    modified_hooks: dict[str, HookEntry] = {}
    # Track which entries need hooks to be started
    entries_needing_hooks: set[str] = set()
    # Track entry IDs that had RUNNING hooks that completed or became zombies
    completed_entry_ids: set[str] = set()

    for hook in changespec.hooks:
        # Check for stale fix-hook suffix (timestamp older than timeout)
        sl = hook.latest_status_line
        if sl is not None and is_suffix_stale(sl.suffix, zombie_timeout_seconds):
            # Mark stale fix-hook as ZOMBIE by setting suffix to "ZOMBIE"
            set_hook_suffix(
                changespec.file_path,
                changespec.name,
                hook.command,
                "ZOMBIE",
                changespec.hooks,
                suffix_type="error",
            )
            updates.append(
                f"Hook '{hook.display_command}' stale fix-hook marked as ZOMBIE"
            )
            # Continue processing this hook normally
            # (the suffix update is written to disk immediately)

        # Check if hook has any RUNNING status (not just the latest)
        # This catches RUNNING hooks from older history entries
        # IMPORTANT: Check completion BEFORE checking if process is dead, because
        # a completed process will no longer be running but should be marked as
        # PASSED/FAILED based on its exit code, not DEAD.
        if hook_has_any_running_status(hook):
            # Check if it has completed
            completed_hook = check_hook_completion(changespec, hook)
            if completed_hook:
                # Track entries that had RUNNING hooks that just completed
                # (status_lines is guaranteed to exist if hook_has_any_running_status)
                for sl in hook.status_lines or []:
                    if sl.status == "RUNNING":
                        completed_entry_ids.add(sl.commit_entry_num)
                updated_hooks.append(completed_hook)
                modified_hooks[completed_hook.command] = completed_hook
                status_msg = completed_hook.status or "UNKNOWN"
                duration_msg = (
                    f" ({completed_hook.duration})" if completed_hook.duration else ""
                )
                updates.append(f"Hook '{hook.command}' -> {status_msg}{duration_msg}")
                continue

        # Check for pending_dead_process hooks that need resolution
        # These were detected as dead in a previous check but are waiting for
        # the 60-second timeout before being marked as truly DEAD.
        found_pending_dead = False
        if hook.status == "RUNNING" and hook.status_lines:
            for sl in hook.status_lines:
                if sl.status == "RUNNING" and sl.suffix_type == "pending_dead_process":
                    # First, check for completion marker (exit code might have appeared)
                    # Pass the specific status line to check ITS output file,
                    # not just the first RUNNING status line's file.
                    completed_hook = check_hook_completion(changespec, hook, sl)
                    if completed_hook:
                        # Found completion marker - recover to PASSED/FAILED
                        for inner_sl in hook.status_lines or []:
                            if inner_sl.status == "RUNNING":
                                completed_entry_ids.add(inner_sl.commit_entry_num)
                        updated_hooks.append(completed_hook)
                        modified_hooks[completed_hook.command] = completed_hook
                        status_msg = completed_hook.status or "UNKNOWN"
                        duration_msg = (
                            f" ({completed_hook.duration})"
                            if completed_hook.duration
                            else ""
                        )
                        updates.append(
                            f"Hook '{hook.command}' -> {status_msg}{duration_msg} "
                            "(recovered from pending dead)"
                        )
                        found_pending_dead = True
                        break

                    # Check if 60 seconds have passed since the pending_dead timestamp
                    # Suffix format: "<PID> | PENDING_DEAD:<timestamp>"
                    pending_timestamp = None
                    if sl.suffix and "PENDING_DEAD:" in sl.suffix:
                        try:
                            parts = sl.suffix.split("PENDING_DEAD:")
                            if len(parts) >= 2:
                                pending_timestamp = parts[1].strip()
                        except (ValueError, IndexError):
                            pass

                    if pending_timestamp:
                        age_seconds = get_hook_file_age_seconds_from_timestamp(
                            pending_timestamp
                        )
                        # Diagnostic logging to help debug PENDING_DEAD resolution
                        log(
                            f"PENDING_DEAD check: ts={pending_timestamp}, "
                            f"age={age_seconds}s, timeout={_PENDING_DEAD_TIMEOUT_SECONDS}s",
                            "dim",
                        )
                        if age_seconds is not None and age_seconds >= (
                            _PENDING_DEAD_TIMEOUT_SECONDS
                        ):
                            # Timeout reached - now mark as truly DEAD
                            timestamp = generate_timestamp()
                            description = (
                                f"[{timestamp}] Process confirmed dead after "
                                f"{_PENDING_DEAD_TIMEOUT_SECONDS}s timeout."
                            )
                            # Extract original PID from suffix (sl.suffix is guaranteed
                            # non-None by the earlier check on line 202)
                            assert sl.suffix is not None
                            original_pid = sl.suffix.split("|")[0].strip()
                            new_suffix = f"{original_pid} | {description}"
                            updated_status_lines = []
                            for inner_sl in hook.status_lines:
                                if inner_sl is sl:
                                    completed_entry_ids.add(inner_sl.commit_entry_num)
                                    updated_status_lines.append(
                                        HookStatusLine(
                                            commit_entry_num=inner_sl.commit_entry_num,
                                            timestamp=inner_sl.timestamp,
                                            status="DEAD",
                                            duration=inner_sl.duration,
                                            suffix=new_suffix,
                                            suffix_type="killed_process",
                                        )
                                    )
                                else:
                                    updated_status_lines.append(inner_sl)
                            dead_hook = HookEntry(
                                command=hook.command,
                                status_lines=updated_status_lines,
                            )
                            updated_hooks.append(dead_hook)
                            modified_hooks[dead_hook.command] = dead_hook
                            updates.append(
                                f"Hook '{hook.command}' -> DEAD "
                                f"(confirmed after {_PENDING_DEAD_TIMEOUT_SECONDS}s)"
                            )
                            found_pending_dead = True
                            break
                        else:
                            # Still waiting - keep as pending_dead_process
                            updated_hooks.append(hook)
                            found_pending_dead = True
                            break

        if found_pending_dead:
            continue

        # Check if RUNNING process is no longer alive (died on its own)
        # This runs AFTER the completion check, so we only mark as DEAD if the
        # process died without logging an exit code (abnormal termination).
        found_dead_process = False
        if hook.status == "RUNNING" and hook.status_lines:
            for sl in hook.status_lines:
                if (
                    sl.status == "RUNNING"
                    and sl.suffix_type == "running_process"
                    and sl.suffix
                ):
                    try:
                        pid = int(sl.suffix)
                        if not is_process_running(pid):
                            # Process exited but no completion marker found yet.
                            # This may be a race condition where file writes haven't
                            # synced yet. Retry a few times before marking as DEAD.
                            # Pass the specific status line to check ITS output file,
                            # not just the first RUNNING status line's file.
                            retry_result = _wait_for_completion_marker(
                                changespec, hook, status_line=sl
                            )
                            if retry_result:
                                # Found completion marker on retry - completed normally
                                for inner_sl in hook.status_lines or []:
                                    if inner_sl.status == "RUNNING":
                                        completed_entry_ids.add(
                                            inner_sl.commit_entry_num
                                        )
                                updated_hooks.append(retry_result)
                                modified_hooks[retry_result.command] = retry_result
                                status_msg = retry_result.status or "UNKNOWN"
                                duration_msg = (
                                    f" ({retry_result.duration})"
                                    if retry_result.duration
                                    else ""
                                )
                                updates.append(
                                    f"Hook '{hook.command}' -> {status_msg}{duration_msg}"
                                )
                                found_dead_process = True  # Skip further processing
                                break

                            # Still no completion marker after retries - mark as
                            # pending_dead_process and wait 60s before confirming DEAD.
                            # This allows more time for filesystem sync or late writes.
                            timestamp = generate_timestamp()
                            new_suffix = f"{sl.suffix} | PENDING_DEAD:{timestamp}"
                            updated_status_lines = []
                            for inner_sl in hook.status_lines:
                                if inner_sl is sl:
                                    # Don't add to completed_entry_ids yet - still pending
                                    updated_status_lines.append(
                                        HookStatusLine(
                                            commit_entry_num=inner_sl.commit_entry_num,
                                            timestamp=inner_sl.timestamp,
                                            status="RUNNING",  # Keep as RUNNING
                                            duration=inner_sl.duration,
                                            suffix=new_suffix,
                                            suffix_type="pending_dead_process",
                                        )
                                    )
                                else:
                                    updated_status_lines.append(inner_sl)
                            pending_hook = HookEntry(
                                command=hook.command,
                                status_lines=updated_status_lines,
                            )
                            updated_hooks.append(pending_hook)
                            modified_hooks[pending_hook.command] = pending_hook
                            updates.append(
                                f"Hook '{hook.command}' -> PENDING_DEAD "
                                f"(will confirm in {_PENDING_DEAD_TIMEOUT_SECONDS}s)"
                            )
                            found_dead_process = True
                            break
                    except ValueError:
                        pass

        if found_dead_process:
            continue

        # Check if this hook is a zombie (running too long)
        if is_hook_zombie(hook, zombie_timeout_seconds):
            # Calculate runtime for description
            age = get_hook_age_seconds(hook)
            runtime_str = format_duration(age) if age else "unknown"
            timestamp = generate_timestamp()
            description = (
                f"[{timestamp}] Killed zombie hook that has been "
                f"running for {runtime_str}."
            )

            if hook.status_lines:
                updated_status_lines = []
                for sl in hook.status_lines:
                    if sl.status == "RUNNING":
                        # Track this entry as completed (zombie)
                        completed_entry_ids.add(sl.commit_entry_num)

                        # Kill the process if it has a running_process suffix
                        if sl.suffix_type == "running_process" and sl.suffix:
                            try:
                                pid = int(sl.suffix)
                                os.killpg(pid, signal.SIGTERM)
                            except (ValueError, ProcessLookupError, PermissionError):
                                pass

                        # Mark as DEAD with zombie description
                        new_suffix = (
                            f"{sl.suffix} | {description}" if sl.suffix else description
                        )
                        updated_status_lines.append(
                            HookStatusLine(
                                commit_entry_num=sl.commit_entry_num,
                                timestamp=sl.timestamp,
                                status="DEAD",
                                duration=sl.duration,
                                suffix=new_suffix,
                                suffix_type="killed_process",
                            )
                        )
                    else:
                        updated_status_lines.append(sl)
                dead_hook = HookEntry(
                    command=hook.command,
                    status_lines=updated_status_lines,
                )
                updated_hooks.append(dead_hook)
                modified_hooks[dead_hook.command] = dead_hook
                updates.append(
                    f"Hook '{hook.command}' -> DEAD - (~$: {runtime_str} zombie)"
                )
            else:
                updated_hooks.append(hook)
            continue

        # Check if hook needs to run for any non-historical entries
        # Don't check for terminal statuses - we won't start new hooks
        if not is_terminal_status:
            # Skip if hook is already running on any entry (limit to one at a time)
            if hook_has_any_running_status(hook):
                updated_hooks.append(hook)
                continue
            hook_entries_needing_run = get_entries_needing_hook_run(hook, entry_ids)
            if hook_entries_needing_run:
                entries_needing_hooks.update(hook_entries_needing_run)
                # Add placeholder - will be replaced after starting
                updated_hooks.append(hook)
            else:
                # Hook is up to date for all entries, keep as is
                updated_hooks.append(hook)
        else:
            # Terminal status - keep hook as is
            updated_hooks.append(hook)

    # Phase 2: Start stale hooks in background (needs workspace)
    # Skip for terminal statuses - don't start new hooks for Reverted/Submitted
    # Start hooks for EACH entry that needs them (each gets its own workspace)
    #
    # Important: Unlimited hooks (those with !-prefix, i.e., skip_fix_hook=True)
    # always start regardless of the runner limit. Only limited hooks are subject
    # to the --max-runners limit.
    if entries_needing_hooks and not is_terminal_status:
        # Check global concurrency limit before starting any hooks
        # Include runners started this cycle (across all ChangeSpecs) that aren't
        # yet written to disk
        current_running = count_all_runners_global() + runners_started_this_cycle
        available_slots = max(0, max_runners - current_running)
        limit_logged = False

        for entry_id in entries_needing_hooks:
            # Determine if we should skip limited hooks for this entry
            # Unlimited (!-prefixed) hooks always start; limited hooks respect the limit
            skip_limited = hooks_started >= available_slots

            if skip_limited and not limit_logged:
                if available_slots == 0:
                    log(
                        f"At runner limit ({current_running} running, "
                        f"limit: {max_runners}), only starting unlimited hooks",
                        "dim",
                    )
                else:
                    log(
                        f"Reached runner limit ({max_runners}), "
                        f"deferring limited hooks (unlimited hooks still start)",
                        "dim",
                    )
                limit_logged = True

            entry = get_history_entry_by_id(changespec, entry_id)
            if entry is None:
                continue
            stale_updates, stale_hooks, limited_count = start_stale_hooks(
                changespec, entry_id, entry, log, skip_limited=skip_limited
            )
            updates.extend(stale_updates)
            hooks_started += limited_count  # Only count limited hooks toward the limit

            # Merge stale hooks into updated_hooks and modified_hooks
            # Replace any stale hooks with their started versions
            if stale_hooks:
                stale_by_command = {h.command: h for h in stale_hooks}
                for i, hook in enumerate(updated_hooks):
                    if hook.command in stale_by_command:
                        updated_hooks[i] = stale_by_command[hook.command]
                # Track started hooks as modified
                for started_hook in stale_hooks:
                    modified_hooks[started_hook.command] = started_hook

    # Deduplicate hooks by command (handles files with duplicate entries)
    updated_hooks = list({h.command: h for h in updated_hooks}.values())

    # Update the HOOKS field in the file only if there were actual changes
    # Use merge_hook_updates to preserve hooks added by other processes
    # (e.g., gai commit adding test hooks while we're updating statuses)
    if modified_hooks:
        success = merge_hook_updates(
            changespec.file_path,
            changespec.name,
            modified_hooks,
        )
        if not success:
            # Log that update failed - will be retried next cycle
            log(
                f"Warning: Hook update failed for {changespec.name}, will retry",
                "dim",
            )

    # Release workspaces for entries whose hooks have all completed
    # This allows early release of older entry workspaces while newer entries
    # are still running
    for entry_id in completed_entry_ids:
        if not entry_has_running_hooks(updated_hooks, entry_id):
            release_entry_workspace(changespec, entry_id, log)

    # Final cleanup: Release all remaining workspaces if no hooks are running
    # This catches any edge cases where individual entry releases were missed
    if not has_running_hooks(updated_hooks):
        release_entry_workspaces(changespec, log)

    return updates, hooks_started
