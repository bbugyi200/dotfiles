"""Modal showing all currently running processes and agents."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ...changespec import (
    ChangeSpec,
    HookEntry,
    HookStatusLine,
    MentorStatusLine,
    find_all_changespecs,
)

# Box dimensions: total width = 87 chars
# Layout: "  | " (5 chars) + content (78 chars) + " |" (4 chars) = 87 chars
_BOX_WIDTH = 87
_CONTENT_WIDTH = 78


@dataclass
class _RunnerInfo:
    """Information about a single runner."""

    runner_type: Literal["process", "agent"]
    cl_name: str
    project_name: str
    hook_command: str | None  # For processes/hook agents
    agent_type: str | None  # fix-hook, summarize-hook, mentor, crs
    pid: int | None
    start_time: datetime | None
    reviewer: str | None  # For CRS agents
    raw_suffix: str | None


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse a YYmmdd_HHMMSS timestamp string to datetime.

    Args:
        ts: Timestamp string in YYmmdd_HHMMSS format.

    Returns:
        datetime object or None if parsing fails.
    """
    try:
        return datetime.strptime(ts, "%y%m%d_%H%M%S")
    except ValueError:
        return None


def _extract_pid_and_timestamp_from_suffix(
    suffix: str,
) -> tuple[int | None, str | None]:
    """Extract PID and timestamp from agent suffix format.

    Args:
        suffix: Suffix like "fix_hook-12345-251230_151429".

    Returns:
        Tuple of (pid, timestamp_str) or (None, None) if format doesn't match.
    """
    if "-" not in suffix:
        return None, None
    parts = suffix.split("-")
    if len(parts) < 3:
        return None, None
    ts = parts[-1]
    pid_str = parts[-2]
    if pid_str.isdigit() and len(ts) == 13 and ts[6] == "_":
        return int(pid_str), ts
    return None, None


def _collect_hook_runners(
    changespec: ChangeSpec,
    hook: HookEntry,
    status_line: HookStatusLine,
) -> _RunnerInfo | None:
    """Collect runner info from a hook status line.

    Args:
        changespec: The ChangeSpec containing the hook.
        hook: The HookEntry containing the status line.
        status_line: The HookStatusLine to examine.

    Returns:
        _RunnerInfo if this is a running process/agent, None otherwise.
    """
    suffix_type = status_line.suffix_type
    suffix = status_line.suffix

    if suffix_type == "running_process":
        # Running hook process - suffix is the PID
        pid = int(suffix) if suffix and suffix.isdigit() else None
        return _RunnerInfo(
            runner_type="process",
            cl_name=changespec.name,
            project_name=changespec.project_basename,
            hook_command=hook.display_command,
            agent_type=None,
            pid=pid,
            start_time=_parse_timestamp(status_line.timestamp),
            reviewer=None,
            raw_suffix=suffix,
        )
    elif suffix_type == "running_agent":
        # Running agent (fix-hook or summarize-hook)
        pid, ts = _extract_pid_and_timestamp_from_suffix(suffix or "")
        # Determine agent type from suffix prefix
        agent_type = "fix-hook"
        if suffix and suffix.startswith("summarize"):
            agent_type = "summarize-hook"
        return _RunnerInfo(
            runner_type="agent",
            cl_name=changespec.name,
            project_name=changespec.project_basename,
            hook_command=hook.display_command,
            agent_type=agent_type,
            pid=pid,
            start_time=_parse_timestamp(ts) if ts else None,
            reviewer=None,
            raw_suffix=suffix,
        )
    return None


def _collect_mentor_runners(
    changespec: ChangeSpec,
    status_line: MentorStatusLine,
) -> _RunnerInfo | None:
    """Collect runner info from a mentor status line.

    Args:
        changespec: The ChangeSpec containing the mentor.
        status_line: The MentorStatusLine to examine.

    Returns:
        _RunnerInfo if this is a running mentor agent, None otherwise.
    """
    if status_line.suffix_type != "running_agent":
        return None

    pid, ts = _extract_pid_and_timestamp_from_suffix(status_line.suffix or "")
    return _RunnerInfo(
        runner_type="agent",
        cl_name=changespec.name,
        project_name=changespec.project_basename,
        hook_command=None,
        agent_type=f"mentor:{status_line.profile_name}:{status_line.mentor_name}",
        pid=pid,
        start_time=_parse_timestamp(ts) if ts else None,
        reviewer=None,
        raw_suffix=status_line.suffix,
    )


