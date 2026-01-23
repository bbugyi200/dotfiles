"""COMMENTS section builder for ChangeSpec detail display."""

import os
from pathlib import Path

from rich.text import Text

from ...changespec import ChangeSpec
from .hint_tracker import HintTracker
from .suffix_formatting import append_suffix_to_text, should_show_suffix


def build_comments_section(
    text: Text,
    changespec: ChangeSpec,
    show_comment_hints: bool,
    hint_tracker: HintTracker,
) -> HintTracker:
    """Build the COMMENTS section of the display.

    Args:
        text: The Rich Text object to append to.
        changespec: The ChangeSpec to display.
        show_comment_hints: Whether to show file path hints.
        hint_tracker: Current hint tracking state.

    Returns:
        Updated HintTracker with new hint mappings.
    """
    if not changespec.comments:
        return hint_tracker

    hint_counter = hint_tracker.counter
    hint_mappings = dict(hint_tracker.mappings)

    text.append("COMMENTS:\n", style="bold #87D7FF")
    for comment in changespec.comments:
        text.append("  ", style="")
        # Add hint before the reviewer if enabled
        if show_comment_hints:
            full_path = os.path.expanduser(comment.file_path)
            hint_mappings[hint_counter] = full_path
            text.append(f"[{hint_counter}] ", style="bold #FFFF00")
            hint_counter += 1
        text.append(f"[{comment.reviewer}]", style="bold #D7AF5F")
        text.append(" ", style="")
        display_path = comment.file_path.replace(str(Path.home()), "~")
        text.append(display_path, style="#87AFFF")
        # Handle running_agent/running_process with suffix (for consistency)
        if should_show_suffix(comment.suffix, comment.suffix_type):
            text.append(" - ")
            append_suffix_to_text(
                text,
                comment.suffix_type,
                comment.suffix,
                summary=None,
                check_entry_ref=True,
            )
        text.append("\n")

    return HintTracker(
        counter=hint_counter,
        mappings=hint_mappings,
        hook_hint_to_idx=hint_tracker.hook_hint_to_idx,
        hint_to_entry_id=hint_tracker.hint_to_entry_id,
        mentor_hint_to_info=hint_tracker.mentor_hint_to_info,
    )
