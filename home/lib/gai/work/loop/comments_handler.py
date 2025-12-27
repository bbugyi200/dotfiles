"""Comment zombie detection for the loop workflow.

This module handles detecting stale comment entries (ZOMBIE marking).
"""

from ..changespec import ChangeSpec
from ..comments import (
    is_comments_suffix_stale,
    set_comment_suffix,
)


def check_comment_zombies(changespec: ChangeSpec) -> list[str]:
    """Check for stale comment entries and mark them as ZOMBIE.

    Comment entries with timestamp suffix >2h old are marked as ZOMBIE.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of update messages.
    """
    updates: list[str] = []

    if not changespec.comments:
        return updates

    for entry in changespec.comments:
        if is_comments_suffix_stale(entry.suffix):
            # Mark as ZOMBIE
            set_comment_suffix(
                changespec.file_path,
                changespec.name,
                entry.reviewer,
                "ZOMBIE",
                changespec.comments,
            )
            updates.append(
                f"Comment entry [{entry.reviewer}] stale CRS marked as ZOMBIE"
            )

    return updates
