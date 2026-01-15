"""Commit entry renumbering and hook status line management for accept workflow."""

import re
from typing import Any

from ace.changespec import changespec_lock, write_changespec_atomic


def _get_entry_id(entry: dict[str, Any]) -> str:
    """Get the entry ID string (e.g., '1', '2a') from an entry dict."""
    num = entry["number"]
    letter = entry.get("letter") or ""
    return f"{num}{letter}"


def _build_entry_id_mapping(
    entries: list[dict[str, Any]],
    new_entries: list[dict[str, Any]],
    accepted_proposals: list[tuple[int, str]],
    next_regular: int,
    remaining_proposals: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, str]]:
    """Build mappings from old entry IDs to new entry IDs.

    When multiple proposals are accepted, only the first proposal's hook status
    lines are promoted to the new entry ID. Other accepted proposals have their
    hook status lines "archived" by appending the new entry ID (e.g., "1a-3").
    This ensures gai loop will run hooks for the new merged commits.

    Args:
        entries: Original entries.
        new_entries: New entries after renumbering.
        accepted_proposals: List of (base_number, letter) tuples that were accepted.
        next_regular: The next regular number assigned to accepted proposals.
        remaining_proposals: Remaining proposals that weren't accepted.

    Returns:
        Tuple of (promote_mapping, archive_mapping):
        - promote_mapping: Maps old entry ID to new entry ID (for first proposal,
          regular entries, remaining proposals, and suffix updates)
        - archive_mapping: Maps old entry ID to archived format (e.g., "1a" -> "1a-3")
          for non-first accepted proposals
    """
    promote_mapping: dict[str, str] = {}
    archive_mapping: dict[str, str] = {}

    # Regular entries keep their IDs
    for entry in entries:
        if entry["letter"] is None:
            old_id = _get_entry_id(entry)
            promote_mapping[old_id] = old_id

    # Accepted proposals - first promoted, others archived
    current_new_num = next_regular - len(accepted_proposals)
    for idx, (base_num, letter) in enumerate(accepted_proposals):
        old_id = f"{base_num}{letter}"
        new_id = str(current_new_num)
        # Always add to promote_mapping (used for suffix updates)
        promote_mapping[old_id] = new_id
        if idx > 0:
            # Non-first proposals: archive with old_id-new_id format
            archive_mapping[old_id] = f"{old_id}-{new_id}"
        current_new_num += 1

    # Remaining proposals keep their original ID unchanged
    for entry in remaining_proposals:
        old_id = _get_entry_id(entry)
        promote_mapping[old_id] = old_id  # Maps to itself

    return promote_mapping, archive_mapping


def _update_hooks_with_id_mapping(
    lines: list[str],
    cl_name: str,
    promote_mapping: dict[str, str],
    archive_mapping: dict[str, str] | None = None,
) -> list[str]:
    """Update hook status lines with new entry IDs based on the mappings.

    For the first accepted proposal, status lines are promoted to the new entry ID.
    For other accepted proposals, status lines are archived by appending the new
    entry ID (e.g., "(1a)" becomes "(1a-3)"). This ensures gai loop will run hooks
    for the new merged commits since no status line exists for those entry IDs.

    Args:
        lines: All lines from the project file.
        cl_name: The CL name.
        promote_mapping: Mapping from old entry IDs to new entry IDs.
        archive_mapping: Mapping from old entry IDs to archived format
            (e.g., "1a" -> "1a-3") for non-first accepted proposals.

    Returns:
        Updated lines with hook status lines renumbered.
    """
    updated_lines: list[str] = []
    in_target_changespec = False
    in_hooks = False

    for line in lines:
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            in_hooks = False
            updated_lines.append(line)
        elif in_target_changespec and line.startswith("HOOKS:"):
            in_hooks = True
            updated_lines.append(line)
        elif in_target_changespec and in_hooks and line.startswith("      | "):
            # This is a status line (6-space + "| " prefixed)
            stripped = line.strip()[2:]  # Skip "| " prefix
            # Match status line format: (N) or (Na) followed by rest
            status_match = re.match(r"^\((\d+[a-z]?)\)(.*)$", stripped)
            if status_match:
                old_id = status_match.group(1)
                rest = status_match.group(2)
                # Update any proposal ID suffix (e.g., "- (1a)" -> "- (2)")
                # Also handles new format with summary: "- (1a | summary)" -> "- (2 | summary)"
                # Suffixes always use promote_mapping (the new entry ID)
                suffix_match = re.search(r" - \((\d+[a-z])(\s*\|[^)]+)?\)$", rest)
                if suffix_match:
                    old_suffix_id = suffix_match.group(1)
                    summary_part = suffix_match.group(2) or ""
                    new_suffix_id = promote_mapping.get(old_suffix_id, old_suffix_id)
                    rest = re.sub(
                        r" - \(\d+[a-z](?:\s*\|[^)]+)?\)$",
                        f" - ({new_suffix_id}{summary_part})",
                        rest,
                    )
                # Check if this entry should be archived or promoted
                if archive_mapping and old_id in archive_mapping:
                    # Archive: (1a) -> (1a-3)
                    archived_id = archive_mapping[old_id]
                    updated_lines.append(f"      | ({archived_id}){rest}\n")
                else:
                    # Promote: map to new ID if in mapping, otherwise keep original
                    new_id = promote_mapping.get(old_id, old_id)
                    updated_lines.append(f"      | ({new_id}){rest}\n")
            else:
                updated_lines.append(line)
        elif in_target_changespec and in_hooks:
            # Check if still in hooks section
            if line.startswith("  ") and not line.startswith("    "):
                # Command line (2-space indented, not 4-space) - still in hooks
                updated_lines.append(line)
            elif line.strip() == "":
                # Blank line - might end hooks section
                in_hooks = False
                updated_lines.append(line)
            else:
                # End of hooks section
                in_hooks = False
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    return updated_lines


