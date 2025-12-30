"""ChangeSpec validation functions."""

from ..comments import is_timestamp_suffix
from .models import READY_TO_MAIL_SUFFIX, ChangeSpec, get_base_status


def has_any_status_suffix(changespec: ChangeSpec) -> bool:
    """Check if a ChangeSpec has any ERROR suffix in STATUS/HISTORY/HOOKS/COMMENTS.

    This checks for error suffix patterns (!: ...) in all locations. Used by
    the !!! and !! query shorthands. Includes READY_TO_MAIL suffix.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        True if any field has an error suffix, False otherwise.
    """
    # Check STATUS field for error suffix format (including READY_TO_MAIL)
    if " - (!: " in changespec.status:
        return True
    # Check HISTORY entries for error suffixes
    if changespec.commits:
        for entry in changespec.commits:
            if entry.suffix_type == "error":
                return True
    # Check HOOKS status lines for error suffixes
    if changespec.hooks:
        for hook in changespec.hooks:
            if hook.status_lines:
                for sl in hook.status_lines:
                    if sl.suffix_type == "error":
                        return True
    # Check COMMENTS entries for error suffixes
    if changespec.comments:
        for comment in changespec.comments:
            if comment.suffix_type == "error":
                return True
    return False


def has_any_error_suffix(changespec: ChangeSpec) -> bool:
    """Check if a ChangeSpec has any error suffixes in STATUS/HISTORY/HOOKS/COMMENTS.

    This is used to determine if a ChangeSpec has any attention markers that
    would prevent the READY TO MAIL suffix from being added.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        True if any field has an error suffix, False otherwise.
    """
    # Check STATUS field for error suffix format (but not READY_TO_MAIL)
    if " - (!: " in changespec.status and READY_TO_MAIL_SUFFIX not in changespec.status:
        return True
    # Check HISTORY entries
    if changespec.commits:
        for entry in changespec.commits:
            if entry.suffix_type == "error":
                return True
    # Check HOOKS status lines
    if changespec.hooks:
        for hook in changespec.hooks:
            if hook.status_lines:
                for sl in hook.status_lines:
                    if sl.suffix_type == "error":
                        return True
    # Check COMMENTS entries
    if changespec.comments:
        for comment in changespec.comments:
            if comment.suffix_type == "error":
                return True
    return False


def is_parent_ready_for_mail(
    changespec: ChangeSpec, all_changespecs: list[ChangeSpec]
) -> bool:
    """Check if a ChangeSpec's parent is ready (allows this changespec to be mailed).

    Returns True if:
    - No parent
    - Parent status is "Submitted" or "Mailed"

    Args:
        changespec: The ChangeSpec to check the parent of.
        all_changespecs: List of all changespecs to find the parent.

    Returns:
        True if parent is ready for mail or there is no parent.
    """
    if changespec.parent is None:
        return True
    for cs in all_changespecs:
        if cs.name == changespec.parent:
            base_status = get_base_status(cs.status)
            if base_status in ("Submitted", "Mailed"):
                return True
            return False
    # Parent not found - allow (same pattern as is_parent_submitted)
    return True


def _is_proposal_entry_id(entry_id: str) -> bool:
    """Check if a history entry ID is a proposal (ends with a letter like '2a')."""
    return bool(entry_id) and entry_id[-1].isalpha()


def get_current_and_proposal_entry_ids(changespec: ChangeSpec) -> list[str]:
    """Get the current history entry ID and all proposal entries for that number.

    "Current" means the latest non-proposal entry. If history is [1, 2, 2a, 2b],
    returns ["2", "2a", "2b"]. Does not include entry "1".

    Args:
        changespec: The ChangeSpec to get entry IDs from.

    Returns:
        List of entry IDs (current + proposals with same number), or empty if no history.
    """
    if not changespec.commits:
        return []

    # Find the latest non-proposal entry
    current_entry = None
    for entry in reversed(changespec.commits):
        if not entry.is_proposed:
            current_entry = entry
            break

    if current_entry is None:
        # All entries are proposals - no current entry
        return []

    current_number = current_entry.number
    result = [str(current_number)]

    # Add all proposals with the same number
    for entry in changespec.commits:
        if entry.is_proposed and entry.number == current_number:
            result.append(entry.display_number)

    return result


def all_hooks_passed_for_entries(changespec: ChangeSpec, entry_ids: list[str]) -> bool:
    """Check if all hooks have PASSED status for the given history entry IDs.

    For each hook and each entry ID:
    - If hook has skip_proposal_runs=True and entry is a proposal, skip it
    - Otherwise, check that a status line exists with status "PASSED"

    Args:
        changespec: The ChangeSpec to check hooks for.
        entry_ids: List of history entry IDs to check (e.g., ["2", "2a", "2b"]).

    Returns:
        True if all applicable hooks have PASSED for all entries, False otherwise.
        Returns True if there are no hooks or no entry IDs.
    """
    if not changespec.hooks or not entry_ids:
        return True

    for hook in changespec.hooks:
        for entry_id in entry_ids:
            # Skip proposal entries for hooks with $ prefix
            if hook.skip_proposal_runs and _is_proposal_entry_id(entry_id):
                continue

            # Get status line for this entry
            status_line = hook.get_status_line_for_commit_entry(entry_id)
            if status_line is None:
                # No status line means hook hasn't been run for this entry
                return False
            if status_line.status != "PASSED":
                return False

    return True


def has_any_running_agent(changespec: ChangeSpec) -> bool:
    """Check if ChangeSpec has any running agents (CRS or fix-hook).

    Returns:
        True if running agents are detected, False otherwise.
    """
    # Check COMMENTS for timestamp suffix (CRS running)
    if changespec.comments:
        for comment in changespec.comments:
            if comment.suffix and is_timestamp_suffix(comment.suffix):
                return True
    # Check HOOKS for RUNNING status
    if changespec.hooks:
        for hook in changespec.hooks:
            if hook.status_lines:
                for sl in hook.status_lines:
                    if sl.status == "RUNNING":
                        return True
    return False
