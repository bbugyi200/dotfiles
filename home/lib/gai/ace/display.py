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
    is_acknowledged_suffix,
    is_error_suffix,
    parse_history_entry_id,
)


def _get_bug_field(project_file: str) -> str | None:
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


def _get_status_color(status: str) -> str:
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


def _is_suffix_timestamp(suffix: str) -> bool:
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


def _is_bare_word_char(char: str) -> bool:
    """Check if a character can be part of a bare word."""
    return char.isalnum() or char in "_-"


def _tokenize_query(query: str) -> list[tuple[str, str]]:
    """Tokenize a query string for syntax highlighting.

    Args:
        query: The query string to tokenize.

    Returns:
        List of (token, token_type) tuples where token_type is one of:
        - "keyword" for AND, OR
        - "negation" for !
        - "error_suffix" for !!! (error suffix shorthand)
        - "paren" for ( and )
        - "quoted" for quoted strings (including the quotes)
        - "term" for unquoted search terms
        - "shorthand" for %d, %m, %s, %r, +project, ^ancestor
        - "property_key" for status:, project:, ancestor:
        - "property_value" for the value after a property key
        - "whitespace" for spaces
    """
    tokens: list[tuple[str, str]] = []
    i = 0

    while i < len(query):
        # Skip and collect whitespace
        if query[i].isspace():
            start = i
            while i < len(query) and query[i].isspace():
                i += 1
            tokens.append((query[start:i], "whitespace"))
            continue

        # Check for parentheses
        if query[i] in "()":
            tokens.append((query[i], "paren"))
            i += 1
            continue

        # Check for !!! (error suffix shorthand) - must come before single ! check
        if query[i : i + 3] == "!!!":
            tokens.append(("!!!", "error_suffix"))
            i += 3
            continue

        # Check for !! (not error suffix shorthand)
        if query[i : i + 2] == "!!" and (
            i + 2 >= len(query) or query[i + 2] in " \t\r\n"
        ):
            tokens.append(("!!", "error_suffix"))
            i += 2
            continue

        # Check for standalone ! (also error suffix)
        if query[i] == "!" and (i + 1 >= len(query) or query[i + 1] in " \t\r\n"):
            tokens.append(("!", "error_suffix"))
            i += 1
            continue

        # Check for negation (! followed by something)
        if query[i] == "!":
            tokens.append(("!", "negation"))
            i += 1
            continue

        # Check for status shorthand: %d, %m, %s, %r
        if query[i] == "%" and i + 1 < len(query) and query[i + 1].lower() in "dmsr":
            tokens.append((query[i : i + 2], "shorthand"))
            i += 2
            continue

        # Check for project shorthand: +identifier
        if (
            query[i] == "+"
            and i + 1 < len(query)
            and (query[i + 1].isalpha() or query[i + 1] == "_")
        ):
            start = i
            i += 1  # Skip +
            while i < len(query) and _is_bare_word_char(query[i]):
                i += 1
            tokens.append((query[start:i], "shorthand"))
            continue

        # Check for ancestor shorthand: ^identifier
        if (
            query[i] == "^"
            and i + 1 < len(query)
            and (query[i + 1].isalpha() or query[i + 1] == "_")
        ):
            start = i
            i += 1  # Skip ^
            while i < len(query) and _is_bare_word_char(query[i]):
                i += 1
            tokens.append((query[start:i], "shorthand"))
            continue

        # Check for quoted strings (with optional case-sensitivity prefix)
        if query[i] == '"' or (
            query[i] == "c" and i + 1 < len(query) and query[i + 1] == '"'
        ):
            start = i
            if query[i] == "c":
                i += 1  # Skip the 'c' prefix
            i += 1  # Skip opening quote
            while i < len(query) and query[i] != '"':
                if query[i] == "\\" and i + 1 < len(query):
                    i += 2  # Skip escaped character
                else:
                    i += 1
            if i < len(query):
                i += 1  # Skip closing quote
            tokens.append((query[start:i], "quoted"))
            continue

        # Check for keywords (AND, OR) - must be at word boundaries
        if (
            query[i : i + 3].upper() == "AND"
            and (i + 3 >= len(query) or not query[i + 3].isalnum())
            and (i == 0 or not query[i - 1].isalnum())
        ):
            tokens.append((query[i : i + 3], "keyword"))
            i += 3
            continue
        if (
            query[i : i + 2].upper() == "OR"
            and (i + 2 >= len(query) or not query[i + 2].isalnum())
            and (i == 0 or not query[i - 1].isalnum())
        ):
            tokens.append((query[i : i + 2], "keyword"))
            i += 2
            continue

        # Collect word (bare word or property key)
        if query[i].isalpha() or query[i] == "_":
            start = i
            while i < len(query) and _is_bare_word_char(query[i]):
                i += 1
            word = query[start:i]

            # Check if this is a property key (followed by :)
            if i < len(query) and query[i] == ":":
                word_lower = word.lower()
                if word_lower in ("status", "project", "ancestor"):
                    # Property key
                    tokens.append((word + ":", "property_key"))
                    i += 1  # Skip the colon

                    # Now parse the property value
                    if i < len(query) and query[i] == '"':
                        # Quoted value
                        start = i
                        i += 1
                        while i < len(query) and query[i] != '"':
                            if query[i] == "\\" and i + 1 < len(query):
                                i += 2
                            else:
                                i += 1
                        if i < len(query):
                            i += 1
                        tokens.append((query[start:i], "property_value"))
                    elif i < len(query) and (query[i].isalpha() or query[i] == "_"):
                        # Bare word value
                        start = i
                        while i < len(query) and _is_bare_word_char(query[i]):
                            i += 1
                        tokens.append((query[start:i], "property_value"))
                    continue

            # Not a property - it's a regular term
            # But first check if it's a keyword we missed
            word_upper = word.upper()
            if word_upper == "AND":
                tokens.append((word, "keyword"))
            elif word_upper == "OR":
                tokens.append((word, "keyword"))
            else:
                tokens.append((word, "term"))
            continue

        # Collect unquoted term (until whitespace, paren, or special char)
        start = i
        while i < len(query) and not query[i].isspace() and query[i] not in '()!"':
            # Stop if we hit AND or OR keyword
            remaining = query[i:]
            if remaining[:3].upper() == "AND" and (
                len(remaining) == 3 or not remaining[3].isalnum()
            ):
                break
            if remaining[:2].upper() == "OR" and (
                len(remaining) == 2 or not remaining[2].isalnum()
            ):
                break
            i += 1
        if i > start:
            tokens.append((query[start:i], "term"))

    return tokens