def _update_mentors_with_id_mapping(
    lines: list[str],
    cl_name: str,
    promote_mapping: dict[str, str],
) -> list[str]:
    """Update MENTORS entry_ref suffixes with new entry IDs based on the mapping.

    This updates entry_ref suffixes in mentor status lines when proposals are
    accepted and renumbered. For example, if a mentor has suffix "(2a)" and
    proposal 2a becomes entry 3, the suffix is updated to "(3)".

    Args:
        lines: All lines from the project file.
        cl_name: The CL name.
        promote_mapping: Mapping from old entry IDs to new entry IDs.

    Returns:
        Updated lines with mentor entry_ref suffixes renumbered.
    """
    updated_lines: list[str] = []
    in_target_changespec = False
    in_mentors = False

    for line in lines:
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            in_mentors = False
            updated_lines.append(line)
        elif in_target_changespec and line.startswith("MENTORS:"):
            in_mentors = True
            updated_lines.append(line)
        elif in_target_changespec and in_mentors and line.startswith("      | "):
            # This is a status line (6-space + "| " prefixed)
            # Format: | profile:mentor - STATUS - (suffix)
            # We need to update entry_ref suffixes like (2a) -> (3)
            suffix_match = re.search(r" - \((\d+[a-z])\)$", line)
            if suffix_match:
                old_suffix_id = suffix_match.group(1)
                new_suffix_id = promote_mapping.get(old_suffix_id, old_suffix_id)
                updated_line = re.sub(
                    r" - \(\d+[a-z]\)$",
                    f" - ({new_suffix_id})",
                    line,
                )
                updated_lines.append(updated_line)
            else:
                updated_lines.append(line)
        elif in_target_changespec and in_mentors:
            # Check if still in mentors section
            if line.startswith("  ") and line.strip().startswith("("):
                # Entry header line (2-space indented, starts with "(") - still in mentors
                updated_lines.append(line)
            elif line.strip() == "":
                # Blank line - might end mentors section
                in_mentors = False
                updated_lines.append(line)
            else:
                # End of mentors section
                in_mentors = False
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    return updated_lines


def _update_comments_with_id_mapping(
    lines: list[str],
    cl_name: str,
    promote_mapping: dict[str, str],
) -> list[str]:
    """Update COMMENTS entry_ref suffixes with new entry IDs based on the mapping.

    This updates entry_ref suffixes in COMMENTS entries when proposals are
    accepted and renumbered. For example, if a comment has suffix "(2c)" and
    proposal 2c becomes entry 3, the suffix is updated to "(3)".

    Args:
        lines: All lines from the project file.
        cl_name: The CL name.
        promote_mapping: Mapping from old entry IDs to new entry IDs.

    Returns:
        Updated lines with comment entry_ref suffixes renumbered.
    """
    updated_lines: list[str] = []
    in_target_changespec = False
    in_comments = False

    for line in lines:
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            in_comments = False
            updated_lines.append(line)
        elif in_target_changespec and line.startswith("COMMENTS:"):
            in_comments = True
            updated_lines.append(line)
        elif in_target_changespec and in_comments:
            # Check if still in comments section (2-space indented, starts with [)
            if line.startswith("  ["):
                # This is a comment entry line
                # Format: [reviewer] path - (suffix)
                # We need to update entry_ref suffixes like (2a) -> (3)
                suffix_match = re.search(r" - \((\d+[a-z])\)$", line)
                if suffix_match:
                    old_suffix_id = suffix_match.group(1)
                    new_suffix_id = promote_mapping.get(old_suffix_id, old_suffix_id)
                    updated_line = re.sub(
                        r" - \(\d+[a-z]\)$",
                        f" - ({new_suffix_id})",
                        line,
                    )
                    updated_lines.append(updated_line)
                else:
                    updated_lines.append(line)
            else:
                # End of comments section
                in_comments = False
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    return updated_lines


