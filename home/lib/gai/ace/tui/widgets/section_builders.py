"""Section builders for ChangeSpec detail display.

Contains functions for building COMMITS, HOOKS, COMMENTS, and MENTORS sections.
"""

import os
import re
from pathlib import Path
from typing import NamedTuple

from accept_workflow.parsing import parse_proposal_id
from rich.text import Text

from ...changespec import (
    ChangeSpec,
    CommitEntry,
    HookEntry,
    get_current_and_proposal_entry_ids,
    parse_commit_entry_id,
)
from ...display_helpers import is_suffix_timestamp
from ...hooks import (
    contract_test_target_command,
    format_timestamp_display,
    get_hook_output_path,
)
from .suffix_formatting import append_suffix_to_text, should_show_suffix


class HintTracker(NamedTuple):
    """Tracks hint state during section building."""

    counter: int
    mappings: dict[int, str]
    hook_hint_to_idx: dict[int, int]
    hint_to_entry_id: dict[int, str]


def _should_show_commits_drawers(
    entry: CommitEntry,
    changespec: ChangeSpec,
    commits_collapsed: bool,
) -> bool:
    """Determine if drawers should be shown for a COMMITS entry.

    When collapsed, show drawers only for:
    - Proposal entries (like "8a") where 8 is the highest numeric ID

    Hide drawers for:
    - All regular entries including entry 1 and the current entry

    When expanded, show all drawers.
    """
    if not commits_collapsed:
        return True
    # Show proposal entries for highest numeric ID only
    if entry.is_proposed and changespec.commits:
        max_number = max(
            (e.number for e in changespec.commits if not e.is_proposed),
            default=0,
        )
        if entry.number == max_number:
            return True
    return False


def _is_fix_hook_proposal_for_this_hook(
    hook: HookEntry,
    entry_id: str,
    changespec: ChangeSpec,
) -> bool:
    """Check if this is a fix-hook proposal running the hook it was fixing.

    A proposal (e.g., "2a") is a fix-hook proposal for a specific hook if
    the parent entry's (e.g., "2") status line for that hook has
    suffix == proposal's ID (e.g., suffix="2a").

    Only returns True for "new" proposals where the base number matches
    the highest all-numeric commit (e.g., if highest is 6, only 6a/6b/etc
    qualify, not 1a or 2a).

    Args:
        hook: The hook entry to check.
        entry_id: The commit entry ID (e.g., "2a").
        changespec: The ChangeSpec containing commits to check against.

    Returns:
        True if this is a fix-hook proposal running its target hook.
    """
    parsed = parse_proposal_id(entry_id)
    if parsed is None:
        return False  # Not a proposal format

    base_number, _letter = parsed

    # Only show for NEW proposals (base number == highest all-numeric commit)
    if not changespec.commits:
        return False
    max_number = max(
        (e.number for e in changespec.commits if not e.is_proposed),
        default=0,
    )
    if base_number != max_number:
        return False

    parent_entry_id = str(base_number)

    parent_status_line = hook.get_status_line_for_commit_entry(parent_entry_id)
    if parent_status_line is None:
        return False

    # Fix-hook exception: parent's suffix matches this proposal's ID
    return parent_status_line.suffix == entry_id