def _collect_comment_runners(changespec: ChangeSpec) -> list[_RunnerInfo]:
    """Collect runner info from comment entries (CRS agents).

    Args:
        changespec: The ChangeSpec to examine.

    Returns:
        List of _RunnerInfo for running CRS agents.
    """
    runners: list[_RunnerInfo] = []
    if not changespec.comments:
        return runners

    for comment in changespec.comments:
        if comment.suffix_type != "running_agent":
            continue

        pid, ts = _extract_pid_and_timestamp_from_suffix(comment.suffix or "")
        runners.append(
            _RunnerInfo(
                runner_type="agent",
                cl_name=changespec.name,
                project_name=changespec.project_basename,
                hook_command=None,
                agent_type="crs",
                pid=pid,
                start_time=_parse_timestamp(ts) if ts else None,
                reviewer=comment.reviewer,
                raw_suffix=comment.suffix,
            )
        )
    return runners


def _collect_runners() -> tuple[list[_RunnerInfo], list[_RunnerInfo]]:
    """Collect all running processes and agents from all ChangeSpecs.

    Returns:
        Tuple of (processes, agents) lists.
    """
    processes: list[_RunnerInfo] = []
    agents: list[_RunnerInfo] = []

    for changespec in find_all_changespecs():
        # Collect from HOOKS
        if changespec.hooks:
            for hook in changespec.hooks:
                if hook.status_lines:
                    for sl in hook.status_lines:
                        runner = _collect_hook_runners(changespec, hook, sl)
                        if runner:
                            if runner.runner_type == "process":
                                processes.append(runner)
                            else:
                                agents.append(runner)

        # Collect from COMMENTS (CRS agents)
        agents.extend(_collect_comment_runners(changespec))

        # Collect from MENTORS
        if changespec.mentors:
            for mentor in changespec.mentors:
                if mentor.status_lines:
                    for msl in mentor.status_lines:
                        runner = _collect_mentor_runners(changespec, msl)
                        if runner:
                            agents.append(runner)

    return processes, agents


def get_runner_count() -> int:
    """Get the total count of running processes and agents.

    Returns:
        Total number of running processes and agents.
    """
    processes, agents = _collect_runners()
    return len(processes) + len(agents)


def _abbreviate_agent_type(agent_type: str) -> str:
    """Abbreviate long agent type strings for display.

    Args:
        agent_type: Full agent type string (e.g., "mentor:code:comments").

    Returns:
        Abbreviated string (e.g., "m:code:comm").
    """
    # Common abbreviations
    abbrevs = {
        "mentor": "m",
        "summarize-hook": "sum",
        "fix-hook": "fix",
        "comments": "comm",
    }

    parts = agent_type.split(":")
    abbreviated_parts = []
    for part in parts:
        if part in abbrevs:
            abbreviated_parts.append(abbrevs[part])
        elif len(part) > 6:
            abbreviated_parts.append(part[:4])
        else:
            abbreviated_parts.append(part)

    result = ":".join(abbreviated_parts)
    # Final truncation if still too long
    if len(result) > 15:
        result = result[:12] + "..."
    return result


def _format_duration(start_time: datetime | None) -> str:
    """Format duration from start time to now.

    Args:
        start_time: The start time, or None.

    Returns:
        Duration string like "5m23s" or "?" if unknown.
    """
    if start_time is None:
        return "?"
    delta = datetime.now() - start_time
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    if minutes < 60:
        return f"{minutes}m{seconds}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h{minutes}m"


