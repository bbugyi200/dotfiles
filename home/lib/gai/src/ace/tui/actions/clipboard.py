"""Clipboard action methods for the ace TUI app."""

from __future__ import annotations

import re
import subprocess
import sys
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ...changespec import ChangeSpec
    from ..models.agent import Agent

from ...changespec import get_raw_changespec_text

TabName = Literal["changespecs", "agents", "axe"]


class ClipboardMixin:
    """Mixin providing clipboard copy actions for all tabs."""

    # Type hints for attributes accessed from AceApp (defined at runtime)
    changespecs: list[ChangeSpec]
    current_idx: int
    current_tab: TabName
    _agents: list[Agent]
    _axe_output: str

    def action_copy_tab_content(self) -> None:
        """Copy tab-specific content to clipboard based on current tab."""
        if self.current_tab == "changespecs":
            self.action_start_copy_mode()
        elif self.current_tab == "agents":
            self._copy_agent_chat_to_clipboard()
        else:  # axe
            self._copy_axe_artifacts_to_clipboard()

    def action_start_copy_mode(self) -> None:
        """Start copy mode - wait for second key to determine copy action."""
        if self.current_tab != "changespecs":
            return

        if not self.changespecs:
            self.notify("No ChangeSpec to copy", severity="warning")  # type: ignore[attr-defined]
            return

        self._copy_mode_active = True  # type: ignore[attr-defined]

    def _handle_copy_key(self, key: str) -> bool:
        """Handle the second key in copy mode sequence.

        Args:
            key: The key pressed after %.

        Returns:
            True if key was handled, False otherwise.
        """
        self._copy_mode_active = False  # type: ignore[attr-defined]

        if self.current_tab != "changespecs":
            return False

        if not self.changespecs:
            return False

        if key == "percent_sign":  # %%
            self._copy_changespec()
        elif key == "exclamation_mark":  # %!
            self._copy_changespec_and_project()
        elif key == "b":  # %b
            self._copy_bug_number()
        elif key == "c":  # %c
            self._copy_cl_number()
        elif key == "p":  # %p
            self._copy_project_spec()
        elif key == "escape":
            # Cancel copy mode silently
            return True
        else:
            self.notify("Unknown copy key", severity="warning")  # type: ignore[attr-defined]
            return False
        return True

    def _copy_changespec(self) -> None:
        """Copy the raw changespec text to clipboard (%%)."""
        changespec = self.changespecs[self.current_idx]
        content = get_raw_changespec_text(changespec)
        if content is None:
            content = _format_changespec_for_clipboard(changespec)

        if _copy_to_system_clipboard(content.strip()):
            self.notify("Copied: ChangeSpec")  # type: ignore[attr-defined]
        else:
            self.notify("Failed to copy to clipboard", severity="error")  # type: ignore[attr-defined]

    def _copy_changespec_and_project(self) -> None:
        """Copy changespec and project spec with multi-format (%!)."""
        changespec = self.changespecs[self.current_idx]

        # Get changespec content
        cs_content = get_raw_changespec_text(changespec)
        if cs_content is None:
            cs_content = _format_changespec_for_clipboard(changespec)

        # Get project spec content
        proj_content = self._get_project_spec_content(changespec)
        if proj_content is None:
            return  # Error already notified

        # Format with headers
        contents = [
            ("ChangeSpec", cs_content.strip()),
            ("Project Spec File", proj_content.strip()),
        ]
        final_content = _format_multi_copy_content(contents)

        if _copy_to_system_clipboard(final_content):
            self.notify("Copied: ChangeSpec + Project Spec")  # type: ignore[attr-defined]
        else:
            self.notify("Failed to copy to clipboard", severity="error")  # type: ignore[attr-defined]

    def _copy_bug_number(self) -> None:
        """Copy the bug number from the current changespec (%b)."""
        changespec = self.changespecs[self.current_idx]
        bug_number = self._get_bug_number(changespec)
        if bug_number is None:
            return  # Error already notified

        if _copy_to_system_clipboard(bug_number):
            self.notify(f"Copied: Bug Number ({bug_number})")  # type: ignore[attr-defined]
        else:
            self.notify("Failed to copy to clipboard", severity="error")  # type: ignore[attr-defined]

    def _copy_cl_number(self) -> None:
        """Copy the CL number from the current changespec (%c)."""
        changespec = self.changespecs[self.current_idx]
        cl_number = self._get_cl_number(changespec)
        if cl_number is None:
            return  # Error already notified

        if _copy_to_system_clipboard(cl_number):
            self.notify(f"Copied: CL Number ({cl_number})")  # type: ignore[attr-defined]
        else:
            self.notify("Failed to copy to clipboard", severity="error")  # type: ignore[attr-defined]

    def _copy_project_spec(self) -> None:
        """Copy the project spec file content (%p)."""
        changespec = self.changespecs[self.current_idx]
        content = self._get_project_spec_content(changespec)
        if content is None:
            return  # Error already notified

        if _copy_to_system_clipboard(content.strip()):
            self.notify("Copied: Project Spec File")  # type: ignore[attr-defined]
        else:
            self.notify("Failed to copy to clipboard", severity="error")  # type: ignore[attr-defined]

    def _get_bug_number(self, changespec: ChangeSpec) -> str | None:
        """Extract the bug number from a ChangeSpec's bug field.

        Args:
            changespec: The ChangeSpec.

        Returns:
            The bug number string, or None if unavailable.
        """
        if not changespec.bug:
            self.notify("No bug number available", severity="warning")  # type: ignore[attr-defined]
            return None

        return changespec.bug

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
        """Copy axe output log to clipboard."""
        content = self._format_axe_output_for_clipboard()

        if not content:
            self.notify("No axe output to copy", severity="warning")  # type: ignore[attr-defined]
            return

        if _copy_to_system_clipboard(content):
            self.notify("Copied axe output")  # type: ignore[attr-defined]
        else:
            self.notify("Failed to copy to clipboard", severity="error")  # type: ignore[attr-defined]

    def _format_axe_output_for_clipboard(self) -> str:
        """Format axe output log for clipboard.

        Returns:
            The output log content with ANSI codes stripped.
        """
        if not self._axe_output:
            return ""

        # Strip ANSI escape codes for clean clipboard content
        ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
        return ansi_escape.sub("", self._axe_output)

    def _get_project_spec_content(self, changespec: ChangeSpec) -> str | None:
        """Read the entire project spec (.gp) file content.

        Args:
            changespec: The ChangeSpec (to get file_path).

        Returns:
            The file content, or None if an error occurred.
        """
        try:
            with open(changespec.file_path) as f:
                return f.read().rstrip("\n")
        except OSError as e:
            self.notify(f"Could not read project file: {e}", severity="error")  # type: ignore[attr-defined]
            return None

    def _get_cl_number(self, changespec: ChangeSpec) -> str | None:
        """Extract the CL number from a ChangeSpec's CL URL.

        Args:
            changespec: The ChangeSpec.

        Returns:
            The CL number string, or None if unavailable.
        """
        if not changespec.cl:
            self.notify("No CL URL available", severity="warning")  # type: ignore[attr-defined]
            return None

        # Match http://cl/<number> or https://cl/<number>
        match = re.match(r"https?://cl/(\d+)", changespec.cl)
        if match:
            return match.group(1)

        self.notify("Could not extract CL number from URL", severity="warning")  # type: ignore[attr-defined]
        return None


def _format_multi_copy_content(contents: list[tuple[str, str]]) -> str:
    """Format multiple copy targets with headers and code blocks.

    Args:
        contents: List of (target_name, content) tuples.

    Returns:
        Formatted string with each target prefixed by ### header and wrapped in code blocks.
    """
    parts: list[str] = []
    for target_name, content in contents:
        parts.append(f"### {target_name}")
        parts.append("```")
        parts.append(content)
        parts.append("```")
    return "\n".join(parts)


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
