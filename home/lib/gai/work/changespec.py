"""ChangeSpec parsing and display utilities."""

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from running_field import get_claimed_workspaces


@dataclass
class HistoryEntry:
    """Represents a single entry in the HISTORY field.

    Regular entries have format: (N) Note text
    Proposed entries have format: (Na) Note text (where 'a' is a lowercase letter)
    """

    number: int
    note: str
    chat: str | None = None
    diff: str | None = None
    proposal_letter: str | None = None  # e.g., 'a', 'b', 'c' for proposed entries

    @property
    def is_proposed(self) -> bool:
        """Check if this is a proposed (not yet accepted) history entry."""
        return self.proposal_letter is not None

    @property
    def display_number(self) -> str:
        """Get the display string for this entry's number (e.g., '2' or '2a')."""
        if self.proposal_letter:
            return f"{self.number}{self.proposal_letter}"
        return str(self.number)


def parse_history_entry_id(entry_id: str) -> tuple[int, str]:
    """Parse a history entry ID into (number, letter) for sorting.

    Args:
        entry_id: The entry ID string (e.g., "1", "1a", "2").

    Returns:
        Tuple of (number, letter) where letter is "" for regular entries.
        E.g., "1" -> (1, ""), "1a" -> (1, "a"), "2" -> (2, "").
    """
    # Match digit(s) optionally followed by a letter
    match = re.match(r"^(\d+)([a-z]?)$", entry_id)
    if match:
        return int(match.group(1)), match.group(2)
    # Fallback for unexpected format
    return 0, entry_id


@dataclass
class HookStatusLine:
    """Represents a single hook status line.

    Format in file:
      (N) [YYmmdd_HHMMSS] RUNNING/PASSED/FAILED/ZOMBIE (XmYs) - (SUFFIX)
    Where N is the HISTORY entry number (1-based).

    The optional suffix can be:
    - A timestamp (YYmmdd_HHMMSS) indicating a fix-hook agent is running
    - "!" indicating no fix-hook hints should be shown for this hook
    """

    history_entry_num: str  # The HISTORY entry ID (e.g., "1", "1a", "2")
    timestamp: str  # YYmmddHHMMSS format
    status: str  # RUNNING, PASSED, FAILED, ZOMBIE
    duration: str | None = None  # e.g., "1m23s"
    suffix: str | None = None  # e.g., "YYmmdd_HHMMSS" or "!"


@dataclass
class HookEntry:
    """Represents a single hook command entry in the HOOKS field.

    Format in file:
      some_command
        (1) [YYmmdd_HHMMSS] PASSED (1m23s)
        (2) [YYmmdd_HHMMSS] RUNNING

    Each hook can have multiple status lines, one per HISTORY entry.

    Commands starting with "!" indicate that FAILED status lines should
    auto-append "- (!)" to skip fix-hook hints. The "!" prefix is stripped
    when displaying or running the command.
    """

    command: str
    status_lines: list[HookStatusLine] | None = None

    @property
    def display_command(self) -> str:
        """Get the command for display purposes (strips leading '!')."""
        if self.command.startswith("!"):
            return self.command[1:]
        return self.command

    @property
    def run_command(self) -> str:
        """Get the command to actually run (strips leading '!')."""
        if self.command.startswith("!"):
            return self.command[1:]
        return self.command

    @property
    def latest_status_line(self) -> HookStatusLine | None:
        """Get the most recent status line (highest history entry ID)."""
        if not self.status_lines:
            return None
        return max(
            self.status_lines,
            key=lambda sl: parse_history_entry_id(sl.history_entry_num),
        )

    def get_status_line_for_history_entry(
        self, history_entry_id: str
    ) -> HookStatusLine | None:
        """Get status line for a specific HISTORY entry ID (e.g., '1', '1a')."""
        if not self.status_lines:
            return None
        for sl in self.status_lines:
            if sl.history_entry_num == history_entry_id:
                return sl
        return None

    # Backward-compatible properties that delegate to latest_status_line
    @property
    def timestamp(self) -> str | None:
        """Get timestamp from the latest status line (backward compatibility)."""
        sl = self.latest_status_line
        return sl.timestamp if sl else None

    @property
    def status(self) -> str | None:
        """Get status from the latest status line (backward compatibility)."""
        sl = self.latest_status_line
        return sl.status if sl else None

    @property
    def duration(self) -> str | None:
        """Get duration from the latest status line (backward compatibility)."""
        sl = self.latest_status_line
        return sl.duration if sl else None