class RunnersModal(ModalScreen[None]):
    """Modal showing all currently running processes and agents."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
        ("r", "close", "Close"),  # Same key closes
        ("ctrl+d", "scroll_down", "Scroll down"),
        ("ctrl+u", "scroll_up", "Scroll up"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="runners-modal-container"):
            yield Static(self._build_title(), id="runners-title")
            with VerticalScroll(id="runners-content-scroll"):
                yield Static(self._build_content(), id="runners-content")
            yield Static(
                "Press r / q / Esc to close  |  Ctrl+D/U to scroll",
                id="runners-footer",
            )

    def _build_title(self) -> Text:
        """Build the styled title."""
        text = Text()
        text.append("\n")
        text.append("  ", style="")
        text.append("\u2726 ", style="bold #FFD700")  # Star
        text.append("Running Processes & Agents", style="bold white")
        text.append(" \u2726", style="bold #FFD700")  # Star
        text.append("\n")
        return text

    def _build_content(self) -> Text:
        """Build the main content showing processes and agents."""
        processes, agents = _collect_runners()
        text = Text()

        # Running Processes section (yellow)
        self._add_section_header(text, "Running Processes", "#FFD700")
        if processes:
            for runner in processes:
                self._add_runner_entry(text, runner, "#FFD700")
        else:
            self._add_empty_row(text, "No running processes", "#FFD700")
        self._add_section_footer(text, "#FFD700")

        text.append("\n")

        # Running Agents section (orange)
        self._add_section_header(text, "Running Agents", "#FF8C00")
        if agents:
            for runner in agents:
                self._add_runner_entry(text, runner, "#FF8C00")
        else:
            self._add_empty_row(text, "No running agents", "#FF8C00")
        self._add_section_footer(text, "#FF8C00")

        return text

    def _add_section_header(self, text: Text, title: str, color: str) -> None:
        """Add a section header with box drawing.

        Args:
            text: The Text object to append to.
            title: The section title.
            color: The color for the box drawing.
        """
        # Header: "  ┌─ TITLE ──────────────────────────────────────────┐"
        # "  ┌─ " = 5 chars, " " after title + dashes + "┐" fills to _BOX_WIDTH
        text.append("  \u250c\u2500 ", style=f"dim {color}")
        text.append(title, style=f"bold {color}")
        text.append(" ", style="")
        # 5 (prefix) + len(title) + 1 (space) + remaining + 1 (corner) = _BOX_WIDTH
        remaining = _BOX_WIDTH - 5 - len(title) - 1 - 1
        text.append("\u2500" * remaining + "\u2510", style=f"dim {color}")
        text.append("\n")

    def _add_section_footer(self, text: Text, color: str) -> None:
        """Add a section footer with box drawing.

        Args:
            text: The Text object to append to.
            color: The color for the box drawing.
        """
        # Footer: "  └─────────────────────────────────────────────────────┘"
        # "  └" = 3 chars, dashes + "┘" fills to _BOX_WIDTH
        text.append("  \u2514", style=f"dim {color}")
        text.append("\u2500" * (_BOX_WIDTH - 4), style=f"dim {color}")
        text.append("\u2518", style=f"dim {color}")
        text.append("\n")

    def _add_empty_row(self, text: Text, message: str, color: str) -> None:
        """Add an empty state row with right border.

        Args:
            text: The Text object to append to.
            message: The empty state message.
            color: The color for the box drawing border.
        """
        # "  │  " = 5 chars prefix, message, padding, " │" = 2 chars suffix
        text.append("  \u2502  ", style=f"dim {color}")
        padding = _CONTENT_WIDTH - len(message)
        text.append(message, style="dim")
        text.append(" " * padding, style="")
        text.append(" \u2502", style=f"dim {color}")
        text.append("\n")

    def _add_runner_entry(self, text: Text, runner: _RunnerInfo, color: str) -> None:
        """Add a single runner entry.

        Args:
            text: The Text object to append to.
            runner: The runner info to display.
            color: The color for the box drawing border.
        """
        # Build content parts and track length
        parts: list[tuple[str, str]] = []  # (text, style) tuples
        content_len = 0

        # CL name (truncate to max 15 chars)
        cl_name = runner.cl_name
        if len(cl_name) > 15:
            cl_name = cl_name[:12] + "..."
        parts.append((cl_name, "bold #87D7FF"))
        parts.append((" ", ""))
        content_len += len(cl_name) + 1

        # Type indicator
        if runner.runner_type == "process":
            type_str = "($)"
            type_style = "bold #3D2B1F on #FFD700"
        else:
            agent_type = runner.agent_type or "agent"
            # Abbreviate long agent types (e.g., mentor:code:comments -> m:code:comm)
            agent_type = _abbreviate_agent_type(agent_type)
            type_str = f"(@:{agent_type})"
            type_style = "bold #FFFFFF on #FF8C00"
        parts.append((type_str, type_style))
        content_len += len(type_str)

        # Hook command if present (truncated to 18 chars)
        if runner.hook_command:
            cmd = runner.hook_command
            if len(cmd) > 18:
                cmd = cmd[:15] + "..."
            parts.append((f" {cmd}", "#87AFAF"))
            content_len += len(cmd) + 1

        # Reviewer for CRS
        if runner.reviewer:
            reviewer_str = f" [{runner.reviewer}]"
            parts.append((reviewer_str, "#D7AF87"))
            content_len += len(reviewer_str)

        # PID and duration
        pid_str = str(runner.pid) if runner.pid else "?"
        duration = _format_duration(runner.start_time)
        pid_duration = f" (PID:{pid_str}, {duration})"
        parts.append((pid_duration, "dim"))
        content_len += len(pid_duration)

        # Write row with proper borders
        text.append("  \u2502  ", style=f"dim {color}")
        for part_text, part_style in parts:
            text.append(part_text, style=part_style)

        # Pad to _CONTENT_WIDTH and add right border
        if content_len < _CONTENT_WIDTH:
            text.append(" " * (_CONTENT_WIDTH - content_len), style="")
        text.append(" \u2502", style=f"dim {color}")
        text.append("\n")

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(None)

    def action_scroll_down(self) -> None:
        """Scroll the content down by half a page."""
        scroll = self.query_one("#runners-content-scroll", VerticalScroll)
        height = scroll.scrollable_content_region.height
        scroll.scroll_relative(y=height // 2, animate=False)

    def action_scroll_up(self) -> None:
        """Scroll the content up by half a page."""
        scroll = self.query_one("#runners-content-scroll", VerticalScroll)
        height = scroll.scrollable_content_region.height
        scroll.scroll_relative(y=-(height // 2), animate=False)
