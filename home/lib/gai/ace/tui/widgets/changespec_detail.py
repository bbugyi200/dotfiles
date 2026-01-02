"""ChangeSpec detail widget for the ace TUI."""

import os
import re
from pathlib import Path
from typing import Any

from rich.panel import Panel
from rich.text import Text
from running_field import get_claimed_workspaces
from textual.widgets import Static

from ...changespec import (
    ChangeSpec,
    get_current_and_proposal_entry_ids,
    parse_commit_entry_id,
)
from ...display_helpers import (
    get_bug_field,
    get_status_color,
    is_entry_ref_suffix,
    is_suffix_timestamp,
)
from ...query.highlighting import QUERY_TOKEN_STYLES, tokenize_query_for_display


def build_query_text(query: str) -> Text:
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
        text.append_text(build_query_text(query_string))
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
        content, _, _ = self._build_display_content(changespec, query_string)
        self.update(content)

    def update_display_with_hints(
        self,
        changespec: ChangeSpec,
        query_string: str,
        hints_for: str | None = None,
    ) -> tuple[dict[int, str], dict[int, int]]:
        """Update display with inline hints and return mappings.

        Args:
            changespec: The ChangeSpec to display
            query_string: The current query string
            hints_for: Controls which entries get hints:
                - None or "all": Show hints for all entries
                - "hooks_latest_only": Show hints only for hook status lines
                  that match current/proposal entry IDs

        Returns:
            Tuple of:
            - Dict mapping hint numbers to file paths
            - Dict mapping hint numbers to hook indices (for hooks_latest_only)
        """
        content, hint_mappings, hook_hint_to_idx = self._build_display_content(
            changespec, query_string, with_hints=True, hints_for=hints_for
        )
        self.update(content)
        return hint_mappings, hook_hint_to_idx

    def show_empty(self, query_string: str) -> None:
        """Show empty state when no ChangeSpecs match."""
        del query_string  # Query is already displayed in SearchQueryPanel
        text = Text()
        text.append("No ChangeSpecs match this query.", style="yellow")

        panel = Panel(
            text,
            title="No Results",
            border_style="yellow",
            padding=(1, 2),
        )
        self.update(panel)

    def _build_display_content(
        self,
        changespec: ChangeSpec,
        query_string: str,
        with_hints: bool = False,
        hints_for: str | None = None,
    ) -> tuple[Panel, dict[int, str], dict[int, int]]:
        """Build the display content for a ChangeSpec."""
        del query_string  # No longer displayed inline; shown in SearchQueryPanel
        text = Text()

        # Hint tracking
        hint_mappings: dict[int, str] = {}
        hook_hint_to_idx: dict[int, int] = {}
        hint_counter = 1  # Start from 1, 0 reserved for project file

        # Hint 0 is always the project file (not displayed)
        if with_hints:
            hint_mappings[0] = changespec.file_path

        # Determine which entries get hints
        show_history_hints = with_hints and hints_for in (None, "all")
        show_comment_hints = with_hints and hints_for in (None, "all")

        # Get non-historical entry IDs for hooks_latest_only mode
        non_historical_ids = (
            get_current_and_proposal_entry_ids(changespec)
            if with_hints and hints_for == "hooks_latest_only"
            else set()
        )

        # ProjectSpec fields (BUG, RUNNING)
        bug_field = get_bug_field(changespec.file_path)
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
            status_color = get_status_color(base_status)
            text.append(base_status, style=f"bold {status_color}")
            text.append(" - ")
            text.append("(!: READY TO MAIL)\n", style="bold #FFFFFF on #AF0000")
        else:
            status_color = get_status_color(changespec.status)
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
                        text.append(
                            f"(!: {entry.suffix})", style="bold #FFFFFF on #AF0000"
                        )
                    elif entry.suffix_type == "running_agent" or is_suffix_timestamp(
                        entry.suffix
                    ):
                        # Orange background with white text (same as @@@ query)
                        text.append(
                            f"(@: {entry.suffix})", style="bold #FFFFFF on #FF8C00"
                        )
                    elif entry.suffix_type == "running_process":
                        # Yellow background with dark brown text (same as $$$ query)
                        text.append(
                            f"($: {entry.suffix})", style="bold #3D2B1F on #FFD700"
                        )
                    elif entry.suffix_type == "killed_process":
                        # Grey background with olive text for killed process
                        text.append(
                            f"(~$: {entry.suffix})", style="bold #B8A800 on #444444"
                        )
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

                # DIFF field
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

        # HOOKS field
        if changespec.hooks:
            from ...hooks import format_timestamp_display, get_hook_output_path

            text.append("HOOKS:\n", style="bold #87D7FF")
            for hook_idx, hook in enumerate(changespec.hooks):
                text.append(f"  {hook.command}\n", style="#D7D7AF")
                if hook.status_lines:
                    sorted_status_lines = sorted(
                        hook.status_lines,
                        key=lambda sl: parse_commit_entry_id(sl.commit_entry_num),
                    )
                    for sl in sorted_status_lines:
                        text.append("    ", style="")
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
                        if sl.suffix is not None and (
                            sl.suffix
                            or sl.suffix_type == "running_agent"
                            or sl.suffix_type == "running_process"
                        ):
                            text.append(" - ")
                            if sl.suffix_type == "error":
                                suffix_content = sl.suffix
                                if sl.summary:
                                    suffix_content = f"{sl.suffix} | {sl.summary}"
                                text.append(
                                    f"(!: {suffix_content})",
                                    style="bold #FFFFFF on #AF0000",
                                )
                            elif (
                                sl.suffix_type == "running_agent"
                                or is_suffix_timestamp(sl.suffix)
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
                            elif sl.suffix_type == "running_process":
                                # Yellow background with dark brown text (same as $$$ query)
                                suffix_content = sl.suffix
                                if sl.summary:
                                    suffix_content = f"{sl.suffix} | {sl.summary}"
                                text.append(
                                    f"($: {suffix_content})",
                                    style="bold #3D2B1F on #FFD700",
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
                            elif sl.suffix_type == "killed_agent":
                                # Grey background with orange text for killed agent
                                suffix_content = sl.suffix
                                if sl.summary:
                                    suffix_content = f"{sl.suffix} | {sl.summary}"
                                text.append(
                                    f"(~@: {suffix_content})",
                                    style="bold #FF8C00 on #444444",
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

        # COMMENTS field
        if changespec.comments:
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
                if comment.suffix is not None and (
                    comment.suffix
                    or comment.suffix_type == "running_agent"
                    or comment.suffix_type == "running_process"
                ):
                    text.append(" - ")
                    if comment.suffix_type == "error":
                        text.append(
                            f"(!: {comment.suffix})", style="bold #FFFFFF on #AF0000"
                        )
                    elif comment.suffix_type == "running_agent" or is_suffix_timestamp(
                        comment.suffix
                    ):
                        # Orange background with white text (same as @@@ query)
                        if comment.suffix:
                            text.append(
                                f"(@: {comment.suffix})",
                                style="bold #FFFFFF on #FF8C00",
                            )
                        else:
                            text.append("(@)", style="bold #FFFFFF on #FF8C00")
                    elif comment.suffix_type == "running_process":
                        # Yellow background with dark brown text (same as $$$ query)
                        text.append(
                            f"($: {comment.suffix})",
                            style="bold #3D2B1F on #FFD700",
                        )
                    elif comment.suffix_type == "killed_process":
                        # Grey background with olive text for killed process
                        text.append(
                            f"(~$: {comment.suffix})",
                            style="bold #B8A800 on #444444",
                        )
                    else:
                        text.append(f"({comment.suffix})")
                text.append("\n")

        text.rstrip()

        # Display in a panel with file location as title
        file_path = changespec.file_path.replace(str(Path.home()), "~")
        file_location = f"{file_path}:{changespec.line_number}"

        panel = Panel(
            text,
            title=f"{file_location}",
            border_style="cyan",
            padding=(1, 2),
        )
        return panel, hint_mappings, hook_hint_to_idx
