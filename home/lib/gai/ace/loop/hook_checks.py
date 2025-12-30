"""Hook checking logic for the loop workflow.

This module handles determining when hooks need checking and processing
hook completion/zombie detection.
"""

from collections.abc import Callable

from ..changespec import (
    ChangeSpec,
    HookEntry,
    HookStatusLine,
    get_current_and_proposal_entry_ids,
)
from ..hooks import (
    check_hook_completion,
    entry_has_running_hooks,
    get_entries_needing_hook_run,
    get_history_entry_by_id,
    has_running_hooks,
    hook_has_any_running_status,
    is_hook_zombie,
    is_suffix_stale,
    set_hook_suffix,
    update_changespec_hooks_field,
)
from .hooks_runner import (
    release_entry_workspace,
    release_entry_workspaces,
    start_stale_hooks,
)

# Type alias for logging callback (same as hooks_runner.py)
LogCallback = Callable[[str, str | None], None]


def check_hooks(changespec: ChangeSpec, log: LogCallback) -> list[str]:
    """Check and run hooks for a ChangeSpec.

    This method handles hooks in two phases:
    1. Check completion status of any RUNNING hooks (no workspace needed)
    2. Start any stale hooks in background (needs workspace)

    Hooks are checked and started for ALL non-historical entries (the latest
    accepted entry + all its proposals).

    Args:
        changespec: The ChangeSpec to check.
        log: Logging callback for status messages.

    Returns:
        List of update messages.
    """
    updates: list[str] = []

    # Hooks should exist at this point since we checked in should_check_hooks
    if not changespec.hooks:
        return updates

    # For terminal statuses (Reverted, Submitted), we still check completion
    # of RUNNING hooks, but we don't start new hooks
    is_terminal_status = changespec.status in ("Reverted", "Submitted")

    # Get all non-historical entry IDs (current + proposals with same number)
    # e.g., if HISTORY has (1), (2), (3), (3a) -> returns ["3", "3a"]
    entry_ids = get_current_and_proposal_entry_ids(changespec)

    # Phase 1: Check completion status of RUNNING hooks (no workspace needed)
    updated_hooks: list[HookEntry] = []
    # Track which entries need hooks to be started
    entries_needing_hooks: set[str] = set()
    # Track entry IDs that had RUNNING hooks that completed or became zombies
    completed_entry_ids: set[str] = set()

    for hook in changespec.hooks:
        # Check for stale fix-hook suffix (>2h old timestamp)
        sl = hook.latest_status_line
        if sl is not None and is_suffix_stale(sl.suffix):
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

        # Check if this hook is a zombie
        if is_hook_zombie(hook):
            # Mark the RUNNING status line as ZOMBIE
            if hook.status_lines:
                updated_status_lines = []
                for sl in hook.status_lines:
                    if sl.status == "RUNNING":
                        # Track this entry as completed (zombie)
                        completed_entry_ids.add(sl.history_entry_num)
                        # Update RUNNING to FAILED with ZOMBIE suffix
                        updated_status_lines.append(
                            HookStatusLine(
                                history_entry_num=sl.history_entry_num,
                                timestamp=sl.timestamp,
                                status="FAILED",
                                duration=sl.duration,
                                suffix="ZOMBIE",
                                suffix_type="error",
                            )
                        )
                    else:
                        updated_status_lines.append(sl)
                failed_hook = HookEntry(
                    command=hook.command,
                    status_lines=updated_status_lines,
                )
                updated_hooks.append(failed_hook)
                updates.append(f"Hook '{hook.command}' -> FAILED - (!: ZOMBIE)")
            else:
                updated_hooks.append(hook)
            continue

        # Check if hook has any RUNNING status (not just the latest)
        # This catches RUNNING hooks from older history entries
        if hook_has_any_running_status(hook):
            # Check if it has completed
            completed_hook = check_hook_completion(changespec, hook)
            if completed_hook:
                # Track entries that had RUNNING hooks that just completed
                # (status_lines is guaranteed to exist if hook_has_any_running_status)
                for sl in hook.status_lines or []:
                    if sl.status == "RUNNING":
                        completed_entry_ids.add(sl.history_entry_num)
                updated_hooks.append(completed_hook)
                status_msg = completed_hook.status or "UNKNOWN"
                duration_msg = (
                    f" ({completed_hook.duration})" if completed_hook.duration else ""
                )
                updates.append(f"Hook '{hook.command}' -> {status_msg}{duration_msg}")
            else:
                # Still running, keep as is
                updated_hooks.append(hook)
            continue

        # Check if hook needs to run for any non-historical entries
        # Don't check for terminal statuses - we won't start new hooks
        if not is_terminal_status:
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
    if entries_needing_hooks and not is_terminal_status:
        for entry_id in entries_needing_hooks:
            entry = get_history_entry_by_id(changespec, entry_id)
            if entry is None:
                continue
            stale_updates, stale_hooks = start_stale_hooks(
                changespec, entry_id, entry, log
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

    return updates
