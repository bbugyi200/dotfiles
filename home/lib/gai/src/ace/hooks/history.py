"""History entry utilities for hooks."""

from ..changespec import ChangeSpec, CommitEntry


def get_last_history_entry_id(changespec: ChangeSpec) -> str | None:
    """Get the ID of the last HISTORY entry (e.g., '1', '1a', '2').

    Args:
        changespec: The ChangeSpec to get the last entry ID from.

    Returns:
        The last history entry ID or None if no history.
    """
    if not changespec.commits:
        return None

    return changespec.commits[-1].display_number


def get_last_history_entry(changespec: ChangeSpec) -> CommitEntry | None:
    """Get the last HISTORY entry.

    Args:
        changespec: The ChangeSpec to get the last entry from.

    Returns:
        The last CommitEntry or None if no history.
    """
    if not changespec.commits:
        return None

    return changespec.commits[-1]


def get_last_accepted_history_entry_id(changespec: ChangeSpec) -> str | None:
    """Get the ID of the last accepted (all-numeric) HISTORY entry.

    This skips proposal entries like '2a' and returns the last entry
    with an all-numeric ID like '2'.

    Args:
        changespec: The ChangeSpec to get the last accepted entry ID from.

    Returns:
        The last accepted history entry ID or None if no history.
    """
    if not changespec.commits:
        return None

    # Iterate in reverse to find the last all-numeric entry
    for entry in reversed(changespec.commits):
        if entry.display_number.isdigit():
            return entry.display_number

    return None


def is_proposal_entry(entry_id: str) -> bool:
    """Check if a history entry ID is a proposal (ends with a letter like '2a')."""
    return bool(entry_id) and entry_id[-1].isalpha()


def get_history_entry_by_id(
    changespec: ChangeSpec, entry_id: str
) -> CommitEntry | None:
    """Get the CommitEntry with the given display number.

    Args:
        changespec: The ChangeSpec to search.
        entry_id: The display number to find (e.g., "1", "2a").

    Returns:
        The matching CommitEntry, or None if not found.
    """
    if not changespec.commits:
        return None
    for entry in changespec.commits:
        if entry.display_number == entry_id:
            return entry
    return None