def _reject_remaining_proposals_unlocked(
    lines: list[str],
    cl_name: str,
) -> list[str]:
    """Reject remaining proposals by changing (!: NEW PROPOSAL) to (~!: NEW PROPOSAL).

    This is an unlocked version that operates on in-memory lines.
    Must be called while holding the changespec lock.

    Args:
        lines: All lines from the project file.
        cl_name: The CL name.

    Returns:
        Updated lines with remaining proposals rejected.
    """
    updated_lines: list[str] = []
    in_target_changespec = False
    in_commits = False

    for line in lines:
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            in_commits = False
            updated_lines.append(line)
        elif in_target_changespec:
            if line.startswith("COMMITS:"):
                in_commits = True
                updated_lines.append(line)
            elif line.startswith(
                (
                    "NAME:",
                    "DESCRIPTION:",
                    "PARENT:",
                    "CL:",
                    "STATUS:",
                    "TEST TARGETS:",
                    "KICKSTART:",
                    "HOOKS:",
                    "COMMENTS:",
                    "MENTORS:",
                )
            ):
                in_commits = False
                if line.startswith("NAME:"):
                    in_target_changespec = False
                updated_lines.append(line)
            elif in_commits:
                stripped = line.strip()
                # Match: (Na) Note text - (!: NEW PROPOSAL)
                entry_match = re.match(
                    r"^\((\d+[a-z])\)\s+(.+?)\s+-\s+\(!:\s*NEW PROPOSAL\)$",
                    stripped,
                )
                if entry_match:
                    matched_id = entry_match.group(1)
                    note_text = entry_match.group(2)
                    # Preserve leading whitespace
                    leading_ws = line[: len(line) - len(line.lstrip())]
                    # Change (!: NEW PROPOSAL) to (~!: NEW PROPOSAL)
                    new_line = (
                        f"{leading_ws}({matched_id}) {note_text} - (~!: NEW PROPOSAL)\n"
                    )
                    updated_lines.append(new_line)
                else:
                    updated_lines.append(line)
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    return updated_lines


def _add_ready_to_mail_suffix_unlocked(
    lines: list[str],
    cl_name: str,
) -> list[str]:
    """Add the READY TO MAIL suffix to a ChangeSpec's STATUS line.

    This is an unlocked version that operates on in-memory lines.
    Must be called while holding the changespec lock.

    Args:
        lines: All lines from the project file.
        cl_name: The CL name.

    Returns:
        Updated lines with READY TO MAIL suffix added to STATUS.
    """
    ready_to_mail_suffix = " - (!: READY TO MAIL)"
    updated_lines: list[str] = []
    in_target_changespec = False

    for line in lines:
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            updated_lines.append(line)
        elif in_target_changespec and line.startswith("STATUS:"):
            # Get current status value
            current_status = line.split(":", 1)[1].strip()
            # Only add suffix if not already present
            if "(!: READY TO MAIL)" not in current_status:
                new_status = current_status + ready_to_mail_suffix
                updated_lines.append(f"STATUS: {new_status}\n")
            else:
                updated_lines.append(line)
            in_target_changespec = False  # Done updating this ChangeSpec
        else:
            updated_lines.append(line)

    return updated_lines


