"""Suffix formatting utilities for ChangeSpec detail display.

Contains common styling logic for suffix types used across different sections
(COMMITS, HOOKS, COMMENTS, MENTORS).
"""

from rich.text import Text

from ...display_helpers import is_entry_ref_suffix, is_suffix_timestamp

# Style definitions for suffix types
SUFFIX_STYLES = {
    "error": "bold #FFFFFF on #AF0000",
    "rejected_proposal": "bold #FF5F5F on #444444",
    "running_agent": "bold #FFFFFF on #FF8C00",
    "running_process": "bold #3D2B1F on #FFD700",
    "pending_dead_process": "bold #FFD700 on #444444",
    "killed_process": "bold #B8A800 on #444444",
    "killed_agent": "bold #FF8C00 on #444444",
    "summarize_complete": "bold #FFFFFF on #008B8B",
    "metahook_complete": "bold #FFFFFF on #8B008B",
    "entry_ref": "bold #FF87AF",
}


def _build_suffix_content(
    suffix: str | None,
    summary: str | None,
) -> str:
    """Build the content string combining suffix and summary.

    Args:
        suffix: The suffix value (can be None or empty string).
        summary: Optional summary text to append.

    Returns:
        Combined suffix content string.
    """
    suffix_content = suffix or ""
    if summary:
        if suffix_content:
            suffix_content = f"{suffix_content} | {summary}"
        else:
            suffix_content = summary
    return suffix_content


def append_suffix_to_text(
    text: Text,
    suffix_type: str | None,
    suffix: str | None,
    summary: str | None = None,
    check_entry_ref: bool = False,
) -> None:
    """Append a styled suffix to a Text object.

    Handles the common suffix formatting pattern used across COMMITS, HOOKS,
    COMMENTS, and MENTORS sections.

    Args:
        text: The Rich Text object to append to.
        suffix_type: The type of suffix (error, running_agent, etc.).
        suffix: The suffix value.
        summary: Optional summary text (used in HOOKS section).
        check_entry_ref: Whether to check for entry reference suffix format.
    """
    # Build content combining suffix and summary
    suffix_content = _build_suffix_content(suffix, summary)

    if suffix_type == "error":
        text.append(f"(!: {suffix_content})", style=SUFFIX_STYLES["error"])
    elif suffix_type == "running_agent" or (suffix and is_suffix_timestamp(suffix)):
        if suffix_content:
            text.append(f"(@: {suffix_content})", style=SUFFIX_STYLES["running_agent"])
        else:
            text.append("(@)", style=SUFFIX_STYLES["running_agent"])
    elif suffix_type == "running_process":
        text.append(f"($: {suffix_content})", style=SUFFIX_STYLES["running_process"])
    elif suffix_type == "pending_dead_process":
        text.append(
            f"(?$: {suffix_content})", style=SUFFIX_STYLES["pending_dead_process"]
        )
    elif suffix_type == "killed_process":
        text.append(f"(~$: {suffix_content})", style=SUFFIX_STYLES["killed_process"])
    elif suffix_type == "killed_agent":
        text.append(f"(~@: {suffix_content})", style=SUFFIX_STYLES["killed_agent"])
    elif suffix_type == "rejected_proposal":
        text.append(f"(~!: {suffix_content})", style=SUFFIX_STYLES["rejected_proposal"])
    elif suffix_type == "summarize_complete":
        if suffix_content:
            text.append(
                f"(%: {suffix_content})", style=SUFFIX_STYLES["summarize_complete"]
            )
        else:
            text.append("(%)", style=SUFFIX_STYLES["summarize_complete"])
    elif suffix_type == "metahook_complete":
        if suffix_content:
            text.append(
                f"(!: metahook | {suffix_content})",
                style=SUFFIX_STYLES["metahook_complete"],
            )
        else:
            text.append("(!: metahook)", style=SUFFIX_STYLES["metahook_complete"])
    elif check_entry_ref and suffix and is_entry_ref_suffix(suffix):
        text.append(f"({suffix_content})", style=SUFFIX_STYLES["entry_ref"])
    else:
        text.append(f"({suffix_content})")


def should_show_suffix(
    suffix: str | None,
    suffix_type: str | None,
) -> bool:
    """Determine if a suffix should be displayed.

    Returns True if:
    - suffix is not None AND (suffix is non-empty OR suffix_type is running_agent
      OR suffix_type is running_process)

    Args:
        suffix: The suffix value.
        suffix_type: The type of suffix.

    Returns:
        True if the suffix should be displayed.
    """
    return suffix is not None and (
        bool(suffix)
        or suffix_type == "running_agent"
        or suffix_type == "running_process"
    )
