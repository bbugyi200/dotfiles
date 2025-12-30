"""Suffix transformation logic for the loop workflow.

This module handles:
- Transforming old proposal suffixes (error -> removed)
- Acknowledging terminal status markers (error -> acknowledged)
- Checking and updating ready-to-mail status
"""

from commit_utils import update_commit_entry_suffix
from status_state_machine import (
    add_ready_to_mail_suffix,
    remove_ready_to_mail_suffix,
)

from ..changespec import (
    ChangeSpec,
    all_hooks_passed_for_entries,
    get_base_status,
    get_current_and_proposal_entry_ids,
    has_any_error_suffix,
    has_ready_to_mail_suffix,
    is_parent_ready_for_mail,
)
from ..comments import update_comment_suffix_type
from ..hooks import update_hook_status_line_suffix_type


def transform_old_proposal_suffixes(changespec: ChangeSpec) -> list[str]:
    """Remove suffixes from old proposal HISTORY entries.

    An "old proposal" is a proposed entry (Na) where N < the latest regular
    entry number. For example, if HISTORY has (3), then (2a), (2b) are old.

    This affects:
    - HISTORY entry lines with error suffixes (suffix is removed)
    - Hook status lines for those entry IDs (handled separately, transformed)

    Args:
        changespec: The ChangeSpec to process.

    Returns:
        List of update messages.
    """
    updates: list[str] = []

    if not changespec.commits:
        return updates

    # Get the last regular (non-proposed) history number
    last_regular_num = 0
    for entry in changespec.commits:
        if entry.proposal_letter is None:
            last_regular_num = max(last_regular_num, entry.number)

    # If no regular entries, nothing is "old"
    if last_regular_num == 0:
        return updates

    # Find old proposals with error suffixes that need removal
    for entry in changespec.commits:
        if entry.proposal_letter is not None:  # Is a proposal
            if entry.number < last_regular_num:  # Is "old"
                if entry.suffix_type == "error":  # Has error suffix
                    # Remove HISTORY entry suffix
                    success = update_commit_entry_suffix(
                        changespec.file_path,
                        changespec.name,
                        entry.display_number,
                        "remove",
                    )
                    if success:
                        updates.append(
                            f"Cleared suffix from old proposal ({entry.display_number})"
                        )

    # Transform hook status line suffixes for old proposal entry IDs
    # (hook suffixes are handled separately by the hooks formatting code)

    return updates


def acknowledge_terminal_status_markers(changespec: ChangeSpec) -> list[str]:
    """Transform error suffixes to acknowledged for terminal status ChangeSpecs.

    For ChangeSpecs with STATUS = "Reverted" or "Submitted", transforms all
    `- (!: MSG)` suffixes to `- (~: MSG)` across HISTORY, HOOKS, and COMMENTS.

    Args:
        changespec: The ChangeSpec to process.

    Returns:
        List of update messages.
    """
    updates: list[str] = []

    # Only process terminal statuses
    if changespec.status not in ("Reverted", "Submitted"):
        return updates

    # Process HISTORY entries with error suffix
    if changespec.commits:
        for entry in changespec.commits:
            if entry.suffix_type == "error":
                success = update_commit_entry_suffix(
                    changespec.file_path,
                    changespec.name,
                    entry.display_number,
                    "acknowledged",
                )
                if success:
                    updates.append(
                        f"Acknowledged HISTORY ({entry.display_number}) "
                        f"suffix: {entry.suffix}"
                    )

    # Process HOOKS entries with error suffix_type
    if changespec.hooks:
        for hook in changespec.hooks:
            if hook.status_lines:
                for sl in hook.status_lines:
                    if sl.suffix and sl.suffix_type == "error":
                        success = update_hook_status_line_suffix_type(
                            changespec.file_path,
                            changespec.name,
                            hook.command,
                            sl.commit_entry_num,
                            "acknowledged",
                            changespec.hooks,
                        )
                        if success:
                            updates.append(
                                f"Acknowledged HOOK '{hook.display_command}' "
                                f"({sl.commit_entry_num}) suffix: {sl.suffix}"
                            )

    # Process COMMENTS entries with error suffix_type
    if changespec.comments:
        for comment in changespec.comments:
            if comment.suffix and comment.suffix_type == "error":
                success = update_comment_suffix_type(
                    changespec.file_path,
                    changespec.name,
                    comment.reviewer,
                    "acknowledged",
                    changespec.comments,
                )
                if success:
                    updates.append(
                        f"Acknowledged COMMENT [{comment.reviewer}] "
                        f"suffix: {comment.suffix}"
                    )

    return updates


def check_ready_to_mail(
    changespec: ChangeSpec, all_changespecs: list[ChangeSpec]
) -> list[str]:
    """Check if a ChangeSpec is ready to mail and add/remove suffix accordingly.

    A ChangeSpec is ready to mail if:
    - STATUS is "Drafted" (base status)
    - No error suffixes exist in HISTORY/HOOKS/COMMENTS
    - Parent is ready (no parent, Submitted, or Mailed)
    - All hooks have PASSED for current history entry and its proposals

    If a ChangeSpec has the READY TO MAIL suffix but conditions are no longer
    met, the suffix will be removed.

    Args:
        changespec: The ChangeSpec to check.
        all_changespecs: All changespecs (for parent lookup).

    Returns:
        List of update messages.
    """
    updates: list[str] = []

    # Get base status (strip any existing suffix)
    base_status = get_base_status(changespec.status)

    # Only applies to Drafted status
    if base_status != "Drafted":
        return updates

    already_has_suffix = has_ready_to_mail_suffix(changespec.status)
    has_errors = has_any_error_suffix(changespec)
    parent_ready = is_parent_ready_for_mail(changespec, all_changespecs)

    # Check if all hooks have PASSED for current entry and proposals
    entry_ids = get_current_and_proposal_entry_ids(changespec)
    hooks_passed = all_hooks_passed_for_entries(changespec, entry_ids)

    # Determine if conditions are met
    conditions_met = not has_errors and parent_ready and hooks_passed

    if conditions_met and not already_has_suffix:
        # Add the suffix
        success = add_ready_to_mail_suffix(changespec.file_path, changespec.name)
        if success:
            updates.append("Added READY TO MAIL suffix")
    elif not conditions_met and already_has_suffix:
        # Remove the suffix - conditions no longer met
        success = remove_ready_to_mail_suffix(changespec.file_path, changespec.name)
        if success:
            if has_errors:
                updates.append("Removed READY TO MAIL suffix (error suffix appeared)")
            elif not parent_ready:
                updates.append("Removed READY TO MAIL suffix (parent no longer ready)")
            else:
                updates.append("Removed READY TO MAIL suffix (hooks not all passed)")

    return updates
