"""ChangeSpec parsing implementation."""

import re

from ..display_helpers import is_entry_ref_suffix
from ..hooks.queries import expand_test_target_shorthand
from .models import (
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
    HookStatusLine,
    MentorEntry,
    MentorStatusLine,
)


def _build_commit_entry(entry_dict: dict[str, str | int | None]) -> CommitEntry:
    """Build a CommitEntry from a dict with proper type handling."""
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

    return CommitEntry(
        number=number,
        note=note,
        chat=chat,
        diff=diff,
        proposal_letter=proposal_letter,
        suffix=suffix,
        suffix_type=suffix_type,
    )


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
    commit_entries: list[CommitEntry] = []
    current_commit_entry: dict[str, str | int | None] | None = None
    hook_entries: list[HookEntry] = []
    current_hook_entry: HookEntry | None = None
    comment_entries: list[CommentEntry] = []
    mentor_entries: list[MentorEntry] = []
    current_mentor_entry: MentorEntry | None = None
    line_number = start_idx + 1  # Convert to 1-based line numbering

    in_description = False
    in_test_targets = False
    in_kickstart = False
    in_commits = False
    in_hooks = False
    in_comments = False
    in_mentors = False
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

        # Parse field lines
        if line.startswith("NAME: "):
            # If we already have a name, this is a new ChangeSpec - stop parsing
            if name is not None:
                # Save any pending entries
                if current_commit_entry is not None:
                    commit_entries.append(_build_commit_entry(current_commit_entry))
                if current_hook_entry is not None:
                    hook_entries.append(current_hook_entry)
                if current_mentor_entry is not None:
                    mentor_entries.append(current_mentor_entry)
                # Don't increment idx - let the caller re-process this NAME line
                idx -= 1
                break
            name = line[6:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_commits = False
            in_hooks = False
            in_comments = False
            in_mentors = False
        elif line.startswith("DESCRIPTION:"):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            # Save any pending mentor entry
            if current_mentor_entry is not None:
                mentor_entries.append(current_mentor_entry)
                current_mentor_entry = None
            in_description = True
            in_test_targets = False
            in_kickstart = False
            in_commits = False
            in_hooks = False
            in_comments = False
            in_mentors = False
            # Check if description is on the same line
            desc_inline = line[12:].strip()
            if desc_inline:
                description_lines.append(desc_inline)
        elif line.startswith("KICKSTART:"):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            # Save any pending mentor entry
            if current_mentor_entry is not None:
                mentor_entries.append(current_mentor_entry)
                current_mentor_entry = None
            in_kickstart = True
            in_description = False
            in_test_targets = False
            in_commits = False
            in_hooks = False
            in_comments = False
            in_mentors = False
            # Check if kickstart is on the same line
            kickstart_inline = line[10:].strip()
            if kickstart_inline:
                kickstart_lines.append(kickstart_inline)
        elif line.startswith("PARENT: "):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            # Save any pending mentor entry
            if current_mentor_entry is not None:
                mentor_entries.append(current_mentor_entry)
                current_mentor_entry = None
            parent = line[8:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_commits = False
            in_hooks = False
            in_comments = False
            in_mentors = False
        elif line.startswith("CL: "):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            # Save any pending mentor entry
            if current_mentor_entry is not None:
                mentor_entries.append(current_mentor_entry)
                current_mentor_entry = None
            cl = line[4:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_commits = False
            in_hooks = False
            in_comments = False
            in_mentors = False
        elif line.startswith("STATUS: "):
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            # Save any pending mentor entry
            if current_mentor_entry is not None:
                mentor_entries.append(current_mentor_entry)
                current_mentor_entry = None
            status = line[8:].strip()
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_commits = False
            in_hooks = False
            in_comments = False
            in_mentors = False
        elif line.startswith("COMMITS:"):
            # Save any pending commit entry before starting new field
            if current_commit_entry is not None:
                commit_entries.append(_build_commit_entry(current_commit_entry))
                current_commit_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            # Save any pending mentor entry
            if current_mentor_entry is not None:
                mentor_entries.append(current_mentor_entry)
                current_mentor_entry = None
            in_commits = True
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_hooks = False
            in_comments = False
            in_mentors = False
        elif line.startswith("HOOKS:"):
            # Save any pending commit entry
            if current_commit_entry is not None:
                commit_entries.append(_build_commit_entry(current_commit_entry))
                current_commit_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            # Save any pending mentor entry
            if current_mentor_entry is not None:
                mentor_entries.append(current_mentor_entry)
                current_mentor_entry = None
            in_hooks = True
            in_commits = False
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_comments = False
            in_mentors = False
        elif line.startswith("COMMENTS:"):
            # Save any pending commit entry
            if current_commit_entry is not None:
                commit_entries.append(_build_commit_entry(current_commit_entry))
                current_commit_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            # Save any pending mentor entry
            if current_mentor_entry is not None:
                mentor_entries.append(current_mentor_entry)
                current_mentor_entry = None
            in_comments = True
            in_hooks = False
            in_commits = False
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_mentors = False
        elif line.startswith("MENTORS:"):
            # Save any pending commit entry
            if current_commit_entry is not None:
                commit_entries.append(_build_commit_entry(current_commit_entry))
                current_commit_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            # Save any pending mentor entry
            if current_mentor_entry is not None:
                mentor_entries.append(current_mentor_entry)
                current_mentor_entry = None
            in_mentors = True
            in_hooks = False
            in_commits = False
            in_description = False
            in_test_targets = False
            in_kickstart = False
            in_comments = False
        elif line.startswith("TEST TARGETS:"):
            # Save any pending commit entry
            if current_commit_entry is not None:
                commit_entries.append(_build_commit_entry(current_commit_entry))
                current_commit_entry = None
            # Save any pending hook entry
            if current_hook_entry is not None:
                hook_entries.append(current_hook_entry)
                current_hook_entry = None
            # Save any pending mentor entry
            if current_mentor_entry is not None:
                mentor_entries.append(current_mentor_entry)
                current_mentor_entry = None
            in_test_targets = True
            in_description = False
            in_kickstart = False
            in_commits = False
            in_hooks = False
            in_comments = False
            in_mentors = False
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
                    # Start new hook entry - expand shorthand if needed
                    expanded_command = expand_test_target_shorthand(stripped)
                    current_hook_entry = HookEntry(command=expanded_command)
            elif line.startswith("      | "):
                # This is a status line (6-space + "| " prefixed)
                # Remove the "| " prefix for regex matching
                status_content = stripped[2:]  # Skip "| " prefix
                # Try new format first: (N) [YYmmdd_HHMMSS] STATUS (XmYs) - (SUFFIX)
                new_status_match = re.match(
                    r"^\((\d+[a-z]?)\)\s+\[(\d{6})_(\d{6})\]\s*(RUNNING|PASSED|FAILED|DEAD)"
                    r"(?:\s+\(([^)]+)\))?(?:\s+-\s+\(([^)]+)\))?$",
                    status_content,
                )
                if new_status_match and current_hook_entry is not None:
                    # New format with commit entry ID (e.g., "1", "1a", "2")
                    commit_num = new_status_match.group(1)
                    timestamp = (
                        new_status_match.group(2) + "_" + new_status_match.group(3)
                    )
                    status_val = new_status_match.group(4)
                    duration_val = new_status_match.group(5)
                    suffix_val = new_status_match.group(6)
                    summary_val: str | None = None

                    # Check for compound suffix with " | " delimiter
                    # Format: (SUFFIX | SUMMARY) or (@: SUFFIX | SUMMARY)
                    if suffix_val and " | " in suffix_val:
                        parts = suffix_val.split(" | ", 1)
                        suffix_val = parts[0]
                        summary_val = parts[1] if len(parts) > 1 else None

                    # Strip "!: " or "@: " prefix if present to store just the message
                    suffix_type_val: str | None = None
                    if suffix_val:
                        if suffix_val.startswith("~!:"):
                            suffix_val = suffix_val[3:].strip()
                            suffix_type_val = "rejected_proposal"
                        elif suffix_val.startswith("!:"):
                            suffix_val = suffix_val[2:].strip()
                            suffix_type_val = "error"
                        elif suffix_val.startswith("~@:"):
                            suffix_val = suffix_val[3:].strip()
                            suffix_type_val = "killed_agent"
                        elif suffix_val.startswith("@:"):
                            suffix_val = suffix_val[2:].strip()
                            suffix_type_val = "running_agent"
                        elif suffix_val == "@":
                            suffix_val = ""
                            suffix_type_val = "running_agent"
                        elif suffix_val.startswith("~$:"):
                            suffix_val = suffix_val[3:].strip()
                            suffix_type_val = "killed_process"
                        elif suffix_val.startswith("?$:"):
                            suffix_val = suffix_val[3:].strip()
                            suffix_type_val = "pending_dead_process"
                        elif suffix_val.startswith("$:"):
                            suffix_val = suffix_val[2:].strip()
                            suffix_type_val = "running_process"
                        elif suffix_val.startswith("%:"):
                            suffix_val = suffix_val[2:].strip()
                            suffix_type_val = "summarize_complete"
                        elif suffix_val == "%":
                            suffix_val = ""
                            suffix_type_val = "summarize_complete"
                    status_line = HookStatusLine(
                        commit_entry_num=commit_num,
                        timestamp=timestamp,
                        status=status_val,
                        duration=duration_val,
                        suffix=suffix_val,
                        suffix_type=suffix_type_val,
                        summary=summary_val,
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
                    # Strip "!: ", "~: ", or "@: " prefix if present to store just the message
                    # Note: "~:" is legacy and treated as plain suffix (no prefix)
                    comment_suffix_type: str | None = None
                    if suffix_val:
                        if suffix_val.startswith("~!:"):
                            suffix_val = suffix_val[3:].strip()
                            comment_suffix_type = "rejected_proposal"
                        elif suffix_val.startswith("!:"):
                            suffix_val = suffix_val[2:].strip()
                            comment_suffix_type = "error"
                        elif suffix_val.startswith("~@:"):
                            suffix_val = suffix_val[3:].strip()
                            comment_suffix_type = "killed_agent"
                        elif suffix_val.startswith("~$:"):
                            suffix_val = suffix_val[3:].strip()
                            comment_suffix_type = "killed_process"
                        elif suffix_val.startswith("?$:"):
                            suffix_val = suffix_val[3:].strip()
                            comment_suffix_type = "pending_dead_process"
                        elif suffix_val.startswith("~:"):
                            suffix_val = suffix_val[2:].strip()
                            # Legacy "~:" prefix treated as plain suffix
                        elif suffix_val.startswith("$:"):
                            suffix_val = suffix_val[2:].strip()
                            comment_suffix_type = "running_process"
                        elif suffix_val.startswith("@:"):
                            suffix_val = suffix_val[2:].strip()
                            comment_suffix_type = "running_agent"
                        elif suffix_val == "@":
                            suffix_val = ""
                            comment_suffix_type = "running_agent"
                    comment_entries.append(
                        CommentEntry(
                            reviewer=reviewer,
                            file_path=file_path_val,
                            suffix=suffix_val,
                            suffix_type=comment_suffix_type,
                        )
                    )
        elif in_mentors:
            # Parse MENTORS entries
            # Format:
            #   (<id>) <profile1> [<profile2> ...]
            #       | <profile>:<mentor> - STATUS - (suffix)
            stripped = line.strip()
            if line.startswith("  ") and not line.startswith("      "):
                # This is an entry line (2-space indented, not 6-space)
                # Pattern: (<id>) <profile1>[x/y] [<profile2>[x/y] ...]
                # Or legacy: (<id>) <profile1> [<profile2> ...]
                entry_match = re.match(r"^\((\d+[a-z]?)\)\s+(.+)$", stripped)
                if entry_match:
                    # Save previous entry if exists
                    if current_mentor_entry is not None:
                        mentor_entries.append(current_mentor_entry)
                    # Start new mentor entry
                    entry_id = entry_match.group(1)
                    profiles_raw = entry_match.group(2)
                    # Detect and strip #WIP marker
                    is_wip = profiles_raw.rstrip().endswith("#WIP")
                    if is_wip:
                        profiles_raw = profiles_raw.replace(" #WIP", "").rstrip()
                    # Try new format: profile[x/y] (extract just profile names)
                    profiles = re.findall(r"(\w+)\[\d+/\d+\]", profiles_raw)
                    if not profiles:
                        # Fallback: old format without counts
                        profiles = profiles_raw.split()
                    current_mentor_entry = MentorEntry(
                        entry_id=entry_id,
                        profiles=profiles,
                        status_lines=[],
                        is_wip=is_wip,
                    )
            elif line.startswith("      | "):
                # This is a status line (6-space + "| " prefixed)
                # Pattern: [timestamp] <profile>:<mentor> - STATUS - (suffix)
                # Timestamp is optional for backward compatibility
                status_content = stripped[2:]  # Skip "| " prefix
                mentor_status_match = re.match(
                    r"^(?:\[(\d{6}_\d{6})\]\s+)?([^:]+):(\S+)\s+-\s+(RUNNING|PASSED|FAILED)"
                    r"(?:\s+-\s+\(([^)]+)\))?$",
                    status_content,
                )
                if mentor_status_match and current_mentor_entry is not None:
                    timestamp_val = mentor_status_match.group(1)  # Optional
                    profile_name = mentor_status_match.group(2)
                    mentor_name = mentor_status_match.group(3)
                    status_val = mentor_status_match.group(4)
                    suffix_val = mentor_status_match.group(5)

                    # Parse suffix and suffix_type
                    mentor_suffix_type: str | None = None
                    mentor_duration_val: str | None = None
                    if suffix_val:
                        if suffix_val.startswith("~!:"):
                            suffix_val = suffix_val[3:].strip()
                            mentor_suffix_type = "rejected_proposal"
                        elif suffix_val.startswith("!:"):
                            suffix_val = suffix_val[2:].strip()
                            mentor_suffix_type = "error"
                        elif suffix_val.startswith("@:"):
                            suffix_val = suffix_val[2:].strip()
                            mentor_suffix_type = "running_agent"
                        elif suffix_val == "@":
                            suffix_val = ""
                            mentor_suffix_type = "running_agent"
                        elif is_entry_ref_suffix(suffix_val):
                            # Entry reference suffix (e.g., "2a") - proposal created
                            mentor_suffix_type = "entry_ref"
                            # Keep suffix_val as-is, don't treat as duration
                        else:
                            # Plain suffix - likely a duration
                            mentor_duration_val = suffix_val
                            suffix_val = None
                            mentor_suffix_type = "plain"

                    mentor_status_line = MentorStatusLine(
                        profile_name=profile_name,
                        mentor_name=mentor_name,
                        status=status_val,
                        timestamp=timestamp_val,
                        duration=mentor_duration_val,
                        suffix=suffix_val,
                        suffix_type=mentor_suffix_type,
                    )
                    if current_mentor_entry.status_lines is None:
                        current_mentor_entry.status_lines = []
                    current_mentor_entry.status_lines.append(mentor_status_line)
        elif in_commits:
            # Parse COMMITS entries
            stripped = line.strip()
            # Check for new commit entry: (N) or (Na) Note text
            # Supports both regular entries (N) and proposed entries (Na)
            commit_match = re.match(r"^\((\d+)([a-z])?\)\s+(.+)$", stripped)
            if commit_match:
                # Save previous entry if exists
                if current_commit_entry is not None:
                    commit_entries.append(_build_commit_entry(current_commit_entry))

                raw_note = commit_match.group(3)

                # Check for suffix pattern at end of note:
                # - (!: MSG), - (~!: MSG), - (~: MSG), - (@: MSG), or - (MSG)
                # Note: "~:" is legacy and treated as plain suffix (no prefix)
                suffix_match = re.search(
                    r"\s+-\s+\((~!:|!:|~:|@:)?\s*([^)]+)\)$", raw_note
                )
                if suffix_match:
                    note_without_suffix = raw_note[: suffix_match.start()]
                    prefix = suffix_match.group(1)  # "~!:", "!:", "~:", "@:", or None
                    suffix_msg = suffix_match.group(2).strip()
                    if prefix == "~!:":
                        suffix_type_val = "rejected_proposal"
                    elif prefix == "!:":
                        suffix_type_val = "error"
                    elif prefix == "~:":
                        # Legacy "~:" prefix treated as plain suffix
                        suffix_type_val = None
                    elif prefix == "@:":
                        suffix_type_val = "running_agent"
                    else:
                        suffix_type_val = None
                    # Handle standalone "@" as running_agent marker
                    if suffix_msg == "@":
                        suffix_msg = ""
                        suffix_type_val = "running_agent"
                else:
                    note_without_suffix = raw_note
                    suffix_msg = None
                    suffix_type_val = None

                # Start new entry
                current_commit_entry = {
                    "number": int(commit_match.group(1)),
                    "proposal_letter": commit_match.group(
                        2
                    ),  # None for regular entries
                    "note": note_without_suffix,
                    "chat": None,
                    "diff": None,
                    "suffix": suffix_msg,
                    "suffix_type": suffix_type_val,
                }
            elif stripped.startswith("| CHAT:"):
                if current_commit_entry is not None:
                    current_commit_entry["chat"] = stripped[7:].strip()
            elif stripped.startswith("| DIFF:"):
                if current_commit_entry is not None:
                    current_commit_entry["diff"] = stripped[7:].strip()
            # If line doesn't match commit format, stay in commits mode
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
                in_commits = False
                in_hooks = False
                in_comments = False
                in_mentors = False

        idx += 1

    # Save any pending commit entry
    if current_commit_entry is not None:
        commit_entries.append(_build_commit_entry(current_commit_entry))

    # Save any pending hook entry
    if current_hook_entry is not None:
        hook_entries.append(current_hook_entry)

    # Save any pending mentor entry
    if current_mentor_entry is not None:
        mentor_entries.append(current_mentor_entry)

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
                commits=commit_entries if commit_entries else None,
                hooks=hook_entries if hook_entries else None,
                comments=comment_entries if comment_entries else None,
                mentors=mentor_entries if mentor_entries else None,
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
