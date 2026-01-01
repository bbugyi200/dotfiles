"""Core hook utilities - timestamps, duration, history, and status checks."""

from datetime import datetime
from zoneinfo import ZoneInfo

from ..changespec import (
    ChangeSpec,
    CommitEntry,
    HookEntry,
    is_error_suffix,
)
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


def _parent_hook_passed_or_is_fix_proposal(
    hook: HookEntry,
    entry_id: str,
) -> bool:
    """Check if a proposal can run this hook based on parent status.

    A proposal entry can run a hook if:
    1. The parent entry has PASSED for this hook, OR
    2. This proposal was created by fix-hook to fix THIS hook's failure
       (detected by parent's status line having suffix == proposal's ID)

    Args:
        hook: The hook entry to check.
        entry_id: The proposal entry ID (e.g., "2a").

    Returns:
        True if the hook can run on this proposal, False if it should wait.
    """
    from accept_workflow.parsing import parse_proposal_id

    parsed = parse_proposal_id(entry_id)
    if parsed is None:
        return True  # Not a valid proposal format - allow

    base_number, _letter = parsed
    parent_entry_id = str(base_number)

    parent_status_line = hook.get_status_line_for_commit_entry(parent_entry_id)

    if parent_status_line is None:
        return False  # No parent status - wait

    # Fix-hook exception: suffix matches this proposal's ID
    if parent_status_line.suffix == entry_id:
        return True

    # Check if parent PASSED
    return parent_status_line.status == "PASSED"


def hook_needs_run(hook: HookEntry, last_history_entry_id: str | None) -> bool:
    """Determine if a hook needs to be run.

    A hook needs to run if no status line exists for the current HISTORY entry.
    Hooks prefixed with "$" are skipped for proposal entries (e.g., "2a").
    For proposals, the parent entry must have PASSED this hook first (unless
    this proposal was created by fix-hook to fix this specific hook).

    Args:
        hook: The hook entry to check.
        last_history_entry_id: The ID of the last HISTORY entry (e.g., '1', '1a').

    Returns:
        True if the hook should be run, False otherwise.
    """
    # If there's no history entry ID, don't run (no history means nothing to run)
    if last_history_entry_id is None:
        return False

    # "$" prefixed hooks are skipped for proposals
    if hook.skip_proposal_runs and is_proposal_entry(last_history_entry_id):
        return False

    # Check if there's a status line for this history entry
    status_line = hook.get_status_line_for_commit_entry(last_history_entry_id)
    if status_line is not None:
        return False

    # For proposals, check if parent has passed (or fix-hook exception)
    if is_proposal_entry(last_history_entry_id):
        if not _parent_hook_passed_or_is_fix_proposal(hook, last_history_entry_id):
            return False

    return True


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


def is_hook_zombie(
    hook: HookEntry,
    zombie_timeout_seconds: int = DEFAULT_ZOMBIE_TIMEOUT_SECONDS,
) -> bool:
    """Check if a running hook is a zombie (running longer than timeout).

    Args:
        hook: The hook entry to check.
        zombie_timeout_seconds: Timeout in seconds (default: 2 hours).

    Returns:
        True if the hook is a zombie, False otherwise.
    """
    if hook.status != "RUNNING":
        return False

    age = _get_hook_file_age_seconds(hook)
    if age is None:
        return False

    return age > zombie_timeout_seconds


def is_timestamp_suffix(suffix: str | None) -> bool:
    """Check if a suffix is a timestamp format (YYmmdd_HHMMSS or YYmmddHHMMSS).

    Args:
        suffix: The suffix value from a HookStatusLine.

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
    if not is_timestamp_suffix(suffix):
        return False
    # Remove underscore for parsing if present
    clean_suffix = suffix.replace("_", "") if suffix else ""
    age = get_hook_file_age_seconds_from_timestamp(clean_suffix)
    return age is not None and age > zombie_timeout_seconds


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


def entry_has_running_hooks(hooks: list[HookEntry] | None, entry_id: str) -> bool:
    """Check if any hooks have RUNNING status for a specific history entry.

    Args:
        hooks: List of hook entries to check.
        entry_id: The history entry ID (e.g., "1", "1a", "2").

    Returns:
        True if any hook has a RUNNING status line for the specified entry.
    """
    if not hooks:
        return False
    for hook in hooks:
        if not hook.status_lines:
            continue
        for sl in hook.status_lines:
            if sl.commit_entry_num == entry_id and sl.status == "RUNNING":
                return True
    return False


def format_timestamp_display(timestamp: str) -> str:
    """Format a raw timestamp for display.

    Args:
        timestamp: Raw timestamp in YYmmdd_HHMMSS format (13 chars with underscore).

    Returns:
        Formatted timestamp like [YYmmdd_HHMMSS].
    """
    # Timestamp already has underscore between date and time parts
    return f"[{timestamp}]"


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


def get_entries_needing_hook_run(hook: HookEntry, entry_ids: list[str]) -> list[str]:
    """Get entry IDs that need this hook to run.

    Returns entry IDs from the given list that don't have a status line
    for this hook yet, respecting the skip_proposal_runs flag and parent-passed
    requirement for proposals.

    Args:
        hook: The hook entry to check.
        entry_ids: List of entry IDs to check (e.g., ["3", "3a"]).

    Returns:
        List of entry IDs that need the hook to run.
    """
    result = []
    for entry_id in entry_ids:
        # Skip proposals for $ prefixed hooks
        if hook.skip_proposal_runs and is_proposal_entry(entry_id):
            continue
        # Check if there's already a status line for this entry
        if hook.get_status_line_for_commit_entry(entry_id) is not None:
            continue
        # For proposals, check if parent has passed (or fix-hook exception)
        if is_proposal_entry(entry_id):
            if not _parent_hook_passed_or_is_fix_proposal(hook, entry_id):
                continue
        result.append(entry_id)
    return result
