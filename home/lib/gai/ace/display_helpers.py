"""Shared display helper functions for ChangeSpec rendering."""

import re
from collections.abc import Sequence
from typing import Protocol


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


class _WorkspaceClaimLike(Protocol):
    """Protocol for workspace claim objects."""

    workspace_num: int
    workflow: str
    cl_name: str | None


def format_running_claims_aligned(
    claims: Sequence[_WorkspaceClaimLike],
) -> list[tuple[str, str, str | None]]:
    """Format RUNNING field claims with aligned columns.

    Uses minimal padding - only adds spaces where needed for alignment.

    Args:
        claims: List of workspace claim objects with workspace_num, workflow,
            and cl_name attributes.

    Returns:
        List of tuples: (formatted_workspace_col, formatted_workflow_col, cl_name)
        where formatted_workspace_col is like "#1" or " #1" (right-aligned) and
        formatted_workflow_col is like "crs      " (left-aligned).
    """
    if not claims:
        return []

    max_ws_len = max(len(str(c.workspace_num)) for c in claims)
    max_wf_len = max(len(c.workflow) for c in claims)

    result: list[tuple[str, str, str | None]] = []
    for claim in claims:
        # Right-align the entire "#N" string (e.g., " #1" to align with "#99")
        ws_str = f"#{claim.workspace_num}"
        ws_col = f"{ws_str:>{max_ws_len + 1}}"  # +1 for the # character
        wf_col = f"{claim.workflow:<{max_wf_len}}"
        result.append((ws_col, wf_col, claim.cl_name))
    return result
