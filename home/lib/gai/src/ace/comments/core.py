"""Core comments utilities - timestamps, stale detection, and path helpers."""

import os
from datetime import datetime

from gai_utils import (
    EASTERN_TZ,
    ensure_gai_directory,
    make_safe_filename,
    strip_reverted_suffix,
)

from ..changespec import CommentEntry, is_error_suffix
from ..constants import DEFAULT_ZOMBIE_TIMEOUT_SECONDS


def get_comments_file_path(name: str, reviewer: str, timestamp: str) -> str:
    """Get the path for a comments JSON file.

    Args:
        name: The ChangeSpec name.
        reviewer: The reviewer identifier (e.g., "critique" or "critique_me").
        timestamp: The timestamp in YYmmdd_HHMMSS format.

    Returns:
        Full path to the comments file.
    """
    comments_dir = ensure_gai_directory("comments")
    safe_name = make_safe_filename(strip_reverted_suffix(name))
    filename = f"{safe_name}-{reviewer}-{timestamp}.json"
    return os.path.join(comments_dir, filename)


def is_timestamp_suffix(suffix: str | None) -> bool:
    """Check if a suffix is a timestamp format (YYmmdd_HHMMSS or YYmmddHHMMSS).

    Args:
        suffix: The suffix value from a CommentEntry.

    Returns:
        True if the suffix is a valid timestamp format, False otherwise.
    """
    if suffix is None or is_error_suffix(suffix):
        return False
    # New format: 13 chars with underscore at position 6
    if len(suffix) == 13 and suffix[6] == "_":
        try:
            datetime.strptime(suffix, "%y%m%d_%H%M%S")
            return True
        except ValueError:
            pass
    # Legacy format: 12 digits
    elif len(suffix) == 12 and suffix.isdigit():
        try:
            datetime.strptime(suffix, "%y%m%d%H%M%S")
            return True
        except ValueError:
            pass
    return False


def _get_suffix_age_seconds(suffix: str) -> float | None:
    """Get the age of a timestamp suffix in seconds.

    Args:
        suffix: The suffix value (timestamp format).

    Returns:
        Age in seconds, or None if not a valid timestamp.
    """
    try:
        # Remove underscore if present for parsing
        clean_suffix = suffix.replace("_", "")
        suffix_time = datetime.strptime(clean_suffix, "%y%m%d%H%M%S")
        suffix_time = suffix_time.replace(tzinfo=EASTERN_TZ)
        now = datetime.now(EASTERN_TZ)
        return (now - suffix_time).total_seconds()
    except (ValueError, TypeError):
        return None


def is_comments_suffix_stale(
    suffix: str | None,
    zombie_timeout_seconds: int = DEFAULT_ZOMBIE_TIMEOUT_SECONDS,
) -> bool:
    """Check if a suffix contains a stale timestamp (older than timeout).

    A stale suffix indicates a CRS workflow started longer than the timeout ago
    but never completed properly (crashed or was killed).

    Args:
        suffix: The suffix value from a CommentEntry.
        zombie_timeout_seconds: Timeout in seconds (default: 2 hours).

    Returns:
        True if the suffix is a timestamp that is older than the timeout.
    """
    if not is_timestamp_suffix(suffix):
        return False
    if suffix is None:
        return False
    age = _get_suffix_age_seconds(suffix)
    return age is not None and age > zombie_timeout_seconds


def comment_needs_crs(entry: CommentEntry) -> bool:
    """Check if a comment entry needs CRS workflow to run.

    A comment entry needs CRS if it has no suffix (not running, not completed).

    Args:
        entry: The CommentEntry to check.

    Returns:
        True if the entry needs CRS workflow, False otherwise.
    """
    return entry.suffix is None
