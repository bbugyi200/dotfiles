"""Hook mutations - suffix operations, bulk operations, and file queries."""

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from ..changespec import HookEntry, HookStatusLine, changespec_lock
from .execution import update_changespec_hooks_field, write_hooks_unlocked

if TYPE_CHECKING:
    from ..changespec import ChangeSpec


# Regex to match /tmp/*_failed_hooks_*.txt paths
_FAILED_HOOKS_FILE_PATTERN = re.compile(
    r"/tmp/[a-zA-Z0-9_]*_failed_hooks_[a-zA-Z0-9_]*\.txt"
)


def add_hook_to_changespec(
    project_file: str,
    changespec_name: str,
    hook_command: str,
    existing_hooks: list[HookEntry] | None = None,
) -> bool:
    """Add a single hook command to a ChangeSpec."""
    # If hooks provided, use them directly (caller responsible for freshness)
    if existing_hooks is not None:
        hooks = list(existing_hooks)
        existing_commands = {hook.command for hook in hooks}
        if hook_command in existing_commands:
            return True
        hooks.append(HookEntry(command=hook_command))
        return update_changespec_hooks_field(project_file, changespec_name, hooks)

    # Otherwise, acquire lock and read fresh state
    from ..changespec import parse_project_file

    try:
        with changespec_lock(project_file):
            changespecs = parse_project_file(project_file)
            current_hooks: list[HookEntry] = []
            for cs in changespecs:
                if cs.name == changespec_name:
                    current_hooks = list(cs.hooks) if cs.hooks else []
                    break

            existing_commands = {hook.command for hook in current_hooks}
            if hook_command in existing_commands:
                return True

            current_hooks.append(HookEntry(command=hook_command))
            write_hooks_unlocked(project_file, changespec_name, current_hooks)
            return True
    except Exception:
        return False


def _apply_hook_suffix_update(
    hooks: list[HookEntry],
    hook_command: str,
    suffix: str,
    entry_id: str | None = None,
    suffix_type: str | None = None,
    summary: str | None = None,
) -> tuple[list[HookEntry], bool]:
    """Apply suffix update to hooks list and return (updated_hooks, was_updated)."""
    updated_hooks = []
    was_updated = False
    for hook in hooks:
        if hook.command == hook_command:
            if hook.status_lines:
                updated_status_lines = []
                # Determine which status line to update
                if entry_id is not None:
                    target_sl = hook.get_status_line_for_commit_entry(entry_id)
                else:
                    target_sl = hook.latest_status_line
                for sl in hook.status_lines:
                    if sl is target_sl:
                        was_updated = True
                        updated_status_lines.append(
                            HookStatusLine(
                                commit_entry_num=sl.commit_entry_num,
                                timestamp=sl.timestamp,
                                status=sl.status,
                                duration=sl.duration,
                                suffix=suffix,
                                suffix_type=suffix_type,
                                summary=summary,
                            )
                        )
                    else:
                        updated_status_lines.append(sl)
                updated_hooks.append(
                    HookEntry(
                        command=hook.command,
                        status_lines=updated_status_lines,
                    )
                )
            else:
                updated_hooks.append(hook)
        else:
            updated_hooks.append(hook)
    return updated_hooks, was_updated


def set_hook_suffix(
    project_file: str,
    changespec_name: str,
    hook_command: str,
    suffix: str,
    hooks: list[HookEntry] | None = None,
    entry_id: str | None = None,
    suffix_type: str | None = None,
    summary: str | None = None,
) -> bool:
    """Set a suffix on a status line of a specific hook.

    Args:
        project_file: Path to the project file.
        changespec_name: Name of the ChangeSpec.
        hook_command: The hook command to update.
        suffix: The suffix to set.
        hooks: List of current hook entries. If None, re-reads from disk to avoid
               overwriting hooks added by concurrent processes.
        entry_id: If provided, set suffix on this specific entry's status line.
                  If None, set suffix on the latest status line (backward compatible).
        suffix_type: Optional suffix type ("error", "running_agent", "summarize_complete").
                     If None, the suffix type is inferred from the suffix value using
                     is_error_suffix() and is_running_agent_suffix() checks.
        summary: Optional summary from summarize_hook workflow. If provided, creates
                 a compound suffix format: (SUFFIX | SUMMARY).
    """
    # If hooks provided, use them directly (caller responsible for freshness)
    if hooks is not None:
        updated_hooks, was_updated = _apply_hook_suffix_update(
            hooks, hook_command, suffix, entry_id, suffix_type, summary
        )
        if not was_updated:
            return False
        return update_changespec_hooks_field(
            project_file, changespec_name, updated_hooks
        )

    # Otherwise, acquire lock and read fresh state
    from ..changespec import parse_project_file

    try:
        with changespec_lock(project_file):
            changespecs = parse_project_file(project_file)
            current_hooks: list[HookEntry] = []
            for cs in changespecs:
                if cs.name == changespec_name:
                    current_hooks = list(cs.hooks) if cs.hooks else []
                    break
            if not current_hooks:
                return False

            updated_hooks, was_updated = _apply_hook_suffix_update(
                current_hooks, hook_command, suffix, entry_id, suffix_type, summary
            )
            if not was_updated:
                return False
            write_hooks_unlocked(project_file, changespec_name, updated_hooks)
            return True
    except Exception:
        return False


