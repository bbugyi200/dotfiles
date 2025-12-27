"""Core hook utilities - timestamps, duration, history, and status checks."""

from datetime import datetime
from zoneinfo import ZoneInfo

# Re-export generate_timestamp for backward compatibility
from gai_utils import generate_timestamp  # noqa: F401

from ..changespec import (
    ChangeSpec,
    HistoryEntry,
    HookEntry,
)
from ..cl_status import FIX_HOOK_STALE_THRESHOLD_SECONDS, HOOK_ZOMBIE_THRESHOLD_SECONDS


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


def get_last_history_entry_id(changespec: ChangeSpec) -> str | None:
    """Get the ID of the last HISTORY entry (e.g., '1', '1a', '2').

    Args:
        changespec: The ChangeSpec to get the last entry ID from.

    Returns:
        The last history entry ID or None if no history.
    """
    if not changespec.history:
        return None

    return changespec.history[-1].display_number


def get_last_history_entry(changespec: ChangeSpec) -> HistoryEntry | None:
    """Get the last HISTORY entry.

    Args:
        changespec: The ChangeSpec to get the last entry from.

    Returns:
        The last HistoryEntry or None if no history.
    """
    if not changespec.history:
        return None

    return changespec.history[-1]


def _is_proposal_entry(entry_id: str) -> bool:
    """Check if a history entry ID is a proposal (ends with a letter like '2a')."""
    return bool(entry_id) and entry_id[-1].isalpha()


def hook_needs_run(hook: HookEntry, last_history_entry_id: str | None) -> bool:
    """Determine if a hook needs to be run.

    A hook needs to run if no status line exists for the current HISTORY entry.
    Hooks prefixed with "!" are skipped for proposal entries (e.g., "2a").

    Args:
        hook: The hook entry to check.
        last_history_entry_id: The ID of the last HISTORY entry (e.g., '1', '1a').

    Returns:
        True if the hook should be run, False otherwise.
    """
    # If there's no history entry ID, don't run (no history means nothing to run)
    if last_history_entry_id is None:
        return False

    # "!" prefixed hooks are skipped for proposals
    if hook.command.startswith("!") and _is_proposal_entry(last_history_entry_id):
        return False

    # Check if there's a status line for this history entry
    status_line = hook.get_status_line_for_history_entry(last_history_entry_id)
    return status_line is None


def get_hook_file_age_seconds_from_timestamp(timestamp: str) -> float | None:
    """Get the age of a hook run based on its timestamp.

    Args:
        timestamp: The timestamp in YYmmdd_HHMMSS or YYmmddHHMMSS format.

    Returns:
        Age in seconds, or None if timestamp can't be parsed.
    """
    try:
        eastern = ZoneInfo("America/New_York")
        # Remove underscore if present for parsing (supports both old and new formats)
        clean_timestamp = timestamp.replace("_", "")
        hook_time = datetime.strptime(clean_timestamp, "%y%m%d%H%M%S")
        hook_time = hook_time.replace(tzinfo=eastern)
        now = datetime.now(eastern)
        return (now - hook_time).total_seconds()
    except (ValueError, TypeError):
        return None


def _get_hook_file_age_seconds(hook: HookEntry) -> float | None:
    """Get the age of a hook's output file in seconds.

    Uses the latest status line's timestamp.

    Args:
        hook: The hook entry to check.

    Returns:
        Age in seconds, or None if no timestamp available.
    """
    if not hook.timestamp:
        return None

    return get_hook_file_age_seconds_from_timestamp(hook.timestamp)


def calculate_duration_from_timestamps(
    start_timestamp: str, end_timestamp: str
) -> float | None:
    """Calculate duration in seconds between two timestamps.

    Args:
        start_timestamp: Start timestamp in YYmmdd_HHMMSS or YYmmddHHMMSS format.
        end_timestamp: End timestamp in YYmmdd_HHMMSS or YYmmddHHMMSS format.

    Returns:
        Duration in seconds, or None if timestamps can't be parsed.
    """
    try:
        eastern = ZoneInfo("America/New_York")
        # Remove underscore if present for parsing (supports both old and new formats)
        clean_start = start_timestamp.replace("_", "")
        clean_end = end_timestamp.replace("_", "")
        start_time = datetime.strptime(clean_start, "%y%m%d%H%M%S")
        start_time = start_time.replace(tzinfo=eastern)
        end_time = datetime.strptime(clean_end, "%y%m%d%H%M%S")
        end_time = end_time.replace(tzinfo=eastern)
        return (end_time - start_time).total_seconds()
    except (ValueError, TypeError):
        return None


def is_hook_zombie(hook: HookEntry) -> bool:
    """Check if a running hook is a zombie (running > 24 hours).

    Args:
        hook: The hook entry to check.

    Returns:
        True if the hook is a zombie, False otherwise.
    """
    if hook.status != "RUNNING":
        return False

    age = _get_hook_file_age_seconds(hook)
    if age is None:
        return False

    return age > HOOK_ZOMBIE_THRESHOLD_SECONDS


def is_timestamp_suffix(suffix: str | None) -> bool:
    """Check if a suffix is a timestamp format (YYmmdd_HHMMSS or YYmmddHHMMSS).

    Args:
        suffix: The suffix value from a HookStatusLine.

    Returns:
        True if the suffix is a valid timestamp format, False otherwise.
    """
    if suffix is None or suffix == "!":
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


def is_suffix_stale(suffix: str | None) -> bool:
    """Check if a suffix contains a stale timestamp (>1h old).

    A stale suffix indicates a fix-hook agent started more than 1 hour ago
    but never completed properly (crashed or was killed).

    Args:
        suffix: The suffix value from a HookStatusLine.

    Returns:
        True if the suffix is a timestamp that is >1 hour old.
    """
    if not is_timestamp_suffix(suffix):
        return False
    # Remove underscore for parsing if present
    clean_suffix = suffix.replace("_", "") if suffix else ""
    age = get_hook_file_age_seconds_from_timestamp(clean_suffix)
    return age is not None and age > FIX_HOOK_STALE_THRESHOLD_SECONDS


def hook_has_any_running_status(hook: HookEntry) -> bool:
    """Check if a hook has any RUNNING status line (not just the latest).

    This is used to detect RUNNING hooks from older history entries
    that may need completion checks.

    Args:
        hook: The hook entry to check.

    Returns:
        True if any status line has RUNNING status.
    """
    if not hook.status_lines:
        return False

    return any(sl.status == "RUNNING" for sl in hook.status_lines)


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


def format_timestamp_display(timestamp: str) -> str:
    """Format a raw timestamp for display.

    Args:
        timestamp: Raw timestamp in YYmmdd_HHMMSS format (13 chars with underscore).

    Returns:
        Formatted timestamp like [YYmmdd_HHMMSS].
    """
    # Timestamp already has underscore between date and time parts
    return f"[{timestamp}]"
