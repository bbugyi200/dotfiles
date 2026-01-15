"""MENTORS section builder for ChangeSpec detail display."""

from rich.text import Text

from ...changespec import ChangeSpec
from ...hooks import format_timestamp_display
from ...scheduler.mentor_runner import get_mentor_chat_path
from .hint_tracker import HintTracker
from .suffix_formatting import append_suffix_to_text


def build_mentors_section(
    text: Text,
    changespec: ChangeSpec,
    mentors_collapsed: bool = True,
    with_hints: bool = False,
    hint_tracker: HintTracker | None = None,
) -> HintTracker:
    """Build the MENTORS section of the display.

    Args:
        text: The Rich Text object to append to.
        changespec: The ChangeSpec to display.
        mentors_collapsed: Whether to collapse mentor status lines.
        with_hints: Whether to show hint numbers for viewable entries.
        hint_tracker: Current hint tracking state (counter, mappings, etc.).

    Returns:
        Updated HintTracker with new hints added.
    """
    # Initialize hint tracking
    hint_counter = hint_tracker.counter if hint_tracker else 0
    hint_mappings = dict(hint_tracker.mappings) if hint_tracker else {}
    hook_hint_to_idx = dict(hint_tracker.hook_hint_to_idx) if hint_tracker else {}
    hint_to_entry_id = dict(hint_tracker.hint_to_entry_id) if hint_tracker else {}

    if not changespec.mentors:
        return HintTracker(
            counter=hint_counter,
            mappings=hint_mappings,
            hook_hint_to_idx=hook_hint_to_idx,
            hint_to_entry_id=hint_to_entry_id,
        )

    # Find the latest (highest numeric) commit ID from COMMITS field
    latest_entry_id: str | None = None
    if changespec.commits:
        for commit in changespec.commits:
            # Only consider all-numeric entries (e.g., "5", not "5a")
            if commit.proposal_letter is None:
                if latest_entry_id is None or commit.number > int(latest_entry_id):
                    latest_entry_id = str(commit.number)

    text.append("MENTORS:\n", style="bold #87D7FF")

    for mentor_entry in changespec.mentors:
        # Filter profiles for WIP entries - only show profiles with run_on_wip mentors
        from mentor_config import profile_has_wip_mentors

        from ...display_helpers import format_profile_with_count

        if mentor_entry.is_wip:
            visible_profiles = [
                p for p in mentor_entry.profiles if profile_has_wip_mentors(p)
            ]
        else:
            visible_profiles = mentor_entry.profiles

        # Skip entry entirely if no visible profiles
        if not visible_profiles:
            continue

        is_latest_entry = mentor_entry.entry_id == latest_entry_id

        # Count non-RUNNING statuses for folded summary
        # (FAILED for latest entry is always shown, so don't count as folded)
        passed_count = 0
        failed_count = 0
        dead_count = 0
        if mentor_entry.status_lines:
            for msl in mentor_entry.status_lines:
                if msl.status == "PASSED":
                    passed_count += 1
                elif msl.status == "FAILED":
                    if not is_latest_entry:
                        failed_count += 1
                elif msl.status == "DEAD":
                    dead_count += 1

        # Entry line (2-space indented): (N) profile1[x/y] [profile2[x/y] ...]
        text.append("  ", style="")
        text.append(f"({mentor_entry.entry_id}) ", style="bold #D7AF5F")
        profiles_with_counts = [
            format_profile_with_count(
                p, mentor_entry.status_lines, is_wip=mentor_entry.is_wip
            )
            for p in visible_profiles
        ]
        text.append(" ".join(profiles_with_counts), style="#D7D7AF")
        if mentor_entry.is_wip:
            text.append(" #WIP", style="bold #FFD700")

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
                # For non-latest entries, hide ALL status lines when collapsed
                if mentors_collapsed and not is_latest_entry:
                    continue
                # For latest entry, hide only PASSED and DEAD (show RUNNING and FAILED)
                if mentors_collapsed and msl.status in ("PASSED", "DEAD"):
                    continue

                text.append("      ", style="")
                text.append("| ", style="#808080")

                # Show hint for viewable mentor entries (PASSED/FAILED with timestamp)
                if with_hints and msl.timestamp and msl.status in ("PASSED", "FAILED"):
                    chat_path = get_mentor_chat_path(
                        changespec.name, msl.mentor_name, msl.timestamp
                    )
                    hint_mappings[hint_counter] = chat_path
                    hint_to_entry_id[hint_counter] = mentor_entry.entry_id
                    text.append(f"[{hint_counter}] ", style="bold #FFFF00")
                    hint_counter += 1

                # Display timestamp if present (same magenta as HOOKS)
                if msl.timestamp:
                    ts_display = format_timestamp_display(msl.timestamp)
                    text.append(f"{ts_display} ", style="#AF87D7")

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

    return HintTracker(
        counter=hint_counter,
        mappings=hint_mappings,
        hook_hint_to_idx=hook_hint_to_idx,
        hint_to_entry_id=hint_to_entry_id,
    )
