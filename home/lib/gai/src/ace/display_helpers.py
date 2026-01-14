"""Shared display helper functions for ChangeSpec rendering."""

import re
from collections.abc import Sequence
from typing import Protocol


def get_status_color(status: str) -> str:
    """Get the color for a given status based on vim syntax file.

    Workspace suffixes (e.g., " (fig_3)") are stripped before color lookup.

    Color mapping:
    - WIP: #FFD700 (gold/yellow)
    - Drafted: #87D700 (green)
    - Mailed: #00D787 (cyan-green)
    - Submitted: #00AF00 (green)
    - Reverted: #808080 (gray)
    """
    # Strip workspace suffix before looking up color
    # Pattern: " (<project>_<N>)" at the end of the status
    base_status = re.sub(r" \([a-zA-Z0-9_-]+_\d+\)$", "", status)

    status_colors = {
        "WIP": "#FFD700",
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
    pid: int
    workflow: str
    cl_name: str | None


def format_running_claims_aligned(
    claims: Sequence[_WorkspaceClaimLike],
) -> list[tuple[str, str, str, str | None]]:
    """Format RUNNING field claims with aligned columns.

    Uses minimal padding - only adds spaces where needed for alignment.

    Args:
        claims: List of workspace claim objects with workspace_num, pid, workflow,
            and cl_name attributes.

    Returns:
        List of tuples: (workspace_col, pid_col, workflow_col, cl_name)
        where workspace_col is like "#1" or " #1" (right-aligned),
        pid_col is like "12345" (right-aligned), and
        workflow_col is like "crs      " (left-aligned).
    """
    if not claims:
        return []

    max_ws_len = max(len(str(c.workspace_num)) for c in claims)
    max_pid_len = max(len(str(c.pid)) for c in claims)
    max_wf_len = max(len(c.workflow) for c in claims)

    result: list[tuple[str, str, str, str | None]] = []
    for claim in claims:
        # Right-align workspace number (e.g., " #1" to align with "#99")
        ws_str = f"#{claim.workspace_num}"
        ws_col = f"{ws_str:>{max_ws_len + 1}}"  # +1 for the # character
        # Right-align PID
        pid_col = f"{claim.pid:>{max_pid_len}}"
        # Left-align workflow
        wf_col = f"{claim.workflow:<{max_wf_len}}"
        result.append((ws_col, pid_col, wf_col, claim.cl_name))
    return result


class _MentorStatusLineLike(Protocol):
    """Protocol for mentor status line objects."""

    profile_name: str
    mentor_name: str


def format_profile_with_count(
    profile_name: str,
    status_lines: Sequence[_MentorStatusLineLike] | None,
    is_wip: bool = False,
) -> str:
    """Format profile name with [started/total] count for display.

    Args:
        profile_name: Name of the mentor profile.
        status_lines: List of MentorStatusLine objects to count started mentors.
        is_wip: If True, only count mentors with run_on_wip=True.

    Returns:
        Formatted string like "profile[2/3]".
    """
    from mentor_config import get_mentor_profile_by_name

    profile_config = get_mentor_profile_by_name(profile_name)
    if profile_config is None:
        return profile_name  # Fallback if profile not found in config

    # Calculate total based on WIP status
    if is_wip:
        total = sum(1 for m in profile_config.mentors if m.run_on_wip)
        wip_mentor_names = {
            m.mentor_name for m in profile_config.mentors if m.run_on_wip
        }
    else:
        total = len(profile_config.mentors)
        wip_mentor_names = None

    started = 0
    if status_lines:
        for sl in status_lines:
            if sl.profile_name == profile_name:
                # For WIP, only count status lines for run_on_wip mentors
                if wip_mentor_names is None or sl.mentor_name in wip_mentor_names:
                    started += 1

    return f"{profile_name}[{started}/{total}]"