def try_claim_hook_for_fix(
    project_file: str,
    changespec_name: str,
    hook_command: str,
    entry_id: str,
    claiming_suffix: str,
) -> str | None:
    """Atomically check eligibility and claim a hook for fix-hook workflow.

    This function prevents race conditions by performing the eligibility check
    and claim in a single atomic operation under the changespec lock.

    Args:
        project_file: Path to the project file.
        changespec_name: Name of the ChangeSpec.
        hook_command: The hook command to claim.
        entry_id: The entry ID for the failing status line.
        claiming_suffix: The suffix to set when claiming (e.g., "claiming-{timestamp}").

    Returns:
        The existing summary if successfully claimed, None if not eligible or already claimed.
    """
    from ..changespec import parse_project_file

    try:
        with changespec_lock(project_file):
            # Re-read fresh state under lock
            changespecs = parse_project_file(project_file)
            cs = next((c for c in changespecs if c.name == changespec_name), None)
            if not cs or not cs.hooks:
                return None

            # Find the hook
            current_hook = next(
                (h for h in cs.hooks if h.command == hook_command), None
            )
            if not current_hook or not current_hook.status_lines:
                return None

            # Check eligibility under lock
            sl = current_hook.get_status_line_for_commit_entry(entry_id)
            if sl is None:
                return None
            if sl.status != "FAILED":
                return None
            if sl.suffix_type != "summarize_complete":
                return None  # Already claimed or not ready
            if not sl.suffix:
                return None

            existing_summary = sl.suffix

            # Claim by updating suffix - build new hooks list
            updated_hooks = []
            for hook in cs.hooks:
                if hook.command == hook_command and hook.status_lines:
                    updated_status_lines = []
                    for status_line in hook.status_lines:
                        if status_line.commit_entry_num == entry_id:
                            # Claim with "claiming_fix" suffix_type
                            updated_status_lines.append(
                                HookStatusLine(
                                    commit_entry_num=status_line.commit_entry_num,
                                    timestamp=status_line.timestamp,
                                    status=status_line.status,
                                    duration=status_line.duration,
                                    suffix=claiming_suffix,
                                    suffix_type="claiming_fix",
                                    summary=existing_summary,
                                )
                            )
                        else:
                            updated_status_lines.append(status_line)
                    updated_hooks.append(
                        HookEntry(
                            command=hook.command,
                            status_lines=updated_status_lines,
                        )
                    )
                else:
                    updated_hooks.append(hook)

            write_hooks_unlocked(project_file, changespec_name, updated_hooks)
            return existing_summary

    except Exception:
        return None


def _apply_clear_hook_suffix(
    hooks: list[HookEntry], hook_command: str
) -> tuple[list[HookEntry], bool]:
    """Apply clear suffix update to hooks list and return (updated_hooks, was_cleared)."""
    updated_hooks = []
    was_cleared = False
    for hook in hooks:
        if hook.command == hook_command:
            if hook.status_lines:
                updated_status_lines = []
                latest_sl = hook.latest_status_line
                for sl in hook.status_lines:
                    if sl is latest_sl and sl.suffix is not None:
                        was_cleared = True
                        updated_status_lines.append(
                            HookStatusLine(
                                commit_entry_num=sl.commit_entry_num,
                                timestamp=sl.timestamp,
                                status=sl.status,
                                duration=sl.duration,
                                suffix=None,
                            )
                        )
                    else:
                        updated_status_lines.append(sl)
                updated_hooks.append(
                    HookEntry(
                        command=hook.command,
                        status_lines=updated_status_lines,
                    )
                )
            else:
                updated_hooks.append(hook)
        else:
            updated_hooks.append(hook)
    return updated_hooks, was_cleared


def clear_hook_suffix(
    project_file: str,
    changespec_name: str,
    hook_command: str,
    hooks: list[HookEntry] | None = None,
) -> bool:
    """Clear the suffix from the latest status line of a specific hook.

    Args:
        project_file: Path to the project file.
        changespec_name: Name of the ChangeSpec.
        hook_command: The hook command to update.
        hooks: List of current hook entries. If None, re-reads from disk to avoid
               overwriting hooks added by concurrent processes.
    """
    # If hooks provided, use them directly (caller responsible for freshness)
    if hooks is not None:
        updated_hooks, was_cleared = _apply_clear_hook_suffix(hooks, hook_command)
        if not was_cleared:
            return False
        return update_changespec_hooks_field(
            project_file, changespec_name, updated_hooks
        )

    # Otherwise, acquire lock and read fresh state
    from ..changespec import parse_project_file

    try:
        with changespec_lock(project_file):
            changespecs = parse_project_file(project_file)
            current_hooks: list[HookEntry] = []
            for cs in changespecs:
                if cs.name == changespec_name:
                    current_hooks = list(cs.hooks) if cs.hooks else []
                    break
            if not current_hooks:
                return False

            updated_hooks, was_cleared = _apply_clear_hook_suffix(
                current_hooks, hook_command
            )
            if not was_cleared:
                return False
            write_hooks_unlocked(project_file, changespec_name, updated_hooks)
            return True
    except Exception:
        return False


