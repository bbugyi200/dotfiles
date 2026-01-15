"""Clipboard action methods for the ace TUI app."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..models.agent import Agent

TabName = Literal["changespecs", "agents", "axe"]


class ClipboardMixin:
    """Mixin providing clipboard copy actions for all tabs."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    _agents: list[Agent]

    def action_copy_tab_content(self) -> None:
        """Copy tab-specific content to clipboard based on current tab."""
        if self.current_tab == "changespecs":
            self._copy_changespec_to_clipboard()
        elif self.current_tab == "agents":
            self._copy_agent_chat_to_clipboard()
        else:  # axe
            self._copy_axe_artifacts_to_clipboard()

    def _copy_changespec_to_clipboard(self) -> None:
        """Copy the current ChangeSpec to clipboard in readable text format."""
        if not self.changespecs:
            self.notify("No ChangeSpec to copy", severity="warning")  # type: ignore[attr-defined]
            return

        changespec = self.changespecs[self.current_idx]
        content = _format_changespec_for_clipboard(changespec)

        if _copy_to_system_clipboard(content):
            self.notify(f"Copied ChangeSpec: {changespec.name}")  # type: ignore[attr-defined]
        else:
            self.notify("Failed to copy to clipboard", severity="error")  # type: ignore[attr-defined]

    def _copy_agent_chat_to_clipboard(self) -> None:
        """Copy the current agent's chat to clipboard."""
        if not self._agents:
            self.notify("No agent to copy", severity="warning")  # type: ignore[attr-defined]
            return

        agent = self._agents[self.current_idx]

        # Only completed agents have chat available
        if agent.status not in ("NO CHANGES", "NEW CL", "NEW PROPOSAL"):
            self.notify(  # type: ignore[attr-defined]
                "Chat only available for completed agents", severity="warning"
            )
            return

        # Check if response path is set
        if not agent.response_path:
            self.notify("No chat file available", severity="warning")  # type: ignore[attr-defined]
            return

        # Read chat content
        content = agent.get_response_content()
        if not content:
            self.notify("Failed to read chat file", severity="warning")  # type: ignore[attr-defined]
            return

        if _copy_to_system_clipboard(content):
            self.notify(f"Copied chat for: {agent.cl_name}")  # type: ignore[attr-defined]
        else:
            self.notify("Failed to copy to clipboard", severity="error")  # type: ignore[attr-defined]

    def _copy_axe_artifacts_to_clipboard(self) -> None:
        """Copy all axe artifact files to clipboard with file path headers."""
        content = _format_axe_artifacts_for_clipboard()

        if not content:
            self.notify("No axe artifacts to copy", severity="warning")  # type: ignore[attr-defined]
            return

        if _copy_to_system_clipboard(content):
            self.notify("Copied axe artifacts")  # type: ignore[attr-defined]
        else:
            self.notify("Failed to copy to clipboard", severity="error")  # type: ignore[attr-defined]