def _sort_hook_status_lines(lines: list[str], cl_name: str) -> list[str]:
    """Sort hook status lines by entry ID within each hook.

    Handles both regular format (1), (1a) and archive format (1a-3).
    Archive format entries are sorted by their original base+letter, so
    (1a-3) sorts before (1b) and (2).

    Args:
        lines: All lines from the project file.
        cl_name: The CL name.

    Returns:
        Lines with hook status lines sorted by entry ID.
    """
    updated_lines: list[str] = []
    in_target_changespec = False
    in_hooks = False
    current_status_lines: list[tuple[str, int, str]] = []  # (line, num, letter)

    def flush_status_lines() -> None:
        """Sort and flush accumulated status lines."""
        nonlocal current_status_lines
        if current_status_lines:
            # Sort by (number, letter)
            current_status_lines.sort(key=lambda x: (x[1], x[2]))
            for line_content, _, _ in current_status_lines:
                updated_lines.append(line_content)
            current_status_lines = []

    for line in lines:
        if line.startswith("NAME: "):
            flush_status_lines()
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            in_hooks = False
            updated_lines.append(line)
        elif in_target_changespec and line.startswith("HOOKS:"):
            flush_status_lines()
            in_hooks = True
            updated_lines.append(line)
        elif in_target_changespec and in_hooks and line.startswith("      | "):
            # Status line - accumulate for sorting
            stripped = line.strip()[2:]  # Skip "| " prefix
            # Match: (1), (1a), or (1a-3) format (archive suffix ignored for sorting)
            status_match = re.match(r"^\((\d+)([a-z]?)(?:-\d+)?\)", stripped)
            if status_match:
                num = int(status_match.group(1))
                letter = status_match.group(2) or ""
                current_status_lines.append((line, num, letter))
            else:
                flush_status_lines()
                updated_lines.append(line)
        elif in_target_changespec and in_hooks and line.startswith("  "):
            # New hook command line
            flush_status_lines()
            updated_lines.append(line)
        elif in_target_changespec and in_hooks:
            # End of hooks section
            flush_status_lines()
            in_hooks = False
            updated_lines.append(line)
        else:
            flush_status_lines()
            updated_lines.append(line)

    # Flush any remaining status lines
    flush_status_lines()

    return updated_lines


