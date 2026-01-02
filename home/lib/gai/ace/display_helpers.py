"""Shared display helper functions for ChangeSpec rendering."""

import re


def get_bug_field(project_file: str) -> str | None:
    """Get the BUG field from a project file if it exists.

    Args:
        project_file: Path to the ProjectSpec file.

    Returns:
        BUG field value, or None if not found.
    """
    try:
        with open(project_file, encoding="utf-8") as f:
            for line in f:
                if line.startswith("BUG:"):
                    value = line.split(":", 1)[1].strip()
                    if value and value != "None":
                        return value
                    break
    except Exception:
        pass

    return None


def get_status_color(status: str) -> str:
    """Get the color for a given status based on vim syntax file.

    Workspace suffixes (e.g., " (fig_3)") are stripped before color lookup.

    Color mapping:
    - Making Change Requests...: #87AFFF (blue/purple)
    - Running QA...: #87AFFF (blue/purple)
    - Drafted: #87D700 (green)
    - Mailed: #00D787 (cyan-green)
    - Submitted: #00AF00 (green)
    - Reverted: #808080 (gray)
    """
    # Strip workspace suffix before looking up color
    # Pattern: " (<project>_<N>)" at the end of the status
    base_status = re.sub(r" \([a-zA-Z0-9_-]+_\d+\)$", "", status)

    status_colors = {
        "Drafted": "#87D700",
        "Mailed": "#00D787",
        "Submitted": "#00AF00",
        "Reverted": "#808080",
    }
    return status_colors.get(base_status, "#FFFFFF")


def is_suffix_timestamp(suffix: str) -> bool:
    """Check if a suffix is a timestamp format for display styling.

    Args:
        suffix: The suffix value from a HookStatusLine.

    Returns:
        True if the suffix looks like a timestamp, False otherwise.
    """
    # New format: 13 chars with underscore at position 6 (YYmmdd_HHMMSS)
    if len(suffix) == 13 and suffix[6] == "_":
        return True
    # Legacy format: 12 digits (YYmmddHHMMSS)
    if len(suffix) == 12 and suffix.isdigit():
        return True
    return False


def is_entry_ref_suffix(suffix: str | None) -> bool:
    """Check if a suffix is an entry reference (e.g., '2', '3', '1a', '2b').

    Args:
        suffix: The suffix value from a HookStatusLine.

    Returns:
        True if the suffix looks like an entry ID, False otherwise.
    """
    if not suffix:
        return False
    return bool(re.match(r"^\d+[a-z]?$", suffix))
