"""ChangeSpec parsing implementation."""

import re

from .models import (
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
    MentorEntry,
)
from .section_parsers import (
    CommitEntryDict,
    build_commit_entry,
    parse_comments_line,
    parse_commits_line,
    parse_hooks_line,
    parse_mentors_line,
)


class _ParserState:
    """Encapsulates parser state for a single ChangeSpec."""

    def __init__(self, start_idx: int, file_path: str) -> None:
        # Field values
        self.name: str | None = None
        self.description_lines: list[str] = []
        self.parent: str | None = None
        self.cl: str | None = None
        self.bug: str | None = None
        self.status: str | None = None
        self.test_targets: list[str] = []
        self.kickstart_lines: list[str] = []

        # Entry collections
        self.commit_entries: list[CommitEntry] = []
        self.current_commit_entry: CommitEntryDict | None = None
        self.hook_entries: list[HookEntry] = []
        self.current_hook_entry: HookEntry | None = None
        self.comment_entries: list[CommentEntry] = []
        self.mentor_entries: list[MentorEntry] = []
        self.current_mentor_entry: MentorEntry | None = None

        # Metadata
        self.line_number = start_idx + 1  # Convert to 1-based line numbering
        self.file_path = file_path

        # Section flags
        self.in_description = False
        self.in_test_targets = False
        self.in_kickstart = False
        self.in_commits = False
        self.in_hooks = False
        self.in_comments = False
        self.in_mentors = False

    def reset_section_flags(self) -> None:
        """Reset all section flags to False."""
        self.in_description = False
        self.in_test_targets = False
        self.in_kickstart = False
        self.in_commits = False
        self.in_hooks = False
        self.in_comments = False
        self.in_mentors = False

    def save_pending_entries(self) -> None:
        """Save any pending entries before switching sections or finalizing."""
        if self.current_commit_entry is not None:
            self.commit_entries.append(build_commit_entry(self.current_commit_entry))
            self.current_commit_entry = None
        if self.current_hook_entry is not None:
            self.hook_entries.append(self.current_hook_entry)
            self.current_hook_entry = None
        if self.current_mentor_entry is not None:
            self.mentor_entries.append(self.current_mentor_entry)
            self.current_mentor_entry = None

    def build_changespec(self) -> ChangeSpec | None:
        """Build ChangeSpec from accumulated state."""
        self.save_pending_entries()

        if self.name and self.status:
            description = "\n".join(self.description_lines).strip()
            kickstart = (
                "\n".join(self.kickstart_lines).strip()
                if self.kickstart_lines
                else None
            )
            return ChangeSpec(
                name=self.name,
                description=description,
                parent=self.parent,
                cl=self.cl,
                status=self.status,
                test_targets=self.test_targets if self.test_targets else None,
                kickstart=kickstart,
                file_path=self.file_path,
                line_number=self.line_number,
                bug=self.bug,
                commits=self.commit_entries if self.commit_entries else None,
                hooks=self.hook_entries if self.hook_entries else None,
                comments=self.comment_entries if self.comment_entries else None,
                mentors=self.mentor_entries if self.mentor_entries else None,
            )
        return None


def _parse_field_header(state: _ParserState, line: str) -> bool:
    """Parse a field header line (NAME:, DESCRIPTION:, etc.).

    Returns True if a field header was parsed, False otherwise.
    """
    if line.startswith("NAME: "):
        # If we already have a name, this is a new ChangeSpec
        if state.name is not None:
            return False  # Signal to stop parsing
        state.name = line[6:].strip()
        state.reset_section_flags()
        return True

    if line.startswith("DESCRIPTION:"):
        state.save_pending_entries()
        state.reset_section_flags()
        state.in_description = True
        # Check if description is on the same line
        desc_inline = line[12:].strip()
        if desc_inline:
            state.description_lines.append(desc_inline)
        return True

    if line.startswith("KICKSTART:"):
        state.save_pending_entries()
        state.reset_section_flags()
        state.in_kickstart = True
        # Check if kickstart is on the same line
        kickstart_inline = line[10:].strip()
        if kickstart_inline:
            state.kickstart_lines.append(kickstart_inline)
        return True

    if line.startswith("PARENT: "):
        state.save_pending_entries()
        state.parent = line[8:].strip()
        state.reset_section_flags()
        return True

    if line.startswith("CL: "):
        state.save_pending_entries()
        state.cl = line[4:].strip()
        state.reset_section_flags()
        return True

    if line.startswith("BUG: "):
        state.save_pending_entries()
        state.bug = line[5:].strip()
        state.reset_section_flags()
        return True

    if line.startswith("STATUS: "):
        state.save_pending_entries()
        state.status = line[8:].strip()
        state.reset_section_flags()
        return True

    return False