def renumber_commit_entries(
    project_file: str,
    cl_name: str,
    accepted_proposals: list[tuple[int, str]],
    extra_msgs: list[str | None] | None = None,
    mark_ready_to_mail: bool = False,
) -> bool:
    """Renumber commit entries after accepting proposals.

    Accepted proposals become the next regular numbers.
    Remaining proposals are renumbered to lowest available letters.
    Hook status lines are also updated to reference the new entry IDs.
    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name.
        accepted_proposals: List of (base_number, letter) tuples that were accepted,
            in the order they should become regular entries.
        extra_msgs: Optional list of messages to append to each accepted entry's note.
            Must be same length as accepted_proposals if provided.
        mark_ready_to_mail: If True, also reject remaining proposals and add
            READY TO MAIL suffix to STATUS, all in the same atomic write.

    Returns:
        True if successful, False otherwise.
    """
    try:
        with changespec_lock(project_file):
            with open(project_file, encoding="utf-8") as f:
                lines = f.readlines()

            # Find the ChangeSpec and its commits section
            in_target_changespec = False
            commits_start = -1
            commits_end = -1

            for i, line in enumerate(lines):
                if line.startswith("NAME: "):
                    current_name = line[6:].strip()
                    if in_target_changespec:
                        # We hit the next ChangeSpec
                        if commits_end < 0:
                            commits_end = i
                        break
                    in_target_changespec = current_name == cl_name
                elif in_target_changespec:
                    if line.startswith("COMMITS:"):
                        commits_start = i
                    elif commits_start >= 0:
                        stripped = line.strip()
                        # Check if still in COMMITS section
                        if re.match(r"^\(\d+[a-z]?\)", stripped) or stripped.startswith(
                            "| "
                        ):
                            commits_end = i + 1  # Track last commit line
                        elif stripped and not stripped.startswith("#"):
                            # Non-commit content
                            break

            if commits_start < 0:
                return False  # No COMMITS section found

            if commits_end < 0:
                commits_end = len(lines)

            # Parse current commit entries
            commit_lines = lines[commits_start + 1 : commits_end]
            entries: list[dict[str, Any]] = []
            current_entry: dict[str, Any] | None = None

            for line in commit_lines:
                stripped = line.strip()
                # Match commit entry: (N) or (Na) Note text
                entry_match = re.match(r"^\((\d+)([a-z])?\)\s+(.+)$", stripped)
                if entry_match:
                    if current_entry:
                        entries.append(current_entry)
                    current_entry = {
                        "number": int(entry_match.group(1)),
                        "letter": entry_match.group(2),
                        "note": entry_match.group(3),
                        "chat": None,
                        "diff": None,
                        "raw_lines": [line],
                    }
                elif stripped.startswith("| CHAT:") and current_entry:
                    current_entry["chat"] = stripped[7:].strip()
                    current_entry["raw_lines"].append(line)  # type: ignore[union-attr]
                elif stripped.startswith("| DIFF:") and current_entry:
                    current_entry["diff"] = stripped[7:].strip()
                    current_entry["raw_lines"].append(line)  # type: ignore[union-attr]
                elif current_entry and stripped == "":
                    # Blank line within commits section
                    pass

            if current_entry:
                entries.append(current_entry)

            # Find max regular (non-proposal) number
            max_regular = 0
            for entry in entries:
                if entry["letter"] is None:
                    max_regular = max(max_regular, int(entry["number"]))  # type: ignore[arg-type]

            # Determine new numbers for accepted proposals
            # They become next regular numbers in the order they were accepted
            next_regular = max_regular + 1
            accepted_set = set(accepted_proposals)

            # Group remaining proposals by base number
            remaining_proposals: list[dict[str, Any]] = []
            for entry in entries:
                if entry["letter"] is not None:
                    key = (int(entry["number"]), str(entry["letter"]))
                    if key not in accepted_set:
                        remaining_proposals.append(entry)

            # Build new entries list
            new_entries: list[dict[str, Any]] = []

            # First, add all regular (non-proposal) entries unchanged
            for entry in entries:
                if entry["letter"] is None:
                    new_entries.append(entry)

            # Add accepted proposals as new regular entries in acceptance order
            for idx, (base_num, letter) in enumerate(accepted_proposals):
                for entry in entries:
                    if entry["number"] == base_num and entry["letter"] == letter:
                        new_entry = entry.copy()
                        new_entry["number"] = next_regular
                        new_entry["letter"] = None
                        # Strip any proposal suffix (e.g., "- (!: NEW PROPOSAL)")
                        new_entry["note"] = re.sub(
                            r" - \([!~]: [^)]+\)$", "", entry["note"]
                        )
                        # Append per-proposal message to the note if provided
                        if extra_msgs and idx < len(extra_msgs) and extra_msgs[idx]:
                            new_entry["note"] = (
                                f"{new_entry['note']} - {extra_msgs[idx]}"
                            )
                        new_entries.append(new_entry)
                        next_regular += 1
                        break

            # Add remaining proposals unchanged (keep original ID)
            for entry in remaining_proposals:
                new_entries.append(entry.copy())

            # Build ID mappings for hook status line updates
            promote_mapping, archive_mapping = _build_entry_id_mapping(
                entries,
                new_entries,
                accepted_proposals,
                next_regular,
                remaining_proposals,
            )

            # Sort entries: regular entries by number, then proposals by base+letter
            def sort_key(e: dict[str, Any]) -> tuple[int, str]:
                num = int(e["number"]) if e["number"] is not None else 0
                letter = str(e["letter"]) if e["letter"] else ""
                return (num, letter)

            new_entries.sort(key=sort_key)

            # Rebuild commits section
            new_commit_lines = ["COMMITS:\n"]
            for entry in new_entries:
                num = entry["number"]
                letter = str(entry["letter"]) if entry["letter"] else ""
                note = entry["note"]
                new_commit_lines.append(f"  ({num}{letter}) {note}\n")
                if entry["chat"]:
                    new_commit_lines.append(f"      | CHAT: {entry['chat']}\n")
                if entry["diff"]:
                    new_commit_lines.append(f"      | DIFF: {entry['diff']}\n")

            # Replace old commits section with new one
            new_lines = lines[:commits_start] + new_commit_lines + lines[commits_end:]

            # Update hook status lines with new entry IDs
            new_lines = _update_hooks_with_id_mapping(
                new_lines, cl_name, promote_mapping, archive_mapping
            )

            # Update mentor entry_ref suffixes with new entry IDs
            new_lines = _update_mentors_with_id_mapping(
                new_lines, cl_name, promote_mapping
            )

            # Update comment entry_ref suffixes with new entry IDs
            new_lines = _update_comments_with_id_mapping(
                new_lines, cl_name, promote_mapping
            )

            # Sort hook status lines by entry ID
            new_lines = _sort_hook_status_lines(new_lines, cl_name)

            # If mark_ready_to_mail is True, also reject remaining proposals
            # and add READY TO MAIL suffix (all in this same atomic write)
            if mark_ready_to_mail:
                new_lines = _reject_remaining_proposals_unlocked(new_lines, cl_name)
                new_lines = _add_ready_to_mail_suffix_unlocked(new_lines, cl_name)

            # Write atomically
            commit_msg = f"Renumber commit entries for {cl_name}"
            if mark_ready_to_mail:
                commit_msg += " and mark ready to mail"
            write_changespec_atomic(
                project_file,
                "".join(new_lines),
                commit_msg,
            )
            return True
    except Exception:
        return False
