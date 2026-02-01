"""Timestamp parsing and extraction utilities for agent loading."""

from datetime import datetime


def extract_timestamp_str_from_suffix(suffix: str | None) -> str | None:
    """Extract raw timestamp string from agent suffix.

    Examples:
        - "mentor_complete-1855023-260112_134051" -> "260112_134051"
        - "fix_hook-12345-251230_151429" -> "251230_151429"
        - "crs-12345-251230_151429" -> "251230_151429"

    Args:
        suffix: The suffix value to parse.

    Returns:
        Timestamp string in YYmmdd_HHMMSS format, or None if not found.
    """
    if not suffix or "-" not in suffix:
        return None
    last_part = suffix.split("-")[-1]
    if len(last_part) == 13 and last_part[6] == "_":
        return last_part
    return None


def extract_timestamp_from_workflow(workflow: str | None) -> str | None:
    """Extract timestamp from axe workflow names.

    Examples:
        - "axe(mentor)-complete-260112_134051" -> "260112_134051"
        - "axe(fix-hook)-260112_134051" -> "260112_134051"
        - "axe(crs)-critique" -> None (no timestamp)
        - "ace(run)-260112_134051" -> "260112_134051"

    Args:
        workflow: The workflow name to parse.

    Returns:
        Timestamp string in YYmmdd_HHMMSS format, or None if not found.
    """
    if not workflow or "-" not in workflow:
        return None
    # Look for YYmmdd_HHMMSS pattern at end
    last_part = workflow.split("-")[-1]
    if len(last_part) == 13 and last_part[6] == "_":
        return last_part
    return None


def parse_timestamp_from_suffix(suffix: str | None) -> datetime | None:
    """Parse start time from agent suffix format.

    Format: <agent>-<PID>-YYmmdd_HHMMSS (e.g., fix_hook-12345-251230_151429)

    Args:
        suffix: The suffix value to parse.

    Returns:
        Parsed datetime, or None if parsing fails.
    """
    if suffix is None or "-" not in suffix:
        return None

    parts = suffix.split("-")
    # Format: <agent>-<PID>-YYmmdd_HHMMSS
    if len(parts) >= 3:
        ts = parts[-1]
        if len(ts) == 13 and ts[6] == "_":
            try:
                return datetime.strptime(ts, "%y%m%d_%H%M%S")
            except ValueError:
                pass

    return None


def parse_timestamp_13_char(timestamp_str: str) -> datetime | None:
    """Parse a 13-character timestamp string (YYmmdd_HHMMSS).

    Args:
        timestamp_str: The timestamp string to parse.

    Returns:
        Parsed datetime, or None if parsing fails.
    """
    if len(timestamp_str) != 13 or timestamp_str[6] != "_":
        return None
    try:
        return datetime.strptime(timestamp_str, "%y%m%d_%H%M%S")
    except ValueError:
        return None


def parse_timestamp_from_workflow_name(workflow: str | None) -> datetime | None:
    """Parse timestamp from workflow name as fallback.

    Args:
        workflow: Workflow name like "axe(fix-hook)-260112_134051"

    Returns:
        Parsed datetime, or None if not extractable.
    """
    ts_str = extract_timestamp_from_workflow(workflow)
    if ts_str:
        return parse_timestamp_13_char(ts_str)
    return None


def parse_timestamp_14_digit(timestamp_str: str) -> datetime | None:
    """Parse a 14-digit timestamp string (YYYYmmddHHMMSS).

    Args:
        timestamp_str: The timestamp string to parse.

    Returns:
        Parsed datetime, or None if parsing fails.
    """
    if len(timestamp_str) != 14 or not timestamp_str.isdigit():
        return None
    try:
        return datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
    except ValueError:
        return None
