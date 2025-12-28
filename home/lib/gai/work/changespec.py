"""ChangeSpec parsing utilities."""

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


# Error suffix messages that require "!: " prefix when formatting/displaying
ERROR_SUFFIX_MESSAGES = frozenset(
    {
        "ZOMBIE",
        "Hook Command Failed",
        "Unresolved Critique Comments",
    }
)


def is_error_suffix(suffix: str | None) -> bool:
    """Check if a suffix indicates an error condition requiring '!: ' prefix.

    Args:
        suffix: The suffix value (message part only, not including "!: " prefix).

    Returns:
        True if the suffix indicates an error, False otherwise.
    """
    return suffix is not None and suffix in ERROR_SUFFIX_MESSAGES


# Acknowledged suffix messages that use "~: " prefix (yellow/orange color)
# These are suffixes that have been "acknowledged" (transformed from error state)
ACKNOWLEDGED_SUFFIX_MESSAGES = frozenset(
    {
        "NEW PROPOSAL",  # After proposal becomes "old" (superseded by newer regular entry)
    }
)


def is_acknowledged_suffix(suffix: str | None) -> bool:
    """Check if a suffix indicates an acknowledged condition requiring '~: ' prefix.

    Acknowledged suffixes are shown in yellow/orange to indicate they've been seen
    but are no longer requiring immediate attention.

    Args:
        suffix: The suffix value (message part only, not including "~: " prefix).

    Returns:
        True if the suffix is acknowledged type, False otherwise.
    """
    return suffix is not None and suffix in ACKNOWLEDGED_SUFFIX_MESSAGES


@dataclass
class HistoryEntry:
    """Represents a single entry in the HISTORY field.

    Regular entries have format: (N) Note text
    Proposed entries have format: (Na) Note text (where 'a' is a lowercase letter)
    Entries can have optional suffix: (Na) Note text - (!: MSG) or - (~: MSG)
    """

    number: int
    note: str
    chat: str | None = None
    diff: str | None = None
    proposal_letter: str | None = None  # e.g., 'a', 'b', 'c' for proposed entries
    suffix: str | None = None  # e.g., "NEW PROPOSAL" (message without prefix)
    suffix_type: str | None = (
        None  # "error" for !:, "acknowledged" for ~:, None for plain
    )

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
      (N) [YYmmdd_HHMMSS] RUNNING/PASSED/FAILED/ZOMBIE (XmYs) - (!: MSG)
    Where N is the HISTORY entry number (1-based).

    The optional suffix can be:
    - A timestamp (YYmmdd_HHMMSS) indicating a fix-hook agent is running
    - "Hook Command Failed" indicating no fix-hook hints should be shown
    - "ZOMBIE" indicating a stale fix-hook agent (>2h old timestamp)

    Note: The suffix stores just the message (e.g., "ZOMBIE"), and the
    "!: " prefix is added when formatting for display/storage.
    """

    history_entry_num: str  # The HISTORY entry ID (e.g., "1", "1a", "2")
    timestamp: str  # YYmmdd_HHMMSS format
    status: str  # RUNNING, PASSED, FAILED, ZOMBIE
    duration: str | None = None  # e.g., "1m23s"
    suffix: str | None = None  # e.g., "YYmmdd_HHMMSS", "ZOMBIE", "Hook Command Failed"


@dataclass
class HookEntry:
    """Represents a single hook command entry in the HOOKS field.

    Format in file:
      some_command
        (1) [YYmmdd_HHMMSS] PASSED (1m23s)
        (2) [YYmmdd_HHMMSS] RUNNING

    Each hook can have multiple status lines, one per HISTORY entry.

    Commands starting with "!" indicate that FAILED status lines should
    auto-append "- (!: Hook Command Failed)" to skip fix-hook hints.
    The "!" prefix is stripped when displaying or running the command.
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