def display_search_query(query: str, console: Console) -> None:
    """Display the search query with syntax highlighting.

    Color scheme:
    - Keywords (AND, OR): bold #87AFFF (blue)
    - Negation (!): bold #FF5F5F (red)
    - Error suffix (!!!, !!, !): bold #FFFFFF on #AF0000 (white on red)
    - Quoted strings: #808080 (gray)
    - Unquoted terms: #00D7AF (cyan-green)
    - Parentheses: bold #FFFFFF (white)
    - Shorthands (%d, +project, ^ancestor): bold #AF87D7 (magenta)
    - Property keys (status:, project:, ancestor:): bold #87D7FF (cyan)
    - Property values: #D7AF5F (gold)

    Args:
        query: The search query string to display.
        console: The Rich console to print to.
    """
    text = Text()
    tokens = _tokenize_query(query)

    for token, token_type in tokens:
        if token_type == "keyword":
            text.append(token.upper(), style="bold #87AFFF")
        elif token_type == "negation":
            text.append(token, style="bold #FF5F5F")
        elif token_type == "error_suffix":
            text.append(token, style="bold #FFFFFF on #AF0000")
        elif token_type == "quoted":
            text.append(token, style="#808080")
        elif token_type == "term":
            text.append(token, style="#00D7AF")
        elif token_type == "paren":
            text.append(token, style="bold #FFFFFF")
        elif token_type == "shorthand":
            text.append(token, style="bold #AF87D7")
        elif token_type == "property_key":
            text.append(token, style="bold #87D7FF")
        elif token_type == "property_value":
            text.append(token, style="#D7AF5F")
        else:  # whitespace
            text.append(token)

    console.print(
        Panel(
            text,
            title="Search Query",
            border_style="cyan",
            padding=(0, 1),
        )
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
        - Dict mapping hint numbers to file paths. Always includes hint 0 for the
          project file (not shown in output). Empty if with_hints is False.
        - Dict mapping hint numbers to hook indices (only populated when
          hints_for is "hooks_latest_only").
    """
    # Track hint number -> file path mappings
    hint_mappings: dict[int, str] = {}
    # Track hint number -> hook index (only for hooks_latest_only mode)
    hook_hint_to_idx: dict[int, int] = {}
    hint_counter = 1  # Start from 1, 0 is reserved for project file

    # Hint 0 is always the project file (not displayed)
    if with_hints:
        hint_mappings[0] = changespec.file_path
    # Build the display text
    text = Text()

    # --- ProjectSpec fields (BUG, RUNNING) ---
    bug_field = _get_bug_field(changespec.file_path)
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
        status_color = _get_status_color(base_status)
        text.append(base_status, style=f"bold {status_color}")
        # " - " in default style, suffix with white (#FFFFFF) on red background
        text.append(" - ")
        text.append("(!: READY TO MAIL)\n", style="bold #FFFFFF on #AF0000")
    else:
        status_color = _get_status_color(changespec.status)
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
    if changespec.history:
        text.append("HISTORY:\n", style="bold #87D7FF")
        for entry in changespec.history:
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
                elif entry.suffix_type == "acknowledged":
                    # Yellow/orange warning color
                    text.append(f"(~: {entry.suffix})", style="bold #FFAF00")
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
            format_timestamp_display,
            get_hook_output_path,
        )

        # Get non-historical entry IDs for hint display
        non_historical_ids = get_current_and_proposal_entry_ids(changespec)

        text.append("HOOKS:\n", style="bold #87D7FF")
        for hook_idx, hook in enumerate(changespec.hooks):
            # Hook command (2-space indented) - show full command including "!" prefix
            text.append(f"  {hook.command}\n", style="#D7D7AF")
            # Status lines (if present) - 4-space indented
            if hook.status_lines:
                # Sort by history entry ID for display (e.g., "1", "1a", "2")
                sorted_status_lines = sorted(
                    hook.status_lines,
                    key=lambda sl: parse_history_entry_id(sl.history_entry_num),
                )

                for idx, sl in enumerate(sorted_status_lines):
                    text.append("    ", style="")
                    # Determine if we should show a hint for this status line
                    show_hint = False
                    if with_hints:
                        if hints_for == "hooks_latest_only":
                            # Show hint for non-historical entries
                            show_hint = sl.history_entry_num in non_historical_ids
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
                    text.append(f"({sl.history_entry_num}) ", style="bold #D7AF5F")
                    ts_display = format_timestamp_display(sl.timestamp)
                    text.append(f"{ts_display} ", style="#AF87D7")
                    # Color based on status
                    if sl.status == "PASSED":
                        text.append(sl.status, style="bold #00AF00")
                    elif sl.status == "FAILED":
                        text.append(sl.status, style="bold #FF5F5F")
                    elif sl.status == "RUNNING":
                        text.append(sl.status, style="bold #87AFFF")
                    elif sl.status == "ZOMBIE":
                        text.append(sl.status, style="bold #FFAF00")
                    else:
                        text.append(sl.status)
                    # Duration (if present)
                    if sl.duration:
                        text.append(f" ({sl.duration})", style="#808080")
                    # Suffix (if present) - different styles for different types:
                    # - error suffix (ZOMBIE, Hook Command Failed, etc): red background
                    # - acknowledged suffix (NEW PROPOSAL after becoming old): yellow/orange
                    # - timestamp (YYmmdd_HHMMSS): pink foreground
                    # - other: default style
                    if sl.suffix:
                        text.append(" - ")
                        if is_error_suffix(sl.suffix):
                            # Red background with white text for maximum visibility
                            text.append(
                                f"(!: {sl.suffix})", style="bold #FFFFFF on #AF0000"
                            )
                        elif is_acknowledged_suffix(sl.suffix):
                            # Yellow/orange warning color
                            text.append(f"(~: {sl.suffix})", style="bold #FFAF00")
                        elif _is_suffix_timestamp(sl.suffix):
                            text.append(f"({sl.suffix})", style="bold #D75F87")
                        else:
                            text.append(f"({sl.suffix})")
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
            # - acknowledged suffix (NEW PROPOSAL after becoming old): yellow/orange
            # - timestamp (YYmmdd_HHMMSS): pink foreground
            # - other: default style
            if comment.suffix:
                text.append(" - ")
                if is_error_suffix(comment.suffix):
                    # Red background with white text for maximum visibility
                    text.append(
                        f"(!: {comment.suffix})", style="bold #FFFFFF on #AF0000"
                    )
                elif is_acknowledged_suffix(comment.suffix):
                    # Yellow/orange warning color
                    text.append(f"(~: {comment.suffix})", style="bold #FFAF00")
                elif _is_suffix_timestamp(comment.suffix):
                    text.append(f"({comment.suffix})", style="bold #D75F87")
                else:
                    text.append(f"({comment.suffix})")
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
