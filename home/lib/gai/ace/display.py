"""Display functions for ChangeSpec - showing ChangeSpec information in the terminal."""

import os
import re
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from running_field import get_claimed_workspaces

from .changespec import (
    ChangeSpec,
    parse_commit_entry_id,
)
from .display_helpers import (
    get_bug_field,
    get_status_color,
    is_entry_ref_suffix,
    is_suffix_timestamp,
)


def display_changespec(
    changespec: ChangeSpec,
    console: Console,
    with_hints: bool = False,
    hints_for: str | None = None,
) -> tuple[dict[int, str], dict[int, int]]:
    """Display a ChangeSpec using rich formatting.

    Color scheme from gaiproject.vim:
    - Field keys (NAME:, DESCRIPTION:, etc.): bold #87D7FF (cyan)
    - NAME/PARENT values: bold #00D7AF (cyan-green)
    - CL values: bold #5FD7FF (light cyan)
    - DESCRIPTION values: #D7D7AF (tan/beige)
    - STATUS values: status-specific colors
    - TEST TARGETS: bold #AFD75F (green)

    Args:
        changespec: The ChangeSpec to display.
        console: The Rich console to print to.
        with_hints: If True, add [N] hints before file paths and return mappings.
        hints_for: Controls which entries get hints when with_hints is True:
            - None or "all": Show hints for all entries (history, hooks, etc.)
            - "hooks_only": Show hints only for hooks with status lines
            - "hooks_latest_only": Show hints only for hook status lines that
              match the last HISTORY entry number (for edit hooks functionality)

    Returns:
        Tuple of:
        - Dict mapping hint numbers to file paths. Empty if with_hints is False.
        - Dict mapping hint numbers to hook indices (only populated when
          hints_for is "hooks_latest_only").
    """
    # Track hint number -> file path mappings
    hint_mappings: dict[int, str] = {}
    # Track hint number -> hook index (only for hooks_latest_only mode)
    hook_hint_to_idx: dict[int, int] = {}
    hint_counter = 1

    # Build the display text
    text = Text()

    # --- ProjectSpec fields (BUG, RUNNING) ---
    bug_field = get_bug_field(changespec.file_path)
    running_claims = get_claimed_workspaces(changespec.file_path)

    if bug_field:
        text.append("BUG: ", style="bold #87D7FF")
        text.append(f"{bug_field}\n", style="#FFD700")

    if running_claims:
        text.append("RUNNING:\n", style="bold #87D7FF")
        for claim in running_claims:
            text.append(f"  #{claim.workspace_num} | {claim.workflow}", style="#87AFFF")
            if claim.cl_name:
                text.append(f" | {claim.cl_name}", style="#87AFFF")
            text.append("\n")

    # Add separator between ProjectSpec and ChangeSpec fields (two blank lines)
    if bug_field or running_claims:
        text.append("\n\n")

    # NAME field
    text.append("NAME: ", style="bold #87D7FF")
    text.append(f"{changespec.name}\n", style="bold #00D7AF")

    # DESCRIPTION field
    text.append("DESCRIPTION:\n", style="bold #87D7FF")
    for line in changespec.description.split("\n"):
        text.append(f"  {line}\n", style="#D7D7AF")

    # KICKSTART field (only display if present)
    if changespec.kickstart:
        text.append("KICKSTART:\n", style="bold #87D7FF")
        for line in changespec.kickstart.split("\n"):
            text.append(f"  {line}\n", style="#D7D7AF")

    # PARENT field (only display if present)
    if changespec.parent:
        text.append("PARENT: ", style="bold #87D7FF")
        text.append(f"{changespec.parent}\n", style="bold #00D7AF")

    # CL field (only display if present)
    if changespec.cl:
        text.append("CL: ", style="bold #87D7FF")
        text.append(f"{changespec.cl}\n", style="bold #5FD7FF")

    # STATUS field
    text.append("STATUS: ", style="bold #87D7FF")
    # Check for READY TO MAIL suffix and highlight it specially (like Vim syntax)
    ready_to_mail_suffix = " - (!: READY TO MAIL)"
    if changespec.status.endswith(ready_to_mail_suffix):
        base_status = changespec.status[: -len(ready_to_mail_suffix)]
        status_color = get_status_color(base_status)
        text.append(base_status, style=f"bold {status_color}")
        # " - " in default style, suffix with white (#FFFFFF) on red background
        text.append(" - ")
        text.append("(!: READY TO MAIL)\n", style="bold #FFFFFF on #AF0000")
    else:
        status_color = get_status_color(changespec.status)
        text.append(f"{changespec.status}\n", style=f"bold {status_color}")

    # TEST TARGETS field (only display if present)
    if changespec.test_targets:
        text.append("TEST TARGETS: ", style="bold #87D7FF")
        if len(changespec.test_targets) == 1:
            # Check if the single value is "None" - if so, skip displaying
            if changespec.test_targets[0] != "None":
                target = changespec.test_targets[0]
                if "(FAILED)" in target:
                    # Split target to highlight (FAILED) in red
                    base_target = target.replace(" (FAILED)", "")
                    text.append(f"{base_target} ", style="bold #AFD75F")
                    text.append("(FAILED)\n", style="bold #FF5F5F")
                else:
                    text.append(f"{target}\n", style="bold #AFD75F")
            else:
                text.append("None\n")
        else:
            text.append("\n")
            for target in changespec.test_targets:
                if target != "None":
                    if "(FAILED)" in target:
                        # Split target to highlight (FAILED) in red
                        base_target = target.replace(" (FAILED)", "")
                        text.append(f"  {base_target} ", style="bold #AFD75F")
                        text.append("(FAILED)\n", style="bold #FF5F5F")
                    else:
                        text.append(f"  {target}\n", style="bold #AFD75F")

    # HISTORY field (only display if present)
    # Determine if we should show hints for history entries
    show_history_hints = with_hints and hints_for in (None, "all")
    if changespec.commits:
        text.append("COMMITS:\n", style="bold #87D7FF")
        for entry in changespec.commits:
            # Entry number and note (2-space indented like other multi-line fields)
            # Use display_number to show proposal letter if present (e.g., "2a")
            entry_style = "bold #D7AF5F"
            text.append(f"  ({entry.display_number}) ", style=entry_style)

            # Check if note contains a file path in parentheses (e.g., "(~/path/to/file)")
            # This handles cases like split spec YAML files
            note_path_match = re.search(r"\((~/[^)]+)\)", entry.note)
            if show_history_hints and note_path_match:
                # Split the note around the path and add hint
                note_path = note_path_match.group(1)
                # Expand ~ to full path for the mapping
                full_path = os.path.expanduser(note_path)
                hint_mappings[hint_counter] = full_path
                # Display: text before path, hint, path in parens, text after
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

            # Display suffix if present
            if entry.suffix:
                text.append(" - ")
                if entry.suffix_type == "error":
                    # Red background with white text for maximum visibility
                    text.append(f"(!: {entry.suffix})", style="bold #FFFFFF on #AF0000")
                elif entry.suffix_type == "running_agent" or is_suffix_timestamp(
                    entry.suffix
                ):
                    # Orange background with white text (same as @@@ query)
                    text.append(f"(@: {entry.suffix})", style="bold #FFFFFF on #FF8C00")
                elif entry.suffix_type == "killed_agent":
                    # Grey background with orange text for killed agent
                    text.append(
                        f"(~@: {entry.suffix})", style="bold #FF8C00 on #444444"
                    )
                elif entry.suffix_type == "running_process":
                    # Yellow background with dark brown text (same as $$$ query)
                    text.append(f"($: {entry.suffix})", style="bold #3D2B1F on #FFD700")
                elif entry.suffix_type == "pending_dead_process":
                    # Grey background with yellow text for pending dead process
                    text.append(
                        f"(?$: {entry.suffix})", style="bold #FFD700 on #444444"
                    )
                elif entry.suffix_type == "killed_process":
                    # Grey background with olive text for killed process
                    text.append(
                        f"(~$: {entry.suffix})", style="bold #B8A800 on #444444"
                    )
                else:
                    text.append(f"({entry.suffix})")
            text.append("\n")

            # CHAT field (if present) - 6 spaces = 2 (base indent) + 4 (sub-field indent)
            if entry.chat:
                text.append("      ", style="")
                # Parse duration suffix from chat (e.g., "path (1h2m3s)" -> "path", "1h2m3s")
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
            # DIFF field (if present)
            if entry.diff:
                text.append("      ", style="")
                if show_history_hints:
                    hint_mappings[hint_counter] = entry.diff
                    text.append(f"[{hint_counter}] ", style="bold #FFFF00")
                    hint_counter += 1
                text.append("| ", style="#808080")
                text.append("DIFF: ", style="bold #87D7FF")
                diff_path = entry.diff.replace(str(Path.home()), "~")
                text.append(f"{diff_path}\n", style="#87AFFF")

    # HOOKS field (only display if present)
    if changespec.hooks:
        # Lazy import to avoid circular dependency
        from .changespec import get_current_and_proposal_entry_ids
        from .hooks import (
            contract_test_target_command,
            format_timestamp_display,
            get_hook_output_path,
        )

        # Get non-historical entry IDs for hint display
        non_historical_ids = get_current_and_proposal_entry_ids(changespec)

        text.append("HOOKS:\n", style="bold #87D7FF")
        for hook_idx, hook in enumerate(changespec.hooks):
            # Hook command (2-space indented) - contract test targets to shorthand
            display_command = contract_test_target_command(hook.command)
            text.append(f"  {display_command}\n", style="#D7D7AF")
            # Status lines (if present) - 4-space indented
            if hook.status_lines:
                # Sort by history entry ID for display (e.g., "1", "1a", "2")
                sorted_status_lines = sorted(
                    hook.status_lines,
                    key=lambda sl: parse_commit_entry_id(sl.commit_entry_num),
                )

                for idx, sl in enumerate(sorted_status_lines):
                    text.append("      ", style="")
                    text.append("| ", style="#808080")
                    # Determine if we should show a hint for this status line
                    show_hint = False
                    if with_hints:
                        if hints_for == "hooks_latest_only":
                            # Show hint for non-historical entries
                            show_hint = sl.commit_entry_num in non_historical_ids
                        else:
                            # Show hints for all status lines (default behavior)
                            show_hint = True

                    if show_hint:
                        hook_output_path = get_hook_output_path(
                            changespec.name, sl.timestamp
                        )
                        hint_mappings[hint_counter] = hook_output_path
                        # Track hook index mapping for hooks_latest_only mode
                        if hints_for == "hooks_latest_only":
                            hook_hint_to_idx[hint_counter] = hook_idx
                        text.append(f"[{hint_counter}] ", style="bold #FFFF00")
                        hint_counter += 1
                    # Format: (N) [timestamp] STATUS (duration)
                    text.append(f"({sl.commit_entry_num}) ", style="bold #D7AF5F")
                    ts_display = format_timestamp_display(sl.timestamp)
                    text.append(f"{ts_display} ", style="#AF87D7")
                    # Color based on status
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
                    # Duration (if present)
                    if sl.duration:
                        text.append(f" ({sl.duration})", style="#808080")
                    # Suffix (if present) - different styles for different types:
                    # - error suffix (ZOMBIE, Hook Command Failed, etc): red background
                    # - running_agent suffix (timestamp or empty): orange background
                    # - killed_agent suffix: faded orange background
                    # - running_process suffix (PID): yellow background
                    # - killed_process suffix: faded yellow background
                    # - other: default style
                    # Handle running_agent/running_process with suffix (RUNNING hooks)
                    if sl.suffix is not None and (
                        sl.suffix
                        or sl.suffix_type == "running_agent"
                        or sl.suffix_type == "running_process"
                    ):
                        text.append(" - ")
                        if sl.suffix_type == "error":
                            # Red background with white text for maximum visibility
                            suffix_content = sl.suffix
                            if sl.summary:
                                suffix_content = f"{sl.suffix} | {sl.summary}"
                            text.append(
                                f"(!: {suffix_content})",
                                style="bold #FFFFFF on #AF0000",
                            )
                        elif sl.suffix_type == "running_agent" or is_suffix_timestamp(
                            sl.suffix
                        ):
                            # Orange background with white text (same as @@@ query)
                            suffix_content = sl.suffix
                            if sl.summary:
                                suffix_content = (
                                    f"{sl.suffix} | {sl.summary}"
                                    if sl.suffix
                                    else sl.summary
                                )
                            if suffix_content:
                                text.append(
                                    f"(@: {suffix_content})",
                                    style="bold #FFFFFF on #FF8C00",
                                )
                            else:
                                text.append("(@)", style="bold #FFFFFF on #FF8C00")
                        elif sl.suffix_type == "killed_agent":
                            # Grey background with orange text for killed agent
                            suffix_content = sl.suffix
                            if sl.summary:
                                suffix_content = f"{sl.suffix} | {sl.summary}"
                            text.append(
                                f"(~@: {suffix_content})",
                                style="bold #FF8C00 on #444444",
                            )
                        elif sl.suffix_type == "running_process":
                            # Yellow background with dark brown text (same as $$$ query)
                            suffix_content = sl.suffix
                            if sl.summary:
                                suffix_content = f"{sl.suffix} | {sl.summary}"
                            text.append(
                                f"($: {suffix_content})",
                                style="bold #3D2B1F on #FFD700",
                            )
                        elif sl.suffix_type == "pending_dead_process":
                            # Grey background with yellow text for pending dead process
                            suffix_content = sl.suffix
                            if sl.summary:
                                suffix_content = f"{sl.suffix} | {sl.summary}"
                            text.append(
                                f"(?$: {suffix_content})",
                                style="bold #FFD700 on #444444",
                            )
                        elif sl.suffix_type == "killed_process":
                            # Grey background with olive text for killed process
                            suffix_content = sl.suffix
                            if sl.summary:
                                suffix_content = f"{sl.suffix} | {sl.summary}"
                            text.append(
                                f"(~$: {suffix_content})",
                                style="bold #B8A800 on #444444",
                            )
                        elif sl.suffix_type == "summarize_complete":
                            # Cyan/teal background for summarize complete
                            suffix_content = sl.suffix or ""
                            if sl.summary:
                                suffix_content = (
                                    f"{sl.suffix} | {sl.summary}"
                                    if sl.suffix
                                    else sl.summary
                                )
                            if suffix_content:
                                text.append(
                                    f"(%: {suffix_content})",
                                    style="bold #FFFFFF on #008B8B",
                                )
                            else:
                                text.append("(%)", style="bold #FFFFFF on #008B8B")
                        elif is_entry_ref_suffix(sl.suffix):
                            # Entry reference suffix (e.g., "2", "1a") - light red/pink
                            suffix_content = sl.suffix
                            if sl.summary:
                                suffix_content = f"{sl.suffix} | {sl.summary}"
                            text.append(f"({suffix_content})", style="bold #FF87AF")
                        else:
                            # Default: include summary if present
                            suffix_content = sl.suffix
                            if sl.summary:
                                suffix_content = f"{sl.suffix} | {sl.summary}"
                            text.append(f"({suffix_content})")
                    text.append("\n")

    # COMMENTS field (only display if present)
    # Show hints for comments when with_hints is True (all modes)
    show_comment_hints = with_hints and hints_for in (None, "all")
    if changespec.comments:
        text.append("COMMENTS:\n", style="bold #87D7FF")
        for comment in changespec.comments:
            # Entry line (2-space indented): [N] [reviewer] path - (suffix)
            text.append("  ", style="")
            # Add hint before the reviewer if enabled
            if show_comment_hints:
                # Expand ~ to full path for the mapping
                full_path = os.path.expanduser(comment.file_path)
                hint_mappings[hint_counter] = full_path
                text.append(f"[{hint_counter}] ", style="bold #FFFF00")
                hint_counter += 1
            text.append(f"[{comment.reviewer}]", style="bold #D7AF5F")
            text.append(" ", style="")
            # Display path with ~ for home directory
            display_path = comment.file_path.replace(str(Path.home()), "~")
            text.append(display_path, style="#87AFFF")
            # Suffix (if present) - different styles for different types:
            # - error suffix (ZOMBIE, Unresolved Critique Comments, etc): red background
            # - running_agent suffix (timestamp or empty): orange background
            # - killed_agent suffix: faded orange background
            # - running_process suffix (PID): yellow background
            # - killed_process suffix: faded yellow background
            # - other: default style
            # Handle running_agent/running_process with suffix (for consistency)
            if comment.suffix is not None and (
                comment.suffix
                or comment.suffix_type == "running_agent"
                or comment.suffix_type == "running_process"
            ):
                text.append(" - ")
                if comment.suffix_type == "error":
                    # Red background with white text for maximum visibility
                    text.append(
                        f"(!: {comment.suffix})", style="bold #FFFFFF on #AF0000"
                    )
                elif comment.suffix_type == "running_agent" or is_suffix_timestamp(
                    comment.suffix
                ):
                    # Orange background with white text (same as @@@ query)
                    # Empty suffix → "(@)", non-empty → "(@: msg)"
                    if comment.suffix:
                        text.append(
                            f"(@: {comment.suffix})", style="bold #FFFFFF on #FF8C00"
                        )
                    else:
                        text.append("(@)", style="bold #FFFFFF on #FF8C00")
                elif comment.suffix_type == "killed_agent":
                    # Grey background with orange text for killed agent
                    text.append(
                        f"(~@: {comment.suffix})", style="bold #FF8C00 on #444444"
                    )
                elif comment.suffix_type == "running_process":
                    # Yellow background with dark brown text (same as $$$ query)
                    text.append(
                        f"($: {comment.suffix})", style="bold #3D2B1F on #FFD700"
                    )
                elif comment.suffix_type == "pending_dead_process":
                    # Grey background with yellow text for pending dead process
                    text.append(
                        f"(?$: {comment.suffix})", style="bold #FFD700 on #444444"
                    )
                elif comment.suffix_type == "killed_process":
                    # Grey background with olive text for killed process
                    text.append(
                        f"(~$: {comment.suffix})", style="bold #B8A800 on #444444"
                    )
                else:
                    text.append(f"({comment.suffix})")
            text.append("\n")

    # MENTORS field (only display if present)
    if changespec.mentors:
        text.append("MENTORS:\n", style="bold #87D7FF")
        for mentor_entry in changespec.mentors:
            # Entry line (2-space indented): (N) profile1 [profile2 ...]
            text.append("  ", style="")
            text.append(f"({mentor_entry.entry_id}) ", style="bold #D7AF5F")
            text.append(" ".join(mentor_entry.profiles), style="#D7D7AF")
            text.append("\n")
            # Status lines (if present) - 6-space indented
            if mentor_entry.status_lines:
                for msl in mentor_entry.status_lines:
                    text.append("      ", style="")
                    text.append("| ", style="#808080")
                    # Format: profile:mentor - STATUS - (suffix/duration)
                    text.append(
                        f"{msl.profile_name}:{msl.mentor_name}", style="bold #87AFFF"
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
                        if msl.suffix_type == "error":
                            text.append(
                                f"(!: {msl.suffix})", style="bold #FFFFFF on #AF0000"
                            )
                        elif msl.suffix_type == "running_agent":
                            if msl.suffix:
                                text.append(
                                    f"(@: {msl.suffix})",
                                    style="bold #FFFFFF on #FF8C00",
                                )
                            else:
                                text.append("(@)", style="bold #FFFFFF on #FF8C00")
                        elif is_entry_ref_suffix(msl.suffix):
                            # Entry reference suffix (e.g., "2a") - pink
                            text.append(f"({msl.suffix})", style="bold #FF87AF")
                        else:
                            text.append(f"({msl.suffix})")
                    text.append("\n")

    # Remove trailing newline to avoid extra blank lines in panel
    text.rstrip()

    # Display in a panel with file location as title
    # Replace home directory with ~ for cleaner display
    file_path = changespec.file_path.replace(str(Path.home()), "~")
    file_location = f"{file_path}:{changespec.line_number}"
    console.print(
        Panel(
            text,
            title=f"📋 {file_location}",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    return hint_mappings, hook_hint_to_idx