def rerun_delete_hooks_by_command(
    project_file: str,
    changespec_name: str,
    commands_to_rerun: set[str],
    commands_to_delete: set[str],
    entry_ids_to_clear: set[str],
) -> bool:
    """Rerun/delete hooks by command string, reading fresh state from disk.

    This function reads fresh hooks from disk to avoid overwriting concurrent
    changes made by other processes (e.g., gai axe updating hook statuses).

    Args:
        project_file: Path to the project file.
        changespec_name: Name of the ChangeSpec.
        commands_to_rerun: Set of hook commands to rerun (clear status lines).
        commands_to_delete: Set of hook commands to delete entirely.
        entry_ids_to_clear: The COMMITS entry IDs to clear status for.

    Returns:
        True if update succeeded, False otherwise.
    """
    from ..changespec import parse_project_file

    try:
        with changespec_lock(project_file):
            changespecs = parse_project_file(project_file)
            current_hooks: list[HookEntry] = []
            for cs in changespecs:
                if cs.name == changespec_name:
                    current_hooks = list(cs.hooks) if cs.hooks else []
                    break

            updated_hooks: list[HookEntry] = []
            for hook in current_hooks:
                if hook.command in commands_to_delete:
                    continue  # Skip (delete)
                elif hook.command in commands_to_rerun:
                    if hook.status_lines:
                        remaining_status_lines = [
                            sl
                            for sl in hook.status_lines
                            if sl.commit_entry_num not in entry_ids_to_clear
                        ]
                        updated_hooks.append(
                            HookEntry(
                                command=hook.command,
                                status_lines=(
                                    remaining_status_lines
                                    if remaining_status_lines
                                    else None
                                ),
                            )
                        )
                    else:
                        updated_hooks.append(hook)
                else:
                    updated_hooks.append(hook)

            write_hooks_unlocked(project_file, changespec_name, updated_hooks)
            return True
    except Exception:
        return False


def get_failed_hooks_file_path(changespec: "ChangeSpec") -> str | None:
    """Find the last failed hooks file path in the ChangeSpec.

    Iterates through all hooks with status lines, looking for any status line
    with suffix_type == "metahook_complete" that contains a path matching
    /tmp/*_failed_hooks_*.txt pattern in either the suffix or summary field.

    Args:
        changespec: The ChangeSpec to search.

    Returns:
        The last matching file path found, or None if not found.
    """
    if not changespec.hooks:
        return None

    result: str | None = None
    for hook in changespec.hooks:
        if not hook.status_lines:
            continue
        for sl in hook.status_lines:
            # Check suffix field
            if sl.suffix:
                match = _FAILED_HOOKS_FILE_PATTERN.search(sl.suffix)
                if match:
                    result = match.group(0)
            # Check summary field
            if sl.summary:
                match = _FAILED_HOOKS_FILE_PATTERN.search(sl.summary)
                if match:
                    result = match.group(0)

    return result


def reset_dollar_hooks(
    project_file: str,
    changespec_name: str,
    log_fn: Callable[[str], None] | None = None,
) -> bool:
    """Reset $-prefixed hooks so gai axe re-runs them.

    After sync/reword/add-tag operations, $-prefixed hooks (skip_proposal_runs)
    need fresh results. This kills any running processes/agents on those hooks
    and deletes status lines for the most recent COMMITS entry ID.

    Args:
        project_file: Path to the project file.
        changespec_name: Name of the ChangeSpec.
        log_fn: Optional callback for logging messages.

    Returns:
        True if reset succeeded or was a no-op, False on error.
    """
    from ..changespec import parse_project_file
    from .history import get_last_history_entry_id
    from .processes import kill_running_processes_for_hooks

    changespecs = parse_project_file(project_file)
    cs = next((c for c in changespecs if c.name == changespec_name), None)
    if cs is None or not cs.hooks:
        return True

    last_entry_id = get_last_history_entry_id(cs)
    if last_entry_id is None:
        return True

    # Identify $-prefixed hooks
    dollar_hook_indices: set[int] = set()
    dollar_commands: set[str] = set()
    for idx, hook in enumerate(cs.hooks):
        if hook.skip_proposal_runs:
            dollar_hook_indices.add(idx)
            dollar_commands.add(hook.command)

    if not dollar_commands:
        return True

    if log_fn:
        log_fn(f"Resetting {len(dollar_commands)} $-prefixed hook(s)...")

    # Kill running processes/agents on dollar hooks
    killed = kill_running_processes_for_hooks(cs.hooks, dollar_hook_indices)
    if killed and log_fn:
        log_fn(f"Killed {killed} running process(es)")

    # Clear status lines for the last entry ID
    return rerun_delete_hooks_by_command(
        project_file,
        changespec_name,
        commands_to_rerun=dollar_commands,
        commands_to_delete=set(),
        entry_ids_to_clear={last_entry_id},
    )