def build_commits_section(
    text: Text,
    changespec: ChangeSpec,
    show_history_hints: bool,
    commits_collapsed: bool,
    hint_tracker: HintTracker,
) -> HintTracker:
    """Build the COMMITS section of the display.

    Args:
        text: The Rich Text object to append to.
        changespec: The ChangeSpec to display.
        show_history_hints: Whether to show file path hints.
        commits_collapsed: Whether to collapse commit drawer lines.
        hint_tracker: Current hint tracking state.

    Returns:
        Updated HintTracker with new hint mappings.
    """
    if not changespec.commits:
        return hint_tracker

    hint_counter = hint_tracker.counter
    hint_mappings = dict(hint_tracker.mappings)

    text.append("COMMITS:\n", style="bold #87D7FF")
    for entry in changespec.commits:
        entry_style = "bold #D7AF5F"
        text.append(f"  ({entry.display_number}) ", style=entry_style)

        # Check if note contains a file path in parentheses
        note_path_match = re.search(r"\((~/[^)]+)\)", entry.note)
        if show_history_hints and note_path_match:
            # Split the note around the path and add hint
            note_path = note_path_match.group(1)
            full_path = os.path.expanduser(note_path)
            hint_mappings[hint_counter] = full_path
            before_path = entry.note[: note_path_match.start()]
            after_path = entry.note[note_path_match.end() :]
            text.append(before_path, style="#D7D7AF")
            text.append("(", style="#D7D7AF")
            text.append(f"[{hint_counter}] ", style="bold #FFFF00")
            text.append(note_path, style="#87AFFF")
            text.append(f"){after_path}", style="#D7D7AF")
            hint_counter += 1
        else:
            text.append(f"{entry.note}", style="#D7D7AF")

        if entry.suffix:
            text.append(" - ")
            if entry.suffix_type == "error":
                text.append(f"(!: {entry.suffix})", style="bold #FFFFFF on #AF0000")
            elif entry.suffix_type == "running_agent" or is_suffix_timestamp(
                entry.suffix
            ):
                # Orange background with white text (same as @@@ query)
                text.append(f"(@: {entry.suffix})", style="bold #FFFFFF on #FF8C00")
            elif entry.suffix_type == "running_process":
                # Yellow background with dark brown text (same as $$$ query)
                text.append(f"($: {entry.suffix})", style="bold #3D2B1F on #FFD700")
            elif entry.suffix_type == "pending_dead_process":
                # Grey background with yellow text for pending dead process
                text.append(f"(?$: {entry.suffix})", style="bold #FFD700 on #444444")
            elif entry.suffix_type == "killed_process":
                # Grey background with olive text for killed process
                text.append(f"(~$: {entry.suffix})", style="bold #B8A800 on #444444")
            else:
                text.append(f"({entry.suffix})")

        # Determine if drawers should be shown for this entry
        show_drawers = _should_show_commits_drawers(
            entry, changespec, commits_collapsed
        )

        # Add folded suffix if drawers are hidden
        if not show_drawers and (entry.chat or entry.diff):
            text.append("  [folded: ", style="italic #808080")
            if entry.chat:
                text.append("CHAT", style="bold #87D7FF")
            if entry.chat and entry.diff:
                text.append(" + ", style="italic #808080")
            if entry.diff:
                text.append("DIFF", style="bold #87D7FF")
            text.append("]", style="italic #808080")

        text.append("\n")

        # CHAT field - only show if drawers visible
        if entry.chat and show_drawers:
            text.append("      ", style="")
            # Parse duration suffix from chat (e.g., "path (1h2m3s)")
            chat_duration_match = re.search(r" \((\d+[hms]+[^)]*)\)$", entry.chat)
            if chat_duration_match:
                chat_path_raw = entry.chat[: chat_duration_match.start()]
                chat_duration = chat_duration_match.group(1)
            else:
                chat_path_raw = entry.chat
                chat_duration = None
            if show_history_hints:
                hint_mappings[hint_counter] = chat_path_raw
                text.append(f"[{hint_counter}] ", style="bold #FFFF00")
                hint_counter += 1
            text.append("| ", style="#808080")
            text.append("CHAT: ", style="bold #87D7FF")
            chat_path = chat_path_raw.replace(str(Path.home()), "~")
            text.append(chat_path, style="#87AFFF")
            if chat_duration:
                text.append(f" ({chat_duration})", style="#808080")
            text.append("\n")

        # DIFF field - only show if drawers visible
        if entry.diff and show_drawers:
            text.append("      ", style="")
            if show_history_hints:
                hint_mappings[hint_counter] = entry.diff
                text.append(f"[{hint_counter}] ", style="bold #FFFF00")
                hint_counter += 1
            text.append("| ", style="#808080")
            text.append("DIFF: ", style="bold #87D7FF")
            diff_path = entry.diff.replace(str(Path.home()), "~")
            text.append(f"{diff_path}\n", style="#87AFFF")

    return HintTracker(
        counter=hint_counter,
        mappings=hint_mappings,
        hook_hint_to_idx=hint_tracker.hook_hint_to_idx,
        hint_to_entry_id=hint_tracker.hint_to_entry_id,
    )


