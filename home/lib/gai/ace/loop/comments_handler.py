"""Comment zombie detection for the loop workflow.

This module handles detecting stale comment entries (ZOMBIE marking).
"""

from ..changespec import ChangeSpec
from ..comments import (
    is_comments_suffix_stale,
    set_comment_suffix,
)
from ..constants import DEFAULT_ZOMBIE_TIMEOUT_SECONDS


def check_comment_zombies(
    changespec: ChangeSpec,
    zombie_timeout_seconds: int = DEFAULT_ZOMBIE_TIMEOUT_SECONDS,
) -> list[str]:
    """Check for stale comment entries and mark them as ZOMBIE.

    Comment entries with timestamp suffix older than timeout are marked as ZOMBIE.

    Args:
        changespec: The ChangeSpec to check.
        zombie_timeout_seconds: Timeout in seconds for zombie detection (default: 2 hours).

    Returns:
        List of update messages.
    """
    updates: list[str] = []

    if not changespec.comments:
        return updates

    for entry in changespec.comments:
        if is_comments_suffix_stale(entry.suffix, zombie_timeout_seconds):
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
