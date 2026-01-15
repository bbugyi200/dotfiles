"""HOOKS section builder for ChangeSpec detail display."""

from accept_workflow.parsing import parse_proposal_id
from rich.text import Text

from ...changespec import (
    ChangeSpec,
    HookEntry,
    get_current_and_proposal_entry_ids,
    parse_commit_entry_id,
)
from ...hooks import (
    contract_test_target_command,
    format_timestamp_display,
    get_hook_output_path,
)
from .hint_tracker import HintTracker
from .suffix_formatting import append_suffix_to_text, should_show_suffix


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