def build_hooks_section(
    text: Text,
    changespec: ChangeSpec,
    with_hints: bool,
    hints_for: str | None,
    hooks_collapsed: bool,
    non_historical_ids: set[str],
    hint_tracker: HintTracker,
) -> HintTracker:
    """Build the HOOKS section of the display.

    Args:
        text: The Rich Text object to append to.
        changespec: The ChangeSpec to display.
        with_hints: Whether hints are enabled.
        hints_for: Controls which entries get hints.
        hooks_collapsed: Whether to collapse hook status lines.
        non_historical_ids: Set of current/proposal entry IDs.
        hint_tracker: Current hint tracking state.

    Returns:
        Updated HintTracker with new hint mappings.
    """
    if not changespec.hooks:
        return hint_tracker

    hint_counter = hint_tracker.counter
    hint_mappings = dict(hint_tracker.mappings)
    hook_hint_to_idx = dict(hint_tracker.hook_hint_to_idx)
    hint_to_entry_id = dict(hint_tracker.hint_to_entry_id)

    # Get current + proposal entry IDs for filtering
    current_and_proposal_ids = set(get_current_and_proposal_entry_ids(changespec))

    text.append("HOOKS:\n", style="bold #87D7FF")
    for hook_idx, hook in enumerate(changespec.hooks):
        # When collapsed, collect hidden status IDs for summary
        passed_ids: list[str] = []
        failed_ids: list[str] = []  # Historical only
        dead_ids: list[str] = []  # Historical only
        if hooks_collapsed and hook.status_lines:
            for sl in hook.status_lines:
                if sl.status == "PASSED":
                    # Exclude fix-hook proposal PASSED (shown, not folded)
                    if not _is_fix_hook_proposal_for_this_hook(
                        hook, sl.commit_entry_num, changespec
                    ):
                        passed_ids.append(sl.commit_entry_num)
                elif sl.status == "FAILED":
                    # Only collect historical FAILED (not current/proposals)
                    if sl.commit_entry_num not in current_and_proposal_ids:
                        failed_ids.append(sl.commit_entry_num)
                elif sl.status == "DEAD":
                    # Only collect historical DEAD (not current/proposals)
                    if sl.commit_entry_num not in current_and_proposal_ids:
                        dead_ids.append(sl.commit_entry_num)
            # Sort all IDs by commit entry ID order
            passed_ids.sort(key=parse_commit_entry_id)
            failed_ids.sort(key=parse_commit_entry_id)
            dead_ids.sort(key=parse_commit_entry_id)

        # Hook command line with optional status summary
        # Contract test target commands to shorthand format
        display_command = contract_test_target_command(hook.command)
        text.append(f"  {display_command}", style="#D7D7AF")
        if hooks_collapsed and (passed_ids or failed_ids or dead_ids):
            text.append("  [folded: ", style="italic #808080")  # Grey italic
            # Build sections for each status type
            sections: list[tuple[str, str, list[str]]] = []
            if passed_ids:
                sections.append(("PASSED", "#00AF00", passed_ids))
            if failed_ids:
                sections.append(("FAILED", "#FF5F5F", failed_ids))
            if dead_ids:
                sections.append(("DEAD", "#B8A800", dead_ids))
            for i, (status, color, ids) in enumerate(sections):
                if i > 0:
                    text.append(" | ", style="italic #808080")
                text.append(status, style=f"bold italic {color}")
                text.append(": ", style="italic")
                for j, entry_id in enumerate(ids):
                    if j > 0:
                        text.append(" ", style="italic")
                    text.append(entry_id, style="bold italic #D7AF5F")
            text.append("]", style="italic #808080")
        text.append("\n")

        if hook.status_lines:
            sorted_status_lines = sorted(
                hook.status_lines,
                key=lambda sl: parse_commit_entry_id(sl.commit_entry_num),
            )
            for sl in sorted_status_lines:
                # Determine if we should show this status line
                if hooks_collapsed:
                    # When collapsed:
                    # - PASSED: hide unless fix-hook proposal for this hook
                    # - RUNNING: always show
                    # - FAILED/DEAD in current/proposals: show
                    # - FAILED/DEAD historical: hide
                    if sl.status == "PASSED":
                        if not _is_fix_hook_proposal_for_this_hook(
                            hook, sl.commit_entry_num, changespec
                        ):
                            continue
                    if sl.status in ("FAILED", "DEAD"):
                        if sl.commit_entry_num not in current_and_proposal_ids:
                            continue

                text.append("      ", style="")
                text.append("| ", style="#808080")
                # Determine if we should show a hint for this status line
                show_hint = False
                if with_hints:
                    if hints_for == "hooks_latest_only":
                        show_hint = sl.commit_entry_num in non_historical_ids
                    else:
                        show_hint = True

                if show_hint:
                    hook_output_path = get_hook_output_path(
                        changespec.name, sl.timestamp
                    )
                    hint_mappings[hint_counter] = hook_output_path
                    if hints_for == "hooks_latest_only":
                        hook_hint_to_idx[hint_counter] = hook_idx
                        hint_to_entry_id[hint_counter] = sl.commit_entry_num
                    text.append(f"[{hint_counter}] ", style="bold #FFFF00")
                    hint_counter += 1

                text.append(f"({sl.commit_entry_num}) ", style="bold #D7AF5F")
                ts_display = format_timestamp_display(sl.timestamp)
                text.append(f"{ts_display} ", style="#AF87D7")
                if sl.status == "PASSED":
                    text.append(sl.status, style="bold #00AF00")
                elif sl.status == "FAILED":
                    text.append(sl.status, style="bold #FF5F5F")
                elif sl.status == "RUNNING":
                    text.append(sl.status, style="bold #FFD700")
                elif sl.status == "DEAD":
                    text.append(sl.status, style="bold #B8A800")
                else:
                    text.append(sl.status)
                if sl.duration:
                    text.append(f" ({sl.duration})", style="#808080")
                # Handle running_agent/running_process with suffix (RUNNING hooks)
                if should_show_suffix(sl.suffix, sl.suffix_type):
                    text.append(" - ")
                    append_suffix_to_text(
                        text,
                        sl.suffix_type,
                        sl.suffix,
                        summary=sl.summary,
                        check_entry_ref=True,
                    )
                text.append("\n")

    return HintTracker(
        counter=hint_counter,
        mappings=hint_mappings,
        hook_hint_to_idx=hook_hint_to_idx,
        hint_to_entry_id=hint_to_entry_id,
    )


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
                check_entry_ref=False,
            )
        text.append("\n")

    return HintTracker(
        counter=hint_counter,
        mappings=hint_mappings,
        hook_hint_to_idx=hint_tracker.hook_hint_to_idx,
        hint_to_entry_id=hint_tracker.hint_to_entry_id,
    )


