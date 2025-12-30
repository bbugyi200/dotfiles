"""ChangeSpec detail widget for the ace TUI."""

import re
from pathlib import Path
from typing import Any

from rich.panel import Panel
from rich.text import Text
from running_field import get_claimed_workspaces
from textual.widgets import Static

from ...changespec import (
    ChangeSpec,
    is_acknowledged_suffix,
    is_error_suffix,
    parse_history_entry_id,
)


def _get_status_color(status: str) -> str:
    """Get the color for a given status.

    Workspace suffixes (e.g., " (fig_3)") are stripped before color lookup.
    """
    # Strip workspace suffix before looking up color
    base_status = re.sub(r" \([a-zA-Z0-9_-]+_\d+\)$", "", status)

    status_colors = {
        "Drafted": "#87D700",
        "Mailed": "#00D787",
        "Submitted": "#00AF00",
        "Reverted": "#808080",
    }
    return status_colors.get(base_status, "#FFFFFF")


def _is_suffix_timestamp(suffix: str) -> bool:
    """Check if a suffix is a timestamp format."""
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
    """Tokenize a query string for syntax highlighting."""
    tokens: list[tuple[str, str]] = []
    i = 0

    while i < len(query):
        if query[i].isspace():
            start = i
            while i < len(query) and query[i].isspace():
                i += 1
            tokens.append((query[start:i], "whitespace"))
            continue

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

        # Check for !@ (not running agent shorthand)
        if query[i : i + 2] == "!@" and (
            i + 2 >= len(query) or query[i + 2] in " \t\r\n"
        ):
            tokens.append(("!@", "running_agent"))
            i += 2
            continue

        # Check for standalone ! (also error suffix)
        if query[i] == "!" and (i + 1 >= len(query) or query[i + 1] in " \t\r\n"):
            tokens.append(("!", "error_suffix"))
            i += 1
            continue

        if query[i] == "!":
            tokens.append(("!", "negation"))
            i += 1
            continue

        # Check for @@@ (running agent shorthand)
        if query[i : i + 3] == "@@@":
            tokens.append(("@@@", "running_agent"))
            i += 3
            continue

        # Check for standalone @ (also running agent)
        if query[i] == "@" and (i + 1 >= len(query) or query[i + 1] in " \t\r\n"):
            tokens.append(("@", "running_agent"))
            i += 1
            continue

        if query[i] == '"' or (
            query[i] == "c" and i + 1 < len(query) and query[i + 1] == '"'
        ):
            start = i
            if query[i] == "c":
                i += 1
            i += 1
            while i < len(query) and query[i] != '"':
                if query[i] == "\\" and i + 1 < len(query):
                    i += 2
                else:
                    i += 1
            if i < len(query):
                i += 1
            tokens.append((query[start:i], "quoted"))
            continue

        # Check for keywords (AND, NOT, OR) - must be at word boundaries
        if (
            query[i : i + 3].upper() == "AND"
            and (i + 3 >= len(query) or not query[i + 3].isalnum())
            and (i == 0 or not query[i - 1].isalnum())
        ):
            tokens.append((query[i : i + 3], "keyword"))
            i += 3
            continue
        if (
            query[i : i + 3].upper() == "NOT"
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
            word_lower = word.lower()

            # Check if this is a property key (followed by :)
            if i < len(query) and query[i] == ":":
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

            # Not a property - check if it's a keyword
            word_upper = word.upper()
            if word_upper == "AND":
                tokens.append((word, "keyword"))
            elif word_upper == "OR":
                tokens.append((word, "keyword"))
            elif word_upper == "NOT":
                tokens.append((word, "keyword"))
            else:
                tokens.append((word, "term"))
            continue

        # Collect unquoted term (until whitespace, paren, or special char)
        start = i
        while i < len(query) and not query[i].isspace() and query[i] not in '()!"':
            remaining = query[i:]
            # Only break on keywords at word boundaries (not in middle of words)
            at_word_boundary = i == 0 or not query[i - 1].isalnum()
            if (
                at_word_boundary
                and remaining[:3].upper() == "AND"
                and (len(remaining) == 3 or not remaining[3].isalnum())
            ):
                break
            if (
                at_word_boundary
                and remaining[:3].upper() == "NOT"
                and (len(remaining) == 3 or not remaining[3].isalnum())
            ):
                break
            if (
                at_word_boundary
                and remaining[:2].upper() == "OR"
                and (len(remaining) == 2 or not remaining[2].isalnum())
            ):
                break
            i += 1
        if i > start:
            tokens.append((query[start:i], "term"))

    return tokens


def _build_query_text(query: str) -> Text:
    """Build a styled Text object for the query.

    Color scheme:
    - Keywords (AND, OR, NOT): bold #87AFFF (blue)
    - Negation (!): bold #FF5F5F (red)
    - Error suffix (!!!, !!, !): bold #FFFFFF on #AF0000 (white on red)
    - Quoted strings: #808080 (gray)
    - Unquoted terms: #00D7AF (cyan-green)
    - Parentheses: bold #FFFFFF (white)
    - Property keys (status:, project:, ancestor:): bold #87D7FF (cyan)
    - Property values: #D7AF5F (gold)
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
        elif token_type == "property_key":
            text.append(token, style="bold #87D7FF")
        elif token_type == "property_value":
            text.append(token, style="#D7AF5F")
        else:
            text.append(token)

    return text


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


class SearchQueryPanel(Static):
    """Panel showing the current search query."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the search query panel."""
        super().__init__(**kwargs)

    def update_query(self, query_string: str) -> None:
        """Update the displayed query.

        Args:
            query_string: The current search query string.
        """
        text = Text()
        text.append("Search Query ", style="dim italic #87D7FF")
        text.append("» ", style="dim #808080")
        text.append_text(_build_query_text(query_string))
        self.update(text)


class ChangeSpecDetail(Static):
    """Right panel showing detailed ChangeSpec information."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the detail widget."""
        super().__init__(**kwargs)

    def update_display(self, changespec: ChangeSpec, query_string: str) -> None:
        """Update the detail view with a new changespec.

        Args:
            changespec: The ChangeSpec to display
            query_string: The current query string
        """
        content = self._build_display_content(changespec, query_string)
        self.update(content)

    def show_empty(self, query_string: str) -> None:
        """Show empty state when no ChangeSpecs match."""
        text = Text()
        text.append("Search Query\n", style="bold #87D7FF")
        text.append_text(_build_query_text(query_string))
        text.append("\n\n")
        text.append("No ChangeSpecs match this query.", style="yellow")

        panel = Panel(
            text,
            title="No Results",
            border_style="yellow",
            padding=(1, 2),
        )
        self.update(panel)

    def _build_display_content(
        self, changespec: ChangeSpec, query_string: str
    ) -> Panel:
        """Build the display content for a ChangeSpec."""
        del query_string  # No longer displayed inline; shown in SearchQueryPanel
        text = Text()

        # ProjectSpec fields (BUG, RUNNING)
        bug_field = _get_bug_field(changespec.file_path)
        running_claims = get_claimed_workspaces(changespec.file_path)

        if bug_field:
            text.append("BUG: ", style="bold #87D7FF")
            text.append(f"{bug_field}\n", style="#FFD700")

        if running_claims:
            text.append("RUNNING:\n", style="bold #87D7FF")
            for claim in running_claims:
                text.append(
                    f"  #{claim.workspace_num} | {claim.workflow}", style="#87AFFF"
                )
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
        ready_to_mail_suffix = " - (!: READY TO MAIL)"
        if changespec.status.endswith(ready_to_mail_suffix):
            base_status = changespec.status[: -len(ready_to_mail_suffix)]
            status_color = _get_status_color(base_status)
            text.append(base_status, style=f"bold {status_color}")
            text.append(" - ")
            text.append("(!: READY TO MAIL)\n", style="bold #FFFFFF on #AF0000")
        else:
            status_color = _get_status_color(changespec.status)
            text.append(f"{changespec.status}\n", style=f"bold {status_color}")

        # TEST TARGETS field
        if changespec.test_targets:
            text.append("TEST TARGETS: ", style="bold #87D7FF")
            if len(changespec.test_targets) == 1:
                if changespec.test_targets[0] != "None":
                    target = changespec.test_targets[0]
                    if "(FAILED)" in target:
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
                            base_target = target.replace(" (FAILED)", "")
                            text.append(f"  {base_target} ", style="bold #AFD75F")
                            text.append("(FAILED)\n", style="bold #FF5F5F")
                        else:
                            text.append(f"  {target}\n", style="bold #AFD75F")

        # HISTORY field
        if changespec.history:
            text.append("HISTORY:\n", style="bold #87D7FF")
            for entry in changespec.history:
                entry_style = "bold #D7AF5F"
                text.append(f"  ({entry.display_number}) ", style=entry_style)
                text.append(f"{entry.note}", style="#D7D7AF")

                if entry.suffix:
                    text.append(" - ")
                    if entry.suffix_type == "error":
                        text.append(
                            f"(!: {entry.suffix})", style="bold #FFFFFF on #AF0000"
                        )
                    elif entry.suffix_type == "acknowledged":
                        text.append(f"(~: {entry.suffix})", style="bold #FFAF00")
                    else:
                        text.append(f"({entry.suffix})")
                text.append("\n")

                # CHAT field
                if entry.chat:
                    text.append("      ", style="")
                    # Parse duration suffix from chat (e.g., "path (1h2m3s)")
                    chat_duration_match = re.search(
                        r" \((\d+[hms]+[^)]*)\)$", entry.chat
                    )
                    if chat_duration_match:
                        chat_path_raw = entry.chat[: chat_duration_match.start()]
                        chat_duration = chat_duration_match.group(1)
                    else:
                        chat_path_raw = entry.chat
                        chat_duration = None
                    text.append("| ", style="#808080")
                    text.append("CHAT: ", style="bold #87D7FF")
                    chat_path = chat_path_raw.replace(str(Path.home()), "~")
                    text.append(chat_path, style="#87AFFF")
                    if chat_duration:
                        text.append(f" ({chat_duration})", style="#808080")
                    text.append("\n")

                # DIFF field
                if entry.diff:
                    text.append("      ", style="")
                    text.append("| ", style="#808080")
                    text.append("DIFF: ", style="bold #87D7FF")
                    diff_path = entry.diff.replace(str(Path.home()), "~")
                    text.append(f"{diff_path}\n", style="#87AFFF")

        # HOOKS field
        if changespec.hooks:
            from ...hooks import format_timestamp_display

            text.append("HOOKS:\n", style="bold #87D7FF")
            for hook in changespec.hooks:
                text.append(f"  {hook.command}\n", style="#D7D7AF")
                if hook.status_lines:
                    sorted_status_lines = sorted(
                        hook.status_lines,
                        key=lambda sl: parse_history_entry_id(sl.history_entry_num),
                    )
                    for sl in sorted_status_lines:
                        text.append("    ", style="")
                        text.append(f"({sl.history_entry_num}) ", style="bold #D7AF5F")
                        ts_display = format_timestamp_display(sl.timestamp)
                        text.append(f"{ts_display} ", style="#AF87D7")
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
                        if sl.duration:
                            text.append(f" ({sl.duration})", style="#808080")
                        if sl.suffix:
                            text.append(" - ")
                            if is_error_suffix(sl.suffix):
                                text.append(
                                    f"(!: {sl.suffix})",
                                    style="bold #FFFFFF on #AF0000",
                                )
                            elif is_acknowledged_suffix(sl.suffix):
                                text.append(f"(~: {sl.suffix})", style="bold #FFAF00")
                            elif _is_suffix_timestamp(sl.suffix):
                                text.append(f"({sl.suffix})", style="bold #D75F87")
                            else:
                                text.append(f"({sl.suffix})")
                        text.append("\n")

        # COMMENTS field
        if changespec.comments:
            text.append("COMMENTS:\n", style="bold #87D7FF")
            for comment in changespec.comments:
                text.append("  ", style="")
                text.append(f"[{comment.reviewer}]", style="bold #D7AF5F")
                text.append(" ", style="")
                display_path = comment.file_path.replace(str(Path.home()), "~")
                text.append(display_path, style="#87AFFF")
                if comment.suffix:
                    text.append(" - ")
                    if is_error_suffix(comment.suffix):
                        text.append(
                            f"(!: {comment.suffix})", style="bold #FFFFFF on #AF0000"
                        )
                    elif is_acknowledged_suffix(comment.suffix):
                        text.append(f"(~: {comment.suffix})", style="bold #FFAF00")
                    elif _is_suffix_timestamp(comment.suffix):
                        text.append(f"({comment.suffix})", style="bold #D75F87")
                    else:
                        text.append(f"({comment.suffix})")
                text.append("\n")

        text.rstrip()

        # Display in a panel with file location as title
        file_path = changespec.file_path.replace(str(Path.home()), "~")
        file_location = f"{file_path}:{changespec.line_number}"

        return Panel(
            text,
            title=f"{file_location}",
            border_style="cyan",
            padding=(1, 2),
        )