def _copy_to_system_clipboard(content: str) -> bool:
    """Copy content to system clipboard.

    Args:
        content: The text content to copy.

    Returns:
        True if successful, False otherwise.
    """
    if sys.platform == "darwin":
        clipboard_cmd = ["pbcopy"]
    elif sys.platform.startswith("linux"):
        clipboard_cmd = ["xclip", "-selection", "clipboard"]
    else:
        return False

    try:
        subprocess.run(clipboard_cmd, input=content, text=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _format_changespec_for_clipboard(cs: ChangeSpec) -> str:
    """Format a ChangeSpec as readable text for clipboard.

    Args:
        cs: The ChangeSpec to format.

    Returns:
        Formatted text representation.
    """
    lines: list[str] = []

    # Basic fields
    lines.append(f"NAME: {cs.name}")
    lines.append(f"DESCRIPTION: {cs.description}")
    if cs.parent:
        lines.append(f"PARENT: {cs.parent}")
    if cs.cl:
        lines.append(f"CL: {cs.cl}")
    lines.append(f"STATUS: {cs.status}")
    if cs.bug:
        lines.append(f"BUG: {cs.bug}")
    if cs.test_targets:
        lines.append(f"TEST_TARGETS: {', '.join(cs.test_targets)}")
    if cs.kickstart:
        lines.append(f"KICKSTART: {cs.kickstart}")

    # COMMITS section
    if cs.commits:
        lines.append("")
        lines.append("COMMITS:")
        for entry in cs.commits:
            suffix_part = ""
            if entry.suffix:
                prefix = "!: " if entry.suffix_type == "error" else ""
                suffix_part = f" - ({prefix}{entry.suffix})"

            chat_part = f" [chat: {entry.chat}]" if entry.chat else ""
            diff_part = f" [diff: {entry.diff}]" if entry.diff else ""

            lines.append(
                f"  ({entry.display_number}) {entry.note}{suffix_part}{chat_part}{diff_part}"
            )

    # HOOKS section
    if cs.hooks:
        lines.append("")
        lines.append("HOOKS:")
        for hook in cs.hooks:
            lines.append(f"  {hook.command}")
            if hook.status_lines:
                for sl in hook.status_lines:
                    suffix_part = ""
                    if sl.suffix:
                        prefix_map = {
                            "error": "!: ",
                            "running_agent": "@: ",
                            "killed_agent": "~@: ",
                            "running_process": "$: ",
                            "pending_dead_process": "?$: ",
                            "killed_process": "~$: ",
                            "summarize_complete": "%: ",
                        }
                        prefix = prefix_map.get(sl.suffix_type or "", "")
                        suffix_part = f" - ({prefix}{sl.suffix})"
                        if sl.summary:
                            suffix_part = f" - ({prefix}{sl.suffix} | {sl.summary})"

                    duration_part = f" ({sl.duration})" if sl.duration else ""
                    lines.append(
                        f"    ({sl.commit_entry_num}) [{sl.timestamp}] {sl.status}{duration_part}{suffix_part}"
                    )

    # COMMENTS section
    if cs.comments:
        lines.append("")
        lines.append("COMMENTS:")
        for comment in cs.comments:
            suffix_part = ""
            if comment.suffix:
                prefix = "!: " if comment.suffix_type == "error" else ""
                if comment.suffix_type == "running_agent":
                    prefix = "@: "
                suffix_part = f" - ({prefix}{comment.suffix})"
            lines.append(f"  [{comment.reviewer}] {comment.file_path}{suffix_part}")

    # MENTORS section
    if cs.mentors:
        lines.append("")
        lines.append("MENTORS:")
        for mentor_entry in cs.mentors:
            wip_marker = " (WIP)" if mentor_entry.is_wip else ""
            lines.append(
                f"  ({mentor_entry.entry_id}) {' '.join(mentor_entry.profiles)}{wip_marker}"
            )
            if mentor_entry.status_lines:
                for msl in mentor_entry.status_lines:
                    suffix_part = ""
                    if msl.suffix:
                        prefix_map = {
                            "running_agent": "@: ",
                            "error": "!: ",
                        }
                        prefix = prefix_map.get(msl.suffix_type or "", "")
                        suffix_part = f" - ({prefix}{msl.suffix})"
                    elif msl.duration:
                        suffix_part = f" - ({msl.duration})"

                    ts_part = f"[{msl.timestamp}] " if msl.timestamp else ""
                    lines.append(
                        f"    | {ts_part}{msl.profile_name}:{msl.mentor_name} - {msl.status}{suffix_part}"
                    )

    return "\n".join(lines)


def _format_axe_artifacts_for_clipboard() -> str:
    """Format all axe artifact files for clipboard.

    Returns:
        Formatted text with file paths as headers, or empty string if no files.
    """
    axe_dir = Path.home() / ".gai" / "axe"

    if not axe_dir.exists():
        return ""

    # Files to include in order
    artifact_files = [
        "status.json",
        "metrics.json",
        "recent_errors.json",
        "last_full_cycle.json",
        "last_hook_cycle.json",
    ]

    sections: list[str] = []

    for filename in artifact_files:
        file_path = axe_dir / filename
        if not file_path.exists():
            continue

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Pretty-print JSON content
            try:
                data = json.loads(content)
                content = json.dumps(data, indent=2)
            except json.JSONDecodeError:
                pass  # Use raw content if not valid JSON

            display_path = f"~/.gai/axe/{filename}"
            sections.append(f"===== {display_path} =====\n{content}")
        except OSError:
            continue

    return "\n\n".join(sections)