def build_mentors_section(
    text: Text,
    changespec: ChangeSpec,
    mentors_collapsed: bool = True,
) -> None:
    """Build the MENTORS section of the display.

    Args:
        text: The Rich Text object to append to.
        changespec: The ChangeSpec to display.
        mentors_collapsed: Whether to collapse mentor status lines.
    """
    if not changespec.mentors:
        return

    text.append("MENTORS:\n", style="bold #87D7FF")

    for mentor_entry in changespec.mentors:
        # Count non-RUNNING statuses for folded summary
        passed_count = 0
        failed_count = 0
        dead_count = 0
        if mentor_entry.status_lines:
            for msl in mentor_entry.status_lines:
                if msl.status == "PASSED":
                    passed_count += 1
                elif msl.status == "FAILED":
                    failed_count += 1
                elif msl.status == "DEAD":
                    dead_count += 1

        # Entry line (2-space indented): (N) profile1 [profile2 ...]
        text.append("  ", style="")
        text.append(f"({mentor_entry.entry_id}) ", style="bold #D7AF5F")
        text.append(" ".join(mentor_entry.profiles), style="#D7D7AF")

        # Add folded suffix if collapsed and has non-RUNNING statuses
        if mentors_collapsed and (passed_count or failed_count or dead_count):
            text.append("  [folded: ", style="italic #808080")
            parts: list[tuple[str, int, str]] = []
            if passed_count:
                parts.append(("PASSED", passed_count, "#00AF00"))
            if failed_count:
                parts.append(("FAILED", failed_count, "#FF5F5F"))
            if dead_count:
                parts.append(("DEAD", dead_count, "#B8A800"))
            for i, (status, count, color) in enumerate(parts):
                if i > 0:
                    text.append(" | ", style="italic #808080")
                text.append(status, style=f"bold italic {color}")
                text.append(f": {count}", style="italic #808080")
            text.append("]", style="italic #808080")

        text.append("\n")

        # Status lines (if present) - 6-space indented
        if mentor_entry.status_lines:
            for msl in mentor_entry.status_lines:
                # Skip non-RUNNING when collapsed
                if mentors_collapsed and msl.status != "RUNNING":
                    continue

                text.append("      ", style="")
                text.append("| ", style="#808080")
                # Format: profile:mentor - STATUS - (suffix/duration)
                text.append(
                    f"{msl.profile_name}:{msl.mentor_name}",
                    style="bold #87AFFF",
                )
                text.append(" - ", style="")
                # Color based on status
                if msl.status == "PASSED":
                    text.append(msl.status, style="bold #00AF00")
                elif msl.status == "FAILED":
                    text.append(msl.status, style="bold #FF5F5F")
                elif msl.status == "RUNNING":
                    text.append(msl.status, style="bold #FFD700")
                else:
                    text.append(msl.status)
                # Duration (if present)
                if msl.duration:
                    text.append(f" - ({msl.duration})", style="#808080")
                # Suffix (if present)
                if msl.suffix is not None and (
                    msl.suffix or msl.suffix_type == "running_agent"
                ):
                    text.append(" - ")
                    append_suffix_to_text(
                        text,
                        msl.suffix_type,
                        msl.suffix,
                        summary=None,
                        check_entry_ref=True,
                    )
                text.append("\n")