def _parse_section_header(state: _ParserState, line: str) -> bool:
    """Parse a section header line (COMMITS:, HOOKS:, etc.).

    Returns True if a section header was parsed, False otherwise.
    """
    if line.startswith("COMMITS:"):
        state.save_pending_entries()
        state.reset_section_flags()
        state.in_commits = True
        return True

    if line.startswith("HOOKS:"):
        state.save_pending_entries()
        state.reset_section_flags()
        state.in_hooks = True
        return True

    if line.startswith("COMMENTS:"):
        state.save_pending_entries()
        state.reset_section_flags()
        state.in_comments = True
        return True

    if line.startswith("MENTORS:"):
        state.save_pending_entries()
        state.reset_section_flags()
        state.in_mentors = True
        return True

    if line.startswith("TEST TARGETS:"):
        state.save_pending_entries()
        state.reset_section_flags()
        state.in_test_targets = True
        # Check if targets are on the same line
        targets_inline = line[13:].strip()
        if targets_inline:
            # Treat as single target (may contain spaces like "target (FAILED)")
            state.test_targets.append(targets_inline)
        return True

    return False


def _parse_section_content(state: _ParserState, line: str) -> None:
    """Parse content within the current section."""
    stripped = line.strip()

    if state.in_hooks:
        state.current_hook_entry, state.hook_entries = parse_hooks_line(
            line, stripped, state.current_hook_entry, state.hook_entries
        )
    elif state.in_comments:
        state.comment_entries = parse_comments_line(
            line, stripped, state.comment_entries
        )
    elif state.in_mentors:
        state.current_mentor_entry, state.mentor_entries = parse_mentors_line(
            line, stripped, state.current_mentor_entry, state.mentor_entries
        )
    elif state.in_commits:
        state.current_commit_entry, state.commit_entries = parse_commits_line(
            line, stripped, state.current_commit_entry, state.commit_entries
        )
    elif state.in_description and line.startswith("  "):
        # Description continuation (2-space indented)
        state.description_lines.append(line[2:].rstrip("\n"))
    elif state.in_kickstart and line.startswith("  "):
        # Kickstart continuation (2-space indented)
        state.kickstart_lines.append(line[2:].rstrip("\n"))
    elif state.in_test_targets and line.startswith("  "):
        # Test targets continuation (2-space indented)
        target = stripped
        if target:
            state.test_targets.append(target)
    elif stripped == "":
        # Blank line - preserve in description or kickstart
        if state.in_description:
            state.description_lines.append("")
        elif state.in_kickstart:
            state.kickstart_lines.append("")
    elif not line.startswith("#"):
        # Any other non-comment content ends the special parsing modes
        state.reset_section_flags()


def _parse_changespec_from_lines(
    lines: list[str], start_idx: int, file_path: str
) -> tuple[ChangeSpec | None, int]:
    """Parse a single ChangeSpec from lines starting at start_idx.

    Returns:
        Tuple of (ChangeSpec or None, next_index_to_process)
    """
    state = _ParserState(start_idx, file_path)
    idx = start_idx
    consecutive_blank_lines = 0

    while idx < len(lines):
        line = lines[idx]

        # Check for end of ChangeSpec (next ChangeSpec header or 2 blank lines)
        if re.match(r"^##\s+ChangeSpec", line.strip()) and idx > start_idx:
            break
        if line.strip() == "":
            consecutive_blank_lines += 1
            # 2 blank lines indicate end of ChangeSpec
            if consecutive_blank_lines >= 2:
                break
        else:
            consecutive_blank_lines = 0

        # Try to parse field headers (NAME:, DESCRIPTION:, etc.)
        if _parse_field_header(state, line):
            idx += 1
            continue

        # Check if we hit a new NAME: when we already have one
        if line.startswith("NAME: ") and state.name is not None:
            state.save_pending_entries()
            # Don't increment idx - let the caller re-process this NAME line
            idx -= 1
            break

        # Try to parse section headers (COMMITS:, HOOKS:, etc.)
        if _parse_section_header(state, line):
            idx += 1
            continue

        # Parse section content
        _parse_section_content(state, line)
        idx += 1

    return state.build_changespec(), idx


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