@dataclass
class CommentEntry:
    """Represents a single entry in the COMMENTS field.

    Format in file:
      [reviewer] ~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json
      [reviewer] ~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json - (SUFFIX)
      [reviewer] ~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json - (!: MSG)

    The optional suffix can be:
    - A timestamp (YYmmdd_HHMMSS) indicating a CRS workflow is running
    - "Unresolved Critique Comments" indicating CRS completed but comments remain
    - "ZOMBIE" indicating a stale CRS run (>2h old timestamp)

    Note: The suffix stores just the message (e.g., "ZOMBIE"), and the
    "!: " prefix is added when formatting for display/storage.
    """

    reviewer: str  # The reviewer username (e.g., "johndoe")
    file_path: str  # Full path to the comments JSON file
    suffix: str | None = (
        None  # e.g., "YYmmdd_HHMMSS", "ZOMBIE", "Unresolved Critique Comments"
    )


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

    suffix_val = entry_dict.get("suffix")
    suffix = str(suffix_val) if suffix_val is not None else None

    suffix_type_val = entry_dict.get("suffix_type")
    suffix_type = str(suffix_type_val) if suffix_type_val is not None else None

    return HistoryEntry(
        number=number,
        note=note,
        chat=chat,
        diff=diff,
        proposal_letter=proposal_letter,
        suffix=suffix,
        suffix_type=suffix_type,
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
    comments: list[CommentEntry] | None = None


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
    comment_entries: list[CommentEntry] = []
    line_number = start_idx + 1  # Convert to 1-based line numbering

    in_description = False
    in_test_targets = False
    in_kickstart = False
    in_history = False
    in_hooks = False
    in_comments = False
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
            in_comments = False
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
            in_comments = False
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
            in_comments = False
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
            in_comments = False
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
            in_comments = False
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
            in_comments = False
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
            in_comments = False
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
            in_comments = False
        elif line.startswith("COMMENTS:"):
            # Save any pending history entry
            if current_history_entry is not None:
                history_entries.append(_build_history_entry(current_history_entry))
                current_history_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            in_comments = True
            in_hooks = False
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
            in_comments = False
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
                    timestamp = (
                        new_status_match.group(2) + "_" + new_status_match.group(3)
                    )
                    status_val = new_status_match.group(4)
                    duration_val = new_status_match.group(5)
                    suffix_val = new_status_match.group(6)
                    # Strip "!: " or "~: " prefix if present to store just the message
                    if suffix_val:
                        if suffix_val.startswith("!:"):
                            suffix_val = suffix_val[2:].strip()
                        elif suffix_val.startswith("~:"):
                            suffix_val = suffix_val[2:].strip()
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
                        timestamp = (
                            old_status_match.group(1) + "_" + old_status_match.group(2)
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
        elif in_comments:
            # Parse COMMENTS entries
            # Format: [reviewer] path or [reviewer] path - (suffix)
            stripped = line.strip()
            if line.startswith("  ") and not line.startswith("    "):
                # This is a comment entry line (2-space indented)
                # Pattern: [reviewer] path or [reviewer] path - (suffix)
                comment_match = re.match(
                    r"^\[([^\]]+)\]\s+(\S+)(?:\s+-\s+\(([^)]+)\))?$",
                    stripped,
                )
                if comment_match:
                    reviewer = comment_match.group(1)
                    file_path_val = comment_match.group(2)
                    suffix_val = comment_match.group(3)
                    # Strip "!: " or "~: " prefix if present to store just the message
                    if suffix_val:
                        if suffix_val.startswith("!:"):
                            suffix_val = suffix_val[2:].strip()
                        elif suffix_val.startswith("~:"):
                            suffix_val = suffix_val[2:].strip()
                    comment_entries.append(
                        CommentEntry(
                            reviewer=reviewer,
                            file_path=file_path_val,
                            suffix=suffix_val,
                        )
                    )
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

                raw_note = history_match.group(3)

                # Check for suffix pattern at end of note:
                # - (!: MSG), - (~: MSG), or - (MSG)
                suffix_match = re.search(r"\s+-\s+\((!:|~:)?\s*([^)]+)\)$", raw_note)
                if suffix_match:
                    note_without_suffix = raw_note[: suffix_match.start()]
                    prefix = suffix_match.group(1)  # "!:" or "~:" or None
                    suffix_msg = suffix_match.group(2).strip()
                    if prefix == "!:":
                        suffix_type_val = "error"
                    elif prefix == "~:":
                        suffix_type_val = "acknowledged"
                    else:
                        suffix_type_val = None
                else:
                    note_without_suffix = raw_note
                    suffix_msg = None
                    suffix_type_val = None

                # Start new entry
                current_history_entry = {
                    "number": int(history_match.group(1)),
                    "proposal_letter": history_match.group(
                        2
                    ),  # None for regular entries
                    "note": note_without_suffix,
                    "chat": None,
                    "diff": None,
                    "suffix": suffix_msg,
                    "suffix_type": suffix_type_val,
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
                in_comments = False

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
                comments=comment_entries if comment_entries else None,
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