def _build_history_entry(entry_dict: dict[str, str | int | None]) -> HistoryEntry:
    """Build a HistoryEntry from a dict with proper type handling."""
    number_val = entry_dict.get("number", 0)
    number = int(number_val) if number_val is not None else 0

    note_val = entry_dict.get("note", "")
    note = str(note_val) if note_val is not None else ""

    chat_val = entry_dict.get("chat")
    chat = str(chat_val) if chat_val is not None else None

    diff_val = entry_dict.get("diff")
    diff = str(diff_val) if diff_val is not None else None

    proposal_letter_val = entry_dict.get("proposal_letter")
    proposal_letter = (
        str(proposal_letter_val) if proposal_letter_val is not None else None
    )

    return HistoryEntry(
        number=number,
        note=note,
        chat=chat,
        diff=diff,
        proposal_letter=proposal_letter,
    )


@dataclass
class ChangeSpec:
    """Represents a single ChangeSpec."""

    name: str
    description: str
    parent: str | None
    cl: str | None
    status: str
    test_targets: list[str] | None
    kickstart: str | None
    file_path: str
    line_number: int
    history: list[HistoryEntry] | None = None
    hooks: list[HookEntry] | None = None


def _parse_changespec_from_lines(
    lines: list[str], start_idx: int, file_path: str
) -> tuple[ChangeSpec | None, int]:
    """Parse a single ChangeSpec from lines starting at start_idx.

    Returns:
        Tuple of (ChangeSpec or None, next_index_to_process)
    """
    name: str | None = None
    description_lines: list[str] = []
    parent: str | None = None
    cl: str | None = None
    status: str | None = None
    test_targets: list[str] = []
    kickstart_lines: list[str] = []
    history_entries: list[HistoryEntry] = []
    current_history_entry: dict[str, str | int | None] | None = None
    hook_entries: list[HookEntry] = []
    current_hook_entry: HookEntry | None = None
    line_number = start_idx + 1  # Convert to 1-based line numbering

    in_description = False
    in_test_targets = False
    in_kickstart = False
    in_history = False
    in_hooks = False
    idx = start_idx
    consecutive_blank_lines = 0

    while idx < len(lines):
        line = lines[idx]

        # Check for end of ChangeSpec (next ChangeSpec header or 2 blank lines)
        if line.strip().startswith("##") and idx > start_idx:
            break
        if line.strip() == "":
            consecutive_blank_lines += 1
            # 2 blank lines indicate end of ChangeSpec
            if consecutive_blank_lines >= 2:
                break
        else:
            consecutive_blank_lines = 0

        # Parse field lines
        if line.startswith("NAME: "):
            # If we already have a name, this is a new ChangeSpec - stop parsing
            if name is not None:
                # Save any pending entries
                if current_history_entry is not None:
                    history_entries.append(_build_history_entry(current_history_entry))
                if current_hook_entry is not None:
                    hook_entries.append(current_hook_entry)
                # Don't increment idx - let the caller re-process this NAME line
                idx -= 1
                break
            name = line[6:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_history = False
            in_hooks = False
        elif line.startswith("DESCRIPTION:"):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            in_description = True
            in_test_targets = False
            in_kickstart = False
            in_history = False
            in_hooks = False
            # Check if description is on the same line
            desc_inline = line[12:].strip()
            if desc_inline:
                description_lines.append(desc_inline)
        elif line.startswith("KICKSTART:"):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            in_kickstart = True
            in_description = False
            in_test_targets = False
            in_history = False
            in_hooks = False
            # Check if kickstart is on the same line
            kickstart_inline = line[10:].strip()
            if kickstart_inline:
                kickstart_lines.append(kickstart_inline)
        elif line.startswith("PARENT: "):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            parent = line[8:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_history = False
            in_hooks = False
        elif line.startswith("CL: "):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            cl = line[4:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_history = False
            in_hooks = False
        elif line.startswith("STATUS: "):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            status = line[8:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_history = False
            in_hooks = False
        elif line.startswith("HISTORY:"):
            # Save any pending history entry before starting new field
            if current_history_entry is not None:
                history_entries.append(_build_history_entry(current_history_entry))
                current_history_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            in_history = True
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_hooks = False
        elif line.startswith("HOOKS:"):
            # Save any pending history entry
            if current_history_entry is not None:
                history_entries.append(_build_history_entry(current_history_entry))
                current_history_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            in_hooks = True
            in_history = False
            in_description = False
            in_test_targets = False
            in_kickstart = False
        elif line.startswith("TEST TARGETS:"):
            # Save any pending history entry
            if current_history_entry is not None:
                history_entries.append(_build_history_entry(current_history_entry))
                current_history_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            in_test_targets = True
            in_description = False
            in_kickstart = False
            in_history = False
            in_hooks = False
            # Check if targets are on the same line
            targets_inline = line[13:].strip()
            if targets_inline:
                # Treat as single target (may contain spaces like "target (FAILED)")
                test_targets.append(targets_inline)
        elif in_hooks:
            # Parse HOOKS entries
            # Format (new):
            #   some_command
            #     (N) [YYmmdd_HHMMSS] STATUS (XmYs)
            # Format (old, for backward compatibility):
            #   some_command
            #     [YYmmdd_HHMMSS] STATUS (XmYs)
            stripped = line.strip()
            if line.startswith("  ") and not line.startswith("    "):
                # This is a command line (2-space indented, not 4-space)
                # Only if it doesn't start with '[' or '(' (status line markers)
                if not stripped.startswith("[") and not stripped.startswith("("):
                    # Save previous hook entry if exists
                    if current_hook_entry is not None:
                        hook_entries.append(current_hook_entry)
                    # Start new hook entry
                    current_hook_entry = HookEntry(command=stripped)
            elif line.startswith("    "):
                # This is a status line (4-space indented)
                # Try new format first: (N) [YYmmdd_HHMMSS] STATUS (XmYs) - (SUFFIX)
                new_status_match = re.match(
                    r"^\((\d+[a-z]?)\)\s+\[(\d{6})_(\d{6})\]\s*(RUNNING|PASSED|FAILED|ZOMBIE)"
                    r"(?:\s+\(([^)]+)\))?(?:\s+-\s+\(([^)]+)\))?$",
                    stripped,
                )
                if new_status_match and current_hook_entry is not None:
                    # New format with history entry ID (e.g., "1", "1a", "2")
                    history_num = new_status_match.group(1)
                    timestamp = new_status_match.group(2) + new_status_match.group(3)
                    status_val = new_status_match.group(4)
                    duration_val = new_status_match.group(5)
                    suffix_val = new_status_match.group(6)
                    status_line = HookStatusLine(
                        history_entry_num=history_num,
                        timestamp=timestamp,
                        status=status_val,
                        duration=duration_val,
                        suffix=suffix_val,
                    )
                    if current_hook_entry.status_lines is None:
                        current_hook_entry.status_lines = []
                    current_hook_entry.status_lines.append(status_line)
                elif stripped.startswith("["):
                    # Old format: [YYmmdd_HHMMSS] STATUS (XmYs)
                    old_status_match = re.match(
                        r"^\[(\d{6})_(\d{6})\]\s*(RUNNING|PASSED|FAILED|ZOMBIE)"
                        r"(?:\s+\(([^)]+)\))?$",
                        stripped,
                    )
                    if old_status_match and current_hook_entry is not None:
                        # Old format - treat as history entry 1 for compatibility
                        timestamp = old_status_match.group(1) + old_status_match.group(
                            2
                        )
                        status_val = old_status_match.group(3)
                        duration_val = old_status_match.group(4)
                        status_line = HookStatusLine(
                            history_entry_num="1",  # Default to "1" for old format
                            timestamp=timestamp,
                            status=status_val,
                            duration=duration_val,
                        )
                        if current_hook_entry.status_lines is None:
                            current_hook_entry.status_lines = []
                        current_hook_entry.status_lines.append(status_line)
        elif in_history:
            # Parse HISTORY entries
            stripped = line.strip()
            # Check for new history entry: (N) or (Na) Note text
            # Supports both regular entries (N) and proposed entries (Na)
            history_match = re.match(r"^\((\d+)([a-z])?\)\s+(.+)$", stripped)
            if history_match:
                # Save previous entry if exists
                if current_history_entry is not None:
                    history_entries.append(_build_history_entry(current_history_entry))
                # Start new entry
                current_history_entry = {
                    "number": int(history_match.group(1)),
                    "proposal_letter": history_match.group(
                        2
                    ),  # None for regular entries
                    "note": history_match.group(3),
                    "chat": None,
                    "diff": None,
                }
            elif stripped.startswith("| CHAT:"):
                if current_history_entry is not None:
                    current_history_entry["chat"] = stripped[7:].strip()
            elif stripped.startswith("| DIFF:"):
                if current_history_entry is not None:
                    current_history_entry["diff"] = stripped[7:].strip()
            # If line doesn't match history format, stay in history mode
            # (blank lines or other content will be ignored)
        elif in_description and line.startswith("  "):
            # Description continuation (2-space indented)
            # Strip trailing newline since we'll add them back with join
            description_lines.append(line[2:].rstrip("\n"))
        elif in_kickstart and line.startswith("  "):
            # Kickstart continuation (2-space indented)
            # Strip trailing newline since we'll add them back with join
            kickstart_lines.append(line[2:].rstrip("\n"))
        elif in_test_targets and line.startswith("  "):
            # Test targets continuation (2-space indented)
            target = line.strip()
            if target:
                test_targets.append(target)
        elif line.strip() == "":
            # Blank line - preserve in description or kickstart if we're in those modes
            if in_description:
                description_lines.append("")
            elif in_kickstart:
                kickstart_lines.append("")
        else:
            # Any other content ends the special parsing modes
            if not line.startswith("#"):  # Ignore comment lines
                in_description = False
                in_test_targets = False
                in_kickstart = False
                in_history = False
                in_hooks = False

        idx += 1

    # Save any pending history entry
    if current_history_entry is not None:
        history_entries.append(_build_history_entry(current_history_entry))

    # Save any pending hook entry
    if current_hook_entry is not None:
        hook_entries.append(current_hook_entry)

    # Create ChangeSpec if we found required fields
    if name and status:
        description = "\n".join(description_lines).strip()
        kickstart = "\n".join(kickstart_lines).strip() if kickstart_lines else None
        return (
            ChangeSpec(
                name=name,
                description=description,
                parent=parent,
                cl=cl,
                status=status,
                test_targets=test_targets if test_targets else None,
                kickstart=kickstart,
                file_path=file_path,
                line_number=line_number,
                history=history_entries if history_entries else None,
                hooks=hook_entries if hook_entries else None,
            ),
            idx,
        )

    return None, idx


def parse_project_file(file_path: str) -> list[ChangeSpec]:
    """Parse all ChangeSpecs from a project file.

    Args:
        file_path: Path to the project markdown file

    Returns:
        List of ChangeSpec objects
    """
    changespecs: list[ChangeSpec] = []

    try:
        with open(file_path) as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return []

    idx = 0
    while idx < len(lines):
        line = lines[idx]

        # Look for ChangeSpec start by detecting NAME: field
        # (ChangeSpecs can start with ## ChangeSpec header OR directly with NAME:)
        if re.match(r"^##\s+ChangeSpec", line.strip()):
            # Skip the header line and parse the ChangeSpec
            changespec, next_idx = _parse_changespec_from_lines(
                lines, idx + 1, file_path
            )
            if changespec:
                changespecs.append(changespec)
            idx = next_idx
        elif line.startswith("NAME: "):
            # ChangeSpec starts directly with NAME field (no header)
            changespec, next_idx = _parse_changespec_from_lines(lines, idx, file_path)
            if changespec:
                changespecs.append(changespec)
            idx = next_idx
        else:
            idx += 1

    return changespecs


def find_all_changespecs() -> list[ChangeSpec]:
    """Find all ChangeSpecs in all project files.

    Returns:
        List of all ChangeSpec objects from ~/.gai/projects/<project>/<project>.gp files
    """
    projects_dir = Path.home() / ".gai" / "projects"

    if not projects_dir.exists():
        return []

    all_changespecs: list[ChangeSpec] = []

    # Iterate through project directories
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue

        # Look for <project>.gp file inside the project directory
        project_name = project_dir.name
        gp_file = project_dir / f"{project_name}.gp"

        if gp_file.exists():
            changespecs = parse_project_file(str(gp_file))
            all_changespecs.extend(changespecs)

    return all_changespecs


def _get_bug_field(project_file: str) -> str | None:
    """Get the BUG field value from a project file.

    Args:
        project_file: Path to the ProjectSpec file

    Returns:
        BUG field value or None if not found
    """
    if not os.path.exists(project_file):
        return None

    try:
        with open(project_file, encoding="utf-8") as f:
            for line in f:
                if line.startswith("BUG:"):
                    return line.split(":", 1)[1].strip()
                # Stop if we hit a NAME field (end of header section)
                if line.startswith("NAME:"):
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
    - Changes Requested: #FFAF00 (orange)
    - Submitted: #00AF00 (green)
    - Reverted: #808080 (gray)
    """
    # Strip workspace suffix before looking up color
    # Pattern: " (<project>_<N>)" at the end of the status
    base_status = re.sub(r" \([a-zA-Z0-9_-]+_\d+\)$", "", status)

    status_colors = {
        "Drafted": "#87D700",
        "Mailed": "#00D787",
        "Changes Requested": "#FFAF00",
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
                text.append(f"){after_path}\n", style="#D7D7AF")
                hint_counter += 1
            else:
                text.append(f"{entry.note}\n", style="#D7D7AF")

            # CHAT field (if present) - 6 spaces = 2 (base indent) + 4 (sub-field indent)
            if entry.chat:
                text.append("      ", style="")
                if show_history_hints:
                    hint_mappings[hint_counter] = entry.chat
                    text.append(f"[{hint_counter}] ", style="bold #FFFF00")
                    hint_counter += 1
                text.append("| CHAT: ", style="#87AFFF")
                chat_path = entry.chat.replace(str(Path.home()), "~")
                text.append(f"{chat_path}\n", style="#87AFFF")
            # DIFF field (if present)
            if entry.diff:
                text.append("      ", style="")
                if show_history_hints:
                    hint_mappings[hint_counter] = entry.diff
                    text.append(f"[{hint_counter}] ", style="bold #FFFF00")
                    hint_counter += 1
                text.append("| DIFF: ", style="#87AFFF")
                diff_path = entry.diff.replace(str(Path.home()), "~")
                text.append(f"{diff_path}\n", style="#87AFFF")

    # HOOKS field (only display if present)
    if changespec.hooks:
        # Lazy import to avoid circular dependency
        from .hooks import (
            format_timestamp_display,
            get_hook_output_path,
            get_last_history_entry_id,
        )

        # Get the last HISTORY entry ID for hooks_latest_only mode (e.g., "1", "1a")
        last_history_entry_id = get_last_history_entry_id(changespec)

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

                for sl in sorted_status_lines:
                    text.append("    ", style="")
                    # Determine if we should show a hint for this status line
                    show_hint = False
                    if with_hints:
                        if hints_for == "hooks_latest_only":
                            # Show hint for status lines matching the last HISTORY entry
                            show_hint = (
                                last_history_entry_id is not None
                                and sl.history_entry_num == last_history_entry_id
                            )
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
                    # - "!" (zombie): red background
                    # - timestamp (YYmmdd_HHMMSS): pink background
                    # - proposal ID (e.g., "2a"): yellow background
                    if sl.suffix:
                        text.append(" - ")
                        if sl.suffix == "!":
                            text.append(f"({sl.suffix})", style="bold white on #AF0000")
                        elif _is_suffix_timestamp(sl.suffix):
                            # Timestamp suffix - already stored with underscore
                            text.append(f"({sl.suffix})", style="bold white on #D75F87")
                        else:
                            # Proposal ID suffix (e.g., "2a")
                            text.append(
                                f"({sl.suffix})", style="bold #000000 on #D7AF00"
                            )
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
