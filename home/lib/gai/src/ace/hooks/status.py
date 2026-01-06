"""Hook status determination utilities."""

from ..changespec import HookEntry
from ..constants import DEFAULT_ZOMBIE_TIMEOUT_SECONDS
from .history import is_proposal_entry
from .timestamps import get_hook_age_seconds


def _parent_hook_passed_or_is_fix_proposal(
    hook: HookEntry,
    entry_id: str,
) -> bool:
    """Check if a proposal can run this hook based on parent status.

    A proposal entry can run a hook if:
    1. The parent entry has PASSED for this hook, OR
    2. This proposal was created by fix-hook to fix THIS hook's failure
       (detected by parent's status line having suffix == proposal's ID)

    Args:
        hook: The hook entry to check.
        entry_id: The proposal entry ID (e.g., "2a").

    Returns:
        True if the hook can run on this proposal, False if it should wait.
    """
    from accept_workflow.parsing import parse_proposal_id

    parsed = parse_proposal_id(entry_id)
    if parsed is None:
        return True  # Not a valid proposal format - allow

    base_number, _letter = parsed
    parent_entry_id = str(base_number)

    parent_status_line = hook.get_status_line_for_commit_entry(parent_entry_id)

    if parent_status_line is None:
        return False  # No parent status - wait

    # Fix-hook exception: suffix matches this proposal's ID
    if parent_status_line.suffix == entry_id:
        return True

    # Check if parent PASSED
    return parent_status_line.status == "PASSED"


def hook_needs_run(hook: HookEntry, last_history_entry_id: str | None) -> bool:
    """Determine if a hook needs to be run.

    A hook needs to run if no status line exists for the current HISTORY entry.
    Hooks prefixed with "$" are skipped for proposal entries (e.g., "2a").
    For proposals, the parent entry must have PASSED this hook first (unless
    this proposal was created by fix-hook to fix this specific hook).

    Args:
        hook: The hook entry to check.
        last_history_entry_id: The ID of the last HISTORY entry (e.g., '1', '1a').

    Returns:
        True if the hook should be run, False otherwise.
    """
    # If there's no history entry ID, don't run (no history means nothing to run)
    if last_history_entry_id is None:
        return False

    # "$" prefixed hooks are skipped for proposals
    if hook.skip_proposal_runs and is_proposal_entry(last_history_entry_id):
        return False

    # Check if there's a status line for this history entry
    status_line = hook.get_status_line_for_commit_entry(last_history_entry_id)
    if status_line is not None:
        return False

    # For proposals, check if parent has passed (or fix-hook exception)
    if is_proposal_entry(last_history_entry_id):
        if not _parent_hook_passed_or_is_fix_proposal(hook, last_history_entry_id):
            return False

    return True


def get_entries_needing_hook_run(hook: HookEntry, entry_ids: list[str]) -> list[str]:
    """Get entry IDs that need this hook to run.

    Returns entry IDs from the given list that don't have a status line
    for this hook yet, respecting the skip_proposal_runs flag and parent-passed
    requirement for proposals.

    Args:
        hook: The hook entry to check.
        entry_ids: List of entry IDs to check (e.g., ["3", "3a"]).

    Returns:
        List of entry IDs that need the hook to run.
    """
    result = []
    for entry_id in entry_ids:
        # Skip proposals for $ prefixed hooks
        if hook.skip_proposal_runs and is_proposal_entry(entry_id):
            continue
        # Check if there's already a status line for this entry
        if hook.get_status_line_for_commit_entry(entry_id) is not None:
            continue
        # For proposals, check if parent has passed (or fix-hook exception)
        if is_proposal_entry(entry_id):
            if not _parent_hook_passed_or_is_fix_proposal(hook, entry_id):
                continue
        result.append(entry_id)
    return result


def is_hook_zombie(
    hook: HookEntry,
    zombie_timeout_seconds: int = DEFAULT_ZOMBIE_TIMEOUT_SECONDS,
) -> bool:
    """Check if a running hook is a zombie (running longer than timeout).

    Args:
        hook: The hook entry to check.
        zombie_timeout_seconds: Timeout in seconds (default: 2 hours).

    Returns:
        True if the hook is a zombie, False otherwise.
    """
    if hook.status != "RUNNING":
        return False

    age = get_hook_age_seconds(hook)
    if age is None:
        return False

    return age > zombie_timeout_seconds


def hook_has_any_running_status(hook: HookEntry) -> bool:
    """Check if a hook has RUNNING status or active workflow (running_agent).

    This is used to detect RUNNING hooks from older history entries
    that may need completion checks. Also detects hooks with active
    workflows (e.g., summarize-hook, fix-hook) via running_agent suffix.

    Args:
        hook: The hook entry to check.

    Returns:
        True if any status line has RUNNING status or running_agent suffix.
    """
    if not hook.status_lines:
        return False

    return any(
        sl.status == "RUNNING" or sl.suffix_type == "running_agent"
        for sl in hook.status_lines
    )


def has_running_hooks(hooks: list[HookEntry] | None) -> bool:
    """Check if any hooks are currently running.

    Args:
        hooks: List of hook entries to check.

    Returns:
        True if any hook has a RUNNING status.
    """
    if not hooks:
        return False

    return any(hook.status == "RUNNING" for hook in hooks)


def entry_has_running_hooks(hooks: list[HookEntry] | None, entry_id: str) -> bool:
    """Check if any hooks have RUNNING status for a specific history entry.

    Args:
        hooks: List of hook entries to check.
        entry_id: The history entry ID (e.g., "1", "1a", "2").

    Returns:
        True if any hook has a RUNNING status line for the specified entry.
    """
    if not hooks:
        return False
    for hook in hooks:
        if not hook.status_lines:
            continue
        for sl in hook.status_lines:
            if sl.commit_entry_num == entry_id and sl.status == "RUNNING":
                return True
    return False
