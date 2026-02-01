"""Timestamp and duration utilities for hooks."""

from datetime import datetime

from gai_utils import EASTERN_TZ

from ..changespec import HookEntry, is_error_suffix
from ..constants import DEFAULT_ZOMBIE_TIMEOUT_SECONDS


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as XhYmZs string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration string (e.g., "1h2m3s", "1m23s", "45s", "2m0s").
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    remaining = total_seconds % 3600
    minutes = remaining // 60
    secs = remaining % 60
    if hours > 0:
        return f"{hours}h{minutes}m{secs}s"
    if minutes > 0:
        return f"{minutes}m{secs}s"
    return f"{secs}s"


def get_current_timestamp() -> str:
    """Get current timestamp in YYmmdd_HHMMSS format.

    Returns:
        Timestamp string (e.g., "251231_143022").
    """
    now = datetime.now(EASTERN_TZ)
    return now.strftime("%y%m%d_%H%M%S")


def get_hook_file_age_seconds_from_timestamp(timestamp: str) -> float | None:
    """Get the age of a hook run based on its timestamp.

    Args:
        timestamp: The timestamp in YYmmdd_HHMMSS format.

    Returns:
        Age in seconds, or None if timestamp can't be parsed.
    """
    try:
        hook_time = datetime.strptime(timestamp, "%y%m%d_%H%M%S")
        hook_time = hook_time.replace(tzinfo=EASTERN_TZ)
        now = datetime.now(EASTERN_TZ)
        return (now - hook_time).total_seconds()
    except (ValueError, TypeError):
        return None


def get_hook_age_seconds(hook: HookEntry) -> float | None:
    """Get the age of a hook's output file in seconds.

    Uses the latest status line's timestamp.

    Args:
        hook: The hook entry to check.

    Returns:
        Age in seconds, or None if no timestamp available.
    """
    latest = hook.latest_status_line
    if not latest or not latest.timestamp:
        return None

    return get_hook_file_age_seconds_from_timestamp(latest.timestamp)


def calculate_duration_from_timestamps(
    start_timestamp: str, end_timestamp: str
) -> float | None:
    """Calculate duration in seconds between two timestamps.

    Args:
        start_timestamp: Start timestamp in YYmmdd_HHMMSS format.
        end_timestamp: End timestamp in YYmmdd_HHMMSS format.

    Returns:
        Duration in seconds, or None if timestamps can't be parsed.
    """
    try:
        start_time = datetime.strptime(start_timestamp, "%y%m%d_%H%M%S")
        start_time = start_time.replace(tzinfo=EASTERN_TZ)
        end_time = datetime.strptime(end_timestamp, "%y%m%d_%H%M%S")
        end_time = end_time.replace(tzinfo=EASTERN_TZ)
        return (end_time - start_time).total_seconds()
    except (ValueError, TypeError):
        return None


def is_timestamp_suffix(suffix: str | None) -> bool:
    """Check if a suffix is a timestamp format (YYmmdd_HHMMSS).

    Args:
        suffix: The suffix value from a HookStatusLine.

    Returns:
        True if the suffix is a valid timestamp format, False otherwise.
    """
    if suffix is None or is_error_suffix(suffix):
        return False
    # Format: 13 chars with underscore at position 6
    if len(suffix) == 13 and suffix[6] == "_":
        try:
            datetime.strptime(suffix, "%y%m%d_%H%M%S")
            return True
        except ValueError:
            pass
    return False


def is_suffix_stale(
    suffix: str | None,
    zombie_timeout_seconds: int = DEFAULT_ZOMBIE_TIMEOUT_SECONDS,
) -> bool:
    """Check if a suffix contains a stale timestamp (older than timeout).

    A stale suffix indicates a fix-hook agent started longer than the timeout ago
    but never completed properly (crashed or was killed).

    Args:
        suffix: The suffix value from a HookStatusLine.
        zombie_timeout_seconds: Timeout in seconds (default: 2 hours).

    Returns:
        True if the suffix is a timestamp that is older than the timeout.
    """
    if not is_timestamp_suffix(suffix) or suffix is None:
        return False
    age = get_hook_file_age_seconds_from_timestamp(suffix)
    return age is not None and age > zombie_timeout_seconds


def format_timestamp_display(timestamp: str) -> str:
    """Format a raw timestamp for display.

    Args:
        timestamp: Raw timestamp in YYmmdd_HHMMSS format (13 chars with underscore).

    Returns:
        Formatted timestamp like [YYmmdd_HHMMSS].
    """
    # Timestamp already has underscore between date and time parts
    return f"[{timestamp}]"
