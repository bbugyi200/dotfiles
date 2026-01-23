"""ChangeSpec detail widget for the ace TUI."""

from pathlib import Path
from typing import Any

from rich.panel import Panel
from rich.text import Text
from running_field import get_claimed_workspaces
from textual.widgets import Static

from ...changespec import ChangeSpec, get_current_and_proposal_entry_ids
from ...display_helpers import (
    format_running_claims_aligned,
    get_status_color,
)
from ...query.highlighting import QUERY_TOKEN_STYLES, tokenize_query_for_display
from .section_builders import (
    HintTracker,
    build_comments_section,
    build_commits_section,
    build_hooks_section,
    build_mentors_section,
)


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

    def update_display(
        self,
        changespec: ChangeSpec,
        query_string: str,
        hooks_collapsed: bool = True,
        commits_collapsed: bool = True,
        mentors_collapsed: bool = True,
    ) -> None:
        """Update the detail view with a new changespec.

        Args:
            changespec: The ChangeSpec to display
            query_string: The current query string
            hooks_collapsed: Whether to collapse hook status lines
            commits_collapsed: Whether to collapse COMMITS drawer lines
            mentors_collapsed: Whether to collapse MENTORS entries
        """
        content, _, _, _, _ = self._build_display_content(
            changespec,
            query_string,
            hooks_collapsed=hooks_collapsed,
            commits_collapsed=commits_collapsed,
            mentors_collapsed=mentors_collapsed,
        )
        self.update(content)

    def update_display_with_hints(
        self,
        changespec: ChangeSpec,
        query_string: str,
        hints_for: str | None = None,
        hooks_collapsed: bool = True,
        commits_collapsed: bool = True,
        mentors_collapsed: bool = True,
    ) -> tuple[
        dict[int, str], dict[int, int], dict[int, str], dict[int, tuple[str, str]]
    ]:
        """Update display with inline hints and return mappings.

        Args:
            changespec: The ChangeSpec to display
            query_string: The current query string
            hints_for: Controls which entries get hints:
                - None or "all": Show hints for all entries
                - "hooks_latest_only": Show hints only for hook status lines
                  that match current/proposal entry IDs
            hooks_collapsed: Whether to collapse hook status lines
            commits_collapsed: Whether to collapse COMMITS drawer lines
            mentors_collapsed: Whether to collapse MENTORS entries

        Returns:
            Tuple of:
            - Dict mapping hint numbers to file paths
            - Dict mapping hint numbers to hook indices (for hooks_latest_only)
            - Dict mapping hint numbers to commit entry IDs (for hooks_latest_only)
            - Dict mapping hint numbers to (mentor_name, profile_name) tuples
        """
        (
            content,
            hint_mappings,
            hook_hint_to_idx,
            hint_to_entry_id,
            mentor_hint_to_info,
        ) = self._build_display_content(
            changespec,
            query_string,
            with_hints=True,
            hints_for=hints_for,
            hooks_collapsed=hooks_collapsed,
            commits_collapsed=commits_collapsed,
            mentors_collapsed=mentors_collapsed,
        )
        self.update(content)
        return hint_mappings, hook_hint_to_idx, hint_to_entry_id, mentor_hint_to_info

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
        hooks_collapsed: bool = True,
        commits_collapsed: bool = True,
        mentors_collapsed: bool = True,
    ) -> tuple[
        Panel,
        dict[int, str],
        dict[int, int],
        dict[int, str],
        dict[int, tuple[str, str]],
    ]:
        """Build the display content for a ChangeSpec."""
        del query_string  # No longer displayed inline; shown in SearchQueryPanel
        text = Text()

        # Initialize hint tracking
        hint_mappings: dict[int, str] = {}
        hook_hint_to_idx: dict[int, int] = {}
        hint_to_entry_id: dict[int, str] = {}
        mentor_hint_to_info: dict[int, tuple[str, str]] = {}
        hint_counter = 1

        # Determine which entries get hints
        show_history_hints = with_hints and hints_for in (None, "all")
        show_comment_hints = with_hints and hints_for in (None, "all")

        # Get non-historical entry IDs for hooks_latest_only mode
        non_historical_ids: set[str] = (
            set(get_current_and_proposal_entry_ids(changespec))
            if with_hints and hints_for == "hooks_latest_only"
            else set()
        )

        # Build RUNNING field (displayed at top of panel)
        self._build_running_field(text, changespec)

        # Build basic ChangeSpec fields
        self._build_basic_fields(text, changespec)

        # Build COMMITS section
        hint_tracker = HintTracker(
            counter=hint_counter,
            mappings=hint_mappings,
            hook_hint_to_idx=hook_hint_to_idx,
            hint_to_entry_id=hint_to_entry_id,
            mentor_hint_to_info=mentor_hint_to_info,
        )
        hint_tracker = build_commits_section(
            text, changespec, show_history_hints, commits_collapsed, hint_tracker
        )

        # Build HOOKS section
        hint_tracker = build_hooks_section(
            text,
            changespec,
            with_hints,
            hints_for,
            hooks_collapsed,
            non_historical_ids,
            hint_tracker,
        )

        # Build COMMENTS section
        hint_tracker = build_comments_section(
            text, changespec, show_comment_hints, hint_tracker
        )

        # Build MENTORS section
        hint_tracker = build_mentors_section(
            text, changespec, mentors_collapsed, with_hints, hint_tracker
        )

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
        return (
            panel,
            hint_tracker.mappings,
            hint_tracker.hook_hint_to_idx,
            hint_tracker.hint_to_entry_id,
            hint_tracker.mentor_hint_to_info,
        )

    def _build_running_field(
        self,
        text: Text,
        changespec: ChangeSpec,
    ) -> None:
        """Build RUNNING claims section (displayed at top of panel)."""
        running_claims = get_claimed_workspaces(changespec.file_path)

        if running_claims:
            text.append("RUNNING:\n", style="bold #87D7FF")
            formatted_claims = format_running_claims_aligned(running_claims)
            for ws_col, pid_col, wf_col, cl_name in formatted_claims:
                # Each column gets a distinct color for beautiful syntax highlighting
                text.append(f"  {ws_col}", style="#5FD7FF")  # Cyan for workspace
                text.append(" | ", style="dim")
                text.append(pid_col, style="#FF87D7")  # Magenta/pink for PID
                text.append(" | ", style="dim")
                text.append(wf_col, style="#FFD787")  # Gold/amber for workflow
                if cl_name:
                    text.append(" | ", style="dim")
                    text.append(cl_name, style="#87D7AF")  # Green for CL name
                text.append("\n")
            text.append("\n\n")  # Separator after RUNNING

    def _build_basic_fields(
        self,
        text: Text,
        changespec: ChangeSpec,
    ) -> None:
        """Build basic ChangeSpec fields (NAME, DESCRIPTION, etc.)."""
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

        # CL field (only display if present)
        if changespec.cl:
            text.append("CL: ", style="bold #87D7FF")
            text.append(f"{changespec.cl}\n", style="bold #5FD7FF")

        # BUG field (only display if present)
        if changespec.bug:
            text.append("BUG: ", style="bold #87D7FF")
            text.append(f"{changespec.bug}\n", style="#FFD700")

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
        self._build_test_targets_field(text, changespec)

    def _build_test_targets_field(
        self,
        text: Text,
        changespec: ChangeSpec,
    ) -> None:
        """Build the TEST TARGETS field."""
        if not changespec.test_targets:
            return

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

    def show_failed_hooks_targets(
        self,
        targets: list[str],
        file_path: str,
    ) -> None:
        """Display failed hooks targets with numbered hints for selection.

        Args:
            targets: List of test targets (lines starting with //).
            file_path: Path to the failed hooks file.
        """
        text = Text()

        # Header with file path
        text.append("FAILED HOOKS TARGETS\n", style="bold #FF5F5F")
        text.append("Source: ", style="dim")
        text.append(file_path, style="bold underline #00D7AF")
        text.append("\n\n")

        # List targets with numbered hints
        text.append("Select targets to add as hooks:\n", style="dim italic")
        for idx, target in enumerate(targets, 1):
            text.append(f"  [{idx}] ", style="bold #FFFF00")
            text.append(f"{target}\n", style="bold #AFD75F")

        text.append("\n")
        text.append("Enter numbers (e.g., 1 3 5 or 1-5) to add as hooks", style="dim")

        panel = Panel(
            text,
            title="Failed Hooks Selection",
            border_style="#FF5F5F",
            padding=(1, 2),
        )
        self.update(panel)
