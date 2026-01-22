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
from ...hints import parse_copy_input

TabName = Literal["changespecs", "agents", "axe"]

# Copy target option names (in order, 1-indexed for user)
COPY_TARGET_NAMES = [
    "Entire Project Spec File",
    "Entire ChangeSpec",
    "CL Name",
    "CL Number",
    "TUI Snapshot",
]


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
            self._copy_changespec_to_clipboard()
        elif self.current_tab == "agents":
            self._copy_agent_chat_to_clipboard()
        else:  # axe
            self._copy_axe_artifacts_to_clipboard()

    def _copy_changespec_to_clipboard(self) -> None:
        """Show copy target selection for the current ChangeSpec."""
        if not self.changespecs:
            self.notify("No ChangeSpec to copy", severity="warning")  # type: ignore[attr-defined]
            return

        changespec = self.changespecs[self.current_idx]

        # Store state for later processing
        self._copy_mode_active = True  # type: ignore[attr-defined]
        self._copy_changespec = changespec  # type: ignore[attr-defined]

        # Update detail panel to show copy targets
        from ..widgets import ChangeSpecDetail, HintInputBar

        detail_widget = self.query_one("#detail-panel", ChangeSpecDetail)  # type: ignore[attr-defined]
        detail_widget.show_copy_targets(changespec.name)

        # Mount the hint input bar
        detail_container = self.query_one("#detail-container")  # type: ignore[attr-defined]
        hint_bar = HintInputBar(mode="copy", id="hint-input-bar")
        detail_container.mount(hint_bar)

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

    def _process_copy_input(self, user_input: str) -> None:
        """Process copy target selection input.

        Args:
            user_input: The user's input string (e.g., "1", "1-3", "2@")
        """
        if not user_input:
            return

        # Get the stored changespec
        changespec: ChangeSpec | None = getattr(self, "_copy_changespec", None)
        if changespec is None:
            self.notify("No ChangeSpec selected", severity="error")  # type: ignore[attr-defined]
            return

        # Parse input
        targets, use_multi_format, invalid_targets = parse_copy_input(user_input)

        if invalid_targets:
            self.notify(  # type: ignore[attr-defined]
                f"Invalid selections: {', '.join(str(t) for t in invalid_targets)}",
                severity="warning",
            )
            return

        if not targets:
            self.notify("No valid targets selected", severity="warning")  # type: ignore[attr-defined]
            return

        # Collect content for each target
        contents: list[tuple[str, str]] = []  # (target_name, content)
        for target_num in targets:
            target_name = COPY_TARGET_NAMES[target_num - 1]  # Convert to 0-indexed
            content = self._get_copy_target_content(changespec, target_num)
            if content is None:
                # Error already notified by helper
                return
            contents.append((target_name, content))

        # Format output
        if use_multi_format:
            final_content = _format_multi_target_content(contents)
        else:
            # Single target without @ suffix - just copy raw content
            final_content = contents[0][1]

        # Copy to clipboard
        if _copy_to_system_clipboard(final_content):
            if len(targets) == 1:
                self.notify(f"Copied: {COPY_TARGET_NAMES[targets[0] - 1]}")  # type: ignore[attr-defined]
            else:
                self.notify(f"Copied {len(targets)} items")  # type: ignore[attr-defined]
        else:
            self.notify("Failed to copy to clipboard", severity="error")  # type: ignore[attr-defined]

    def _get_copy_target_content(
        self, changespec: ChangeSpec, target_num: int
    ) -> str | None:
        """Get content for a specific copy target.

        Args:
            changespec: The ChangeSpec to get content from.
            target_num: The target number (1-indexed).

        Returns:
            The content string, or None if an error occurred.
        """
        if target_num == 1:
            # Entire Project Spec File
            return self._get_project_spec_content(changespec)
        elif target_num == 2:
            # Entire ChangeSpec
            content = get_raw_changespec_text(changespec)
            if content is None:
                content = _format_changespec_for_clipboard(changespec)
            return content
        elif target_num == 3:
            # CL Name
            return changespec.name
        elif target_num == 4:
            # CL Number
            return self._get_cl_number(changespec)
        elif target_num == 5:
            # TUI Snapshot
            return self._get_tui_snapshot()
        else:
            self.notify(f"Invalid target: {target_num}", severity="error")  # type: ignore[attr-defined]
            return None

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

    def _get_tui_snapshot(self) -> str:
        """Get a plain text snapshot of the current TUI state.

        Returns:
            The TUI snapshot as plain text (ANSI codes stripped).
        """
        # For now, return a simple representation
        # In a full implementation, this would capture the actual TUI rendering
        lines: list[str] = []

        # Add CL list
        lines.append("=== CLs ===")
        for idx, cs in enumerate(self.changespecs):
            marker = ">" if idx == self.current_idx else " "
            lines.append(f"{marker} {cs.name} [{cs.status}]")

        # Add detail panel
        lines.append("")
        lines.append("=== Detail ===")
        if self.changespecs:
            cs = self.changespecs[self.current_idx]
            lines.append(f"NAME: {cs.name}")
            lines.append(f"DESCRIPTION: {cs.description}")
            if cs.cl:
                lines.append(f"CL: {cs.cl}")
            lines.append(f"STATUS: {cs.status}")

        return "\n".join(lines)


def _format_multi_target_content(contents: list[tuple[str, str]]) -> str:
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
