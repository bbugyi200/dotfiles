"""Workflow-specific hook queries for fix-hook and summarize-hook."""

from ..changespec import HookEntry
from .history import is_proposal_entry


def _hook_has_fix_excluded_suffix(hook: HookEntry) -> bool:
    """Check if a hook's latest status line has a suffix that excludes it from fix-hook."""
    sl = hook.latest_status_line
    if sl is None:
        return False
    return sl.suffix is not None


def get_failing_hooks_for_fix(hooks: list[HookEntry]) -> list[HookEntry]:
    """Get failing hooks that are eligible for fix-hook workflow.

    A hook is eligible if:
    - Status is FAILED
    - History entry ID is NOT a proposal (regular entry like "1", "2")
    - No excluded suffix exists

    Note: This only checks the latest status line. Use get_failing_hook_entries_for_fix()
    to check specific entry IDs.
    """
    result: list[HookEntry] = []
    for hook in hooks:
        latest = hook.latest_status_line
        if not latest or latest.status != "FAILED":
            continue
        if hook.skip_fix_hook:
            continue
        if _hook_has_fix_excluded_suffix(hook):
            continue
        # Exclude proposal entries - they go to summarize-hook instead
        sl = hook.latest_status_line
        if sl and is_proposal_entry(sl.commit_entry_num):
            continue
        result.append(hook)
    return result


def get_failing_hook_entries_for_fix(
    hooks: list[HookEntry], entry_ids: list[str]
) -> list[tuple[HookEntry, str]]:
    """Get failing hook entries for specific entry IDs that are eligible for fix-hook.

    Unlike get_failing_hooks_for_fix(), this checks ALL specified entry IDs,
    not just the latest status line.

    A hook entry is eligible for fix-hook if:
    - Has a status line for the entry ID with FAILED status
    - The entry ID is NOT a proposal (regular entry like "1", "2", "3")
    - Has suffix_type="summarize_complete" (summary already generated, ready for fix)
    - Has non-empty suffix (contains the summary text)

    Args:
        hooks: List of hook entries to check.
        entry_ids: List of entry IDs to check (e.g., ["3", "3a"]).

    Returns:
        List of (HookEntry, entry_id) tuples for entries eligible for fix-hook.
    """
    result: list[tuple[HookEntry, str]] = []
    for hook in hooks:
        if not hook.status_lines:
            continue
        if hook.skip_fix_hook:
            continue
        for entry_id in entry_ids:
            # Skip proposal entries - they don't get fix-hook
            if is_proposal_entry(entry_id):
                continue
            sl = hook.get_status_line_for_commit_entry(entry_id)
            if sl is None:
                continue
            # Must be FAILED
            if sl.status != "FAILED":
                continue
            # Must have summarize_complete suffix (summary already generated)
            if sl.suffix_type != "summarize_complete":
                continue
            # Must have non-empty summary text (stored in suffix field)
            if not sl.suffix:
                continue
            result.append((hook, entry_id))
    return result


def get_failing_hooks_for_summarize(hooks: list[HookEntry]) -> list[HookEntry]:
    """Get failing hooks eligible for summarize-hook workflow.

    A hook is eligible for summarize if:
    - Its latest status line has FAILED status
    - The history entry ID is a proposal (ends with letter like "2a")
    - No suffix exists on the latest status line

    Note: This only checks the latest status line. Use get_failing_hook_entries_for_summarize()
    to check specific entry IDs.

    Args:
        hooks: List of hook entries to check.

    Returns:
        List of HookEntry objects eligible for summarize-hook workflow.
    """
    result: list[HookEntry] = []
    for hook in hooks:
        sl = hook.latest_status_line
        if sl is None:
            continue
        # Must be FAILED
        if sl.status != "FAILED":
            continue
        # Must be a proposal entry (ends with letter)
        if not is_proposal_entry(sl.commit_entry_num):
            continue
        # Must not have a suffix already
        if sl.suffix is not None:
            continue
        result.append(hook)
    return result


def get_failing_hook_entries_for_summarize(
    hooks: list[HookEntry], entry_ids: list[str]
) -> list[tuple[HookEntry, str]]:
    """Get failing hook entries for specific entry IDs that are eligible for summarize.

    Unlike get_failing_hooks_for_summarize(), this checks ALL specified entry IDs,
    not just the latest status line.

    A hook entry is eligible for summarize if:
    - Has a status line for the entry ID with FAILED status
    - No suffix exists on that status line

    Note: Both proposal entries (like "2a") AND non-proposal entries (like "2")
    are eligible for summarize. Non-proposal entries will proceed to fix-hook
    after summarize completes.

    Args:
        hooks: List of hook entries to check.
        entry_ids: List of entry IDs to check (e.g., ["3", "3a"]).

    Returns:
        List of (HookEntry, entry_id) tuples for entries eligible for summarize-hook.
    """
    result: list[tuple[HookEntry, str]] = []
    for hook in hooks:
        if not hook.status_lines:
            continue
        for entry_id in entry_ids:
            sl = hook.get_status_line_for_commit_entry(entry_id)
            if sl is None:
                continue
            # Must be FAILED
            if sl.status != "FAILED":
                continue
            # Must not have a suffix already
            if sl.suffix is not None:
                continue
            result.append((hook, entry_id))
    return result


def has_failing_hooks_for_fix(hooks: list[HookEntry] | None) -> bool:
    """Check if there are any hooks eligible for fix-hook workflow."""
    if not hooks:
        return False
    return len(get_failing_hooks_for_fix(hooks)) > 0
