"""Suffix transformation logic for the loop workflow.

This module handles:
- Transforming old proposal suffixes (error -> removed)
- Stripping error markers from old commit entry hooks (error -> plain)
- Stripping terminal status markers (error -> removed)
- Checking and updating ready-to-mail status
"""

from commit_utils import update_commit_entry_suffix
from status_state_machine import (
    add_ready_to_mail_suffix,
    remove_ready_to_mail_suffix,
)

from ..changespec import (
    ChangeSpec,
    HookEntry,
    HookStatusLine,
    all_hooks_passed_for_entries,
    get_base_status,
    get_current_and_proposal_entry_ids,
    has_any_error_suffix,
    has_ready_to_mail_suffix,
    is_parent_ready_for_mail,
    parse_commit_entry_id,
)
from ..comments import clear_comment_suffix
from ..hooks import update_changespec_hooks_field, update_hook_status_line_suffix_type


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


def strip_old_entry_error_markers(changespec: ChangeSpec) -> list[str]:
    """Strip error markers from hook status lines for older commit entries.

    An "older" entry is one where the numeric part of the commit entry ID is
    less than the highest all-numeric entry ID. For example, if COMMITS has
    (1), (2), (3), (2a), then entries (1), (2), (2a) are all "older" than (3).

    This transforms:
        (1) [timestamp] FAILED - (!: message)
    To:
        (1) [timestamp] FAILED - (message)

    Args:
        changespec: The ChangeSpec to process.

    Returns:
        List of update messages.
    """
    updates: list[str] = []

    if not changespec.commits or not changespec.hooks:
        return updates

    # Find the highest all-numeric commit entry ID
    highest_numeric_id = 0
    for entry in changespec.commits:
        if entry.proposal_letter is None:  # All-numeric entry (no letter suffix)
            highest_numeric_id = max(highest_numeric_id, entry.number)

    # If no regular entries, nothing to strip
    if highest_numeric_id == 0:
        return updates

    # Process each hook's status lines
    for hook in changespec.hooks:
        if not hook.status_lines:
            continue

        for sl in hook.status_lines:
            # Only process status lines with error suffix_type
            if sl.suffix_type != "error":
                continue

            # Parse the commit entry ID to get numeric part
            entry_num, _ = parse_commit_entry_id(sl.commit_entry_num)

            # Check if this entry is "older" (numeric part < highest)
            if entry_num < highest_numeric_id:
                # Strip the error marker by changing to "plain"
                success = update_hook_status_line_suffix_type(
                    changespec.file_path,
                    changespec.name,
                    hook.command,
                    sl.commit_entry_num,
                    "plain",
                    changespec.hooks,
                )
                if success:
                    updates.append(
                        f"Stripped error marker from HOOK '{hook.display_command}' "
                        f"({sl.commit_entry_num}): {sl.suffix}"
                    )

    return updates


def _strip_terminal_status_markers(changespec: ChangeSpec) -> list[str]:
    """Strip error suffixes for terminal status ChangeSpecs.

    For ChangeSpecs with STATUS = "Reverted" or "Submitted", removes all
    error suffixes (`- (!: MSG)`) across HISTORY, HOOKS, and COMMENTS.

    Args:
        changespec: The ChangeSpec to process.

    Returns:
        List of update messages.
    """
    updates: list[str] = []

    # Only process terminal statuses
    if changespec.status not in ("Reverted", "Submitted"):
        return updates

    # Process HISTORY entries with error or running_agent suffix
    if changespec.commits:
        for entry in changespec.commits:
            if entry.suffix_type in ("error", "running_agent"):
                success = update_commit_entry_suffix(
                    changespec.file_path,
                    changespec.name,
                    entry.display_number,
                    "remove",
                )
                if success:
                    updates.append(
                        f"Cleared HISTORY ({entry.display_number}) "
                        f"suffix: {entry.suffix}"
                    )

    # Process HOOKS entries with error or running_agent suffix_type
    # Build modified hooks list with cleared suffixes
    if changespec.hooks:
        hooks_to_update: list[HookEntry] = []
        hook_updates: list[str] = []

        for hook in changespec.hooks:
            if hook.status_lines:
                updated_status_lines: list[HookStatusLine] = []
                for sl in hook.status_lines:
                    if sl.suffix_type == "running_agent" and sl.suffix is not None:
                        # Convert running_agent (@:) to killed_agent (~@:)
                        updated_status_lines.append(
                            HookStatusLine(
                                commit_entry_num=sl.commit_entry_num,
                                timestamp=sl.timestamp,
                                status=sl.status,
                                duration=sl.duration,
                                suffix=sl.suffix,
                                suffix_type="killed_agent",
                            )
                        )
                        hook_updates.append(
                            f"Converted HOOK '{hook.display_command}' "
                            f"({sl.commit_entry_num}) to killed_agent: {sl.suffix}"
                        )
                    elif sl.suffix_type == "error" and sl.suffix:
                        # Convert error (!:) to plain (no prefix)
                        updated_status_lines.append(
                            HookStatusLine(
                                commit_entry_num=sl.commit_entry_num,
                                timestamp=sl.timestamp,
                                status=sl.status,
                                duration=sl.duration,
                                suffix=sl.suffix,
                                suffix_type="plain",
                            )
                        )
                        hook_updates.append(
                            f"Stripped error marker from HOOK '{hook.display_command}' "
                            f"({sl.commit_entry_num}): {sl.suffix}"
                        )
                    else:
                        updated_status_lines.append(sl)
                hooks_to_update.append(
                    HookEntry(command=hook.command, status_lines=updated_status_lines)
                )
            else:
                hooks_to_update.append(hook)

        if hook_updates:
            success = update_changespec_hooks_field(
                changespec.file_path,
                changespec.name,
                hooks_to_update,
            )
            if success:
                updates.extend(hook_updates)

    # Process COMMENTS entries with error or running_agent suffix_type
    if changespec.comments:
        for comment in changespec.comments:
            # Clear error suffixes (must be non-empty) and running_agent
            # suffixes (including empty "- (@)" markers)
            if (
                comment.suffix_type == "running_agent" and comment.suffix is not None
            ) or (comment.suffix_type == "error" and comment.suffix):
                success = clear_comment_suffix(
                    changespec.file_path,
                    changespec.name,
                    comment.reviewer,
                    changespec.comments,
                )
                if success:
                    updates.append(
                        f"Cleared COMMENT [{comment.reviewer}] suffix: {comment.suffix}"
                    )

    return updates


# Keep old function name as alias for backward compatibility
acknowledge_terminal_status_markers = _strip_terminal_status_markers


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
