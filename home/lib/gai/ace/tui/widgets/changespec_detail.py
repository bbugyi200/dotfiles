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
    parse_commit_entry_id,
)
from ...query.highlighting import QUERY_TOKEN_STYLES, tokenize_query_for_display


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


def _build_query_text(query: str) -> Text:
    """Build a styled Text object for the query.

    Uses shared highlighting from query.highlighting module.
    """
    text = Text()
    tokens = tokenize_query_for_display(query)

    for token, token_type in tokens:
        style = QUERY_TOKEN_STYLES.get(token_type, "")
        if token_type == "keyword":
            text.append(token.upper(), style=style)
        elif style:
            text.append(token, style=style)
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
        if changespec.commits:
            text.append("COMMITS:\n", style="bold #87D7FF")
            for entry in changespec.commits:
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
                        key=lambda sl: parse_commit_entry_id(sl.commit_entry_num),
                    )
                    for sl in sorted_status_lines:
                        text.append("    ", style="")
                        text.append(f"({sl.commit_entry_num}) ", style="bold #D7AF5F")
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
