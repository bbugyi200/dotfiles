"""COMMITS section builder for ChangeSpec detail display."""

import os
import re
from pathlib import Path

from rich.text import Text

from ...changespec import ChangeSpec, CommitEntry
from ...display_helpers import is_suffix_timestamp
from .hint_tracker import HintTracker


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


def _get_rejected_proposals_for_entry(
    entry: CommitEntry,
    all_commits: list[CommitEntry],
    max_number: int,
) -> list[CommitEntry]:
    """Get rejected proposals that belong to this parent entry.

    A proposal is rejected if its number doesn't match the max (latest) number.

    Args:
        entry: The parent (non-proposal) entry to check.
        all_commits: All commit entries in the ChangeSpec.
        max_number: The highest numeric commit entry number.

    Returns:
        List of rejected proposals for this parent entry.
    """
    if entry.is_proposed:
        return []  # Only regular entries can have proposals folded under them

    return [
        e
        for e in all_commits
        if e.is_proposed
        and e.number == entry.number  # Same base number
        and e.number != max_number  # Not the latest (i.e., rejected)
    ]


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

    # Calculate max_number once before the loop for rejected proposal detection
    max_number = max(
        (e.number for e in changespec.commits if not e.is_proposed),
        default=0,
    )

    text.append("COMMITS:\n", style="bold #87D7FF")
    for entry in changespec.commits:
        # Skip rejected proposals when collapsed (they're folded under parent)
        if commits_collapsed and entry.is_proposed and entry.number != max_number:
            continue

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
            elif entry.suffix_type == "rejected_proposal":
                # Grey background with red text for rejected proposal
                text.append(f"(~!: {entry.suffix})", style="bold #FF5F5F on #444444")
            else:
                text.append(f"({entry.suffix})")

        # Determine if drawers should be shown for this entry
        show_drawers = _should_show_commits_drawers(
            entry, changespec, commits_collapsed
        )

        # Add folded suffix if drawers are hidden or proposals are folded
        rejected_proposals = (
            _get_rejected_proposals_for_entry(entry, changespec.commits, max_number)
            if commits_collapsed
            else []
        )
        has_folded_drawers = not show_drawers and (entry.chat or entry.diff)
        has_folded_content = has_folded_drawers or rejected_proposals

        if has_folded_content:
            text.append("  [folded: ", style="italic #808080")
            parts: list[tuple[str, str]] = []
            if not show_drawers and entry.chat:
                parts.append(("CHAT", "bold #87D7FF"))
            if not show_drawers and entry.diff:
                parts.append(("DIFF", "bold #87D7FF"))
            if rejected_proposals:
                count = len(rejected_proposals)
                label = f"{count} proposal{'s' if count > 1 else ''}"
                parts.append((label, "bold #87D7FF"))

            for i, (label, style) in enumerate(parts):
                if i > 0:
                    text.append(" + ", style="italic #808080")
                text.append(label, style=style)
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
        mentor_hint_to_info=hint_tracker.mentor_hint_to_info,
    )
