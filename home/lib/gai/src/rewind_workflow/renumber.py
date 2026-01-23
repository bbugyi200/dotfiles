"""Commit entry renumbering for rewind workflow."""

import re
from typing import Any

from ace.changespec import changespec_lock, write_changespec_atomic


def _get_entry_id(entry: dict[str, Any]) -> str:
    """Get the entry ID string (e.g., '1', '2a') from an entry dict."""
    num = entry["number"]
    letter = entry.get("letter") or ""
    return f"{num}{letter}"


def _get_lowest_available_letter(
    base_num: int,
    existing_letters: set[str],
) -> str:
    """Get the lowest available proposal letter for a base number.

    Args:
        base_num: The base number for proposals.
        existing_letters: Set of already-used letters.

    Returns:
        The lowest available letter (a-z).
    """
    for letter in "abcdefghijklmnopqrstuvwxyz":
        if letter not in existing_letters:
            return letter
    raise ValueError("No available proposal letters (a-z all used)")


def _update_hooks_with_id_mapping(
    lines: list[str],
    cl_name: str,
    id_mapping: dict[str, str | None],
) -> list[str]:
    """Update hook status lines with new entry IDs based on the mapping.

    Entries mapped to None are deleted.

    Args:
        lines: All lines from the project file.
        cl_name: The CL name.
        id_mapping: Mapping from old entry IDs to new entry IDs (or None for deletion).

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
            # Match status line format: (N) or (Na) or (Na-M) followed by rest
            status_match = re.match(r"^\((\d+[a-z]?)(?:-\d+)?\)(.*)$", stripped)
            if status_match:
                old_id = status_match.group(1)
                rest = status_match.group(2)

                # Check if this entry should be deleted
                if old_id in id_mapping and id_mapping[old_id] is None:
                    # Skip this line (delete it)
                    continue

                # Update any proposal ID suffix (e.g., "- (1a)" -> "- (2)")
                suffix_match = re.search(r" - \((\d+[a-z])(\s*\|[^)]+)?\)$", rest)
                if suffix_match:
                    old_suffix_id = suffix_match.group(1)
                    summary_part = suffix_match.group(2) or ""
                    new_suffix_id = id_mapping.get(old_suffix_id)
                    if new_suffix_id is None:
                        # Suffix entry is being deleted, remove the suffix
                        rest = re.sub(r" - \(\d+[a-z](?:\s*\|[^)]+)?\)$", "", rest)
                    elif new_suffix_id != old_suffix_id:
                        rest = re.sub(
                            r" - \(\d+[a-z](?:\s*\|[^)]+)?\)$",
                            f" - ({new_suffix_id}{summary_part})",
                            rest,
                        )

                # Map the entry ID
                new_id = id_mapping.get(old_id, old_id)
                if new_id is not None:
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
    id_mapping: dict[str, str | None],
) -> list[str]:
    """Update MENTORS entry IDs and suffixes based on the mapping.

    Entries mapped to None are deleted.

    Args:
        lines: All lines from the project file.
        cl_name: The CL name.
        id_mapping: Mapping from old entry IDs to new entry IDs (or None for deletion).

    Returns:
        Updated lines with mentor entries renumbered.
    """
    updated_lines: list[str] = []
    in_target_changespec = False
    in_mentors = False
    skip_status_lines = (
        False  # Track if we're skipping status lines for a deleted entry
    )

    for line in lines:
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            in_mentors = False
            skip_status_lines = False
            updated_lines.append(line)
        elif in_target_changespec and line.startswith("MENTORS:"):
            in_mentors = True
            skip_status_lines = False
            updated_lines.append(line)
        elif in_target_changespec and in_mentors:
            # Check if this is an entry header line: (N) profile1 [profile2 ...]
            entry_match = re.match(r"^  \((\d+[a-z]?)\)\s+(.*)$", line)
            if entry_match:
                old_id = entry_match.group(1)
                rest = entry_match.group(2)
                new_id = id_mapping.get(old_id, old_id)
                if new_id is None:
                    # Delete this entry and its status lines
                    skip_status_lines = True
                    continue
                else:
                    skip_status_lines = False
                    if new_id != old_id:
                        updated_lines.append(f"  ({new_id}) {rest}\n")
                    else:
                        updated_lines.append(line)
            elif skip_status_lines and line.startswith("      | "):
                # Skip status lines for deleted entries
                continue
            elif line.startswith("      | "):
                # Status line - check for entry_ref suffix
                suffix_match = re.search(r" - \((\d+[a-z])\)$", line)
                if suffix_match:
                    old_suffix_id = suffix_match.group(1)
                    new_suffix_id = id_mapping.get(old_suffix_id)
                    if new_suffix_id is None:
                        # Suffix entry is being deleted, remove the suffix
                        updated_line = re.sub(r" - \(\d+[a-z]\)$", "", line)
                        updated_lines.append(updated_line)
                    elif new_suffix_id != old_suffix_id:
                        updated_line = re.sub(
                            r" - \(\d+[a-z]\)$",
                            f" - ({new_suffix_id})",
                            line,
                        )
                        updated_lines.append(updated_line)
                    else:
                        updated_lines.append(line)
                else:
                    updated_lines.append(line)
            elif line.strip() == "":
                # Blank line - might end mentors section
                in_mentors = False
                skip_status_lines = False
                updated_lines.append(line)
            else:
                # End of mentors section
                in_mentors = False
                skip_status_lines = False
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    return updated_lines


def _update_comments_with_id_mapping(
    lines: list[str],
    cl_name: str,
    id_mapping: dict[str, str | None],
) -> list[str]:
    """Update COMMENTS entry_ref suffixes based on the mapping.

    Args:
        lines: All lines from the project file.
        cl_name: The CL name.
        id_mapping: Mapping from old entry IDs to new entry IDs (or None for deletion).

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
            if line.startswith("  ["):
                # Comment entry line - check for entry_ref suffix
                suffix_match = re.search(r" - \((\d+[a-z])\)$", line)
                if suffix_match:
                    old_suffix_id = suffix_match.group(1)
                    new_suffix_id = id_mapping.get(old_suffix_id)
                    if new_suffix_id is None:
                        # Suffix entry is being deleted, remove the suffix
                        updated_line = re.sub(r" - \(\d+[a-z]\)$", "", line)
                        updated_lines.append(updated_line)
                    elif new_suffix_id != old_suffix_id:
                        updated_line = re.sub(
                            r" - \(\d+[a-z]\)$",
                            f" - ({new_suffix_id})",
                            line,
                        )
                        updated_lines.append(updated_line)
                    else:
                        updated_lines.append(line)
                else:
                    updated_lines.append(line)
            else:
                # End of comments section
                in_comments = False
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    return updated_lines


def _sort_entries_by_id(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort entries by number, then by letter.

    Args:
        entries: List of entry dicts.

    Returns:
        Sorted list of entries.
    """

    def sort_key(e: dict[str, Any]) -> tuple[int, str]:
        num = int(e["number"]) if e["number"] is not None else 0
        letter = str(e["letter"]) if e["letter"] else ""
        return (num, letter)

    return sorted(entries, key=sort_key)


def _sort_hook_status_lines(lines: list[str], cl_name: str) -> list[str]:
    """Sort hook status lines by entry ID within each hook.

    Args:
        lines: All lines from the project file.
        cl_name: The CL name.

    Returns:
        Lines with hook status lines sorted by entry ID.
    """
    updated_lines: list[str] = []
    in_target_changespec = False
    in_hooks = False
    current_status_lines: list[tuple[str, int, str]] = []

    def flush_status_lines() -> None:
        nonlocal current_status_lines
        if current_status_lines:
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
            stripped = line.strip()[2:]
            status_match = re.match(r"^\((\d+)([a-z]?)(?:-\d+)?\)", stripped)
            if status_match:
                num = int(status_match.group(1))
                letter = status_match.group(2) or ""
                current_status_lines.append((line, num, letter))
            else:
                flush_status_lines()
                updated_lines.append(line)
        elif in_target_changespec and in_hooks and line.startswith("  "):
            flush_status_lines()
            updated_lines.append(line)
        elif in_target_changespec and in_hooks:
            flush_status_lines()
            in_hooks = False
            updated_lines.append(line)
        else:
            flush_status_lines()
            updated_lines.append(line)

    flush_status_lines()
    return updated_lines


def rewind_commit_entries(
    project_file: str,
    cl_name: str,
    selected_entry_num: int,
) -> bool:
    """Update ChangeSpec after rewinding to a previous entry.

    The renumbering logic:
    1. Keep entries 1...(selected-1) as accepted entries
    2. Delete ALL entries after "entry after selected" (entries selected+2, selected+3, ...)
    3. Convert entry (selected+1) to proposal with lowest available letter
    4. Keep existing proposals for base=selected, convert them to base=(selected-1)
    5. Convert selected entry to proposal with next available letter
    6. Update all references in HOOKS/MENTORS/COMMENTS

    Example: Entries (1), (2), (3), (3a), (3b), (4), (5), (6), rewind to (3):
    - Keep (1), (2) as accepted
    - Delete (5), (6) - entries after "entry after" (4)
    - Convert (4) to (2a) - entry after becomes lowest letter proposal
    - Convert (3a), (3b) to (2b), (2c) - existing proposals
    - Convert (3) to (2d) - selected entry becomes proposal

    Result: (1), (2), (2a)[was 4], (2b)[was 3a], (2c)[was 3b], (2d)[was 3]

    Args:
        project_file: Path to the project file.
        cl_name: The CL name.
        selected_entry_num: The entry number being rewound to.

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
                        if commits_end < 0:
                            commits_end = i
                        break
                    in_target_changespec = current_name == cl_name
                elif in_target_changespec:
                    if line.startswith("COMMITS:"):
                        commits_start = i
                    elif commits_start >= 0:
                        stripped = line.strip()
                        if re.match(r"^\(\d+[a-z]?\)", stripped) or stripped.startswith(
                            "| "
                        ):
                            commits_end = i + 1
                        elif stripped and not stripped.startswith("#"):
                            break

            if commits_start < 0:
                return False

            if commits_end < 0:
                commits_end = len(lines)

            # Parse current commit entries
            commit_lines = lines[commits_start + 1 : commits_end]
            entries: list[dict[str, Any]] = []
            current_entry: dict[str, Any] | None = None

            for line in commit_lines:
                stripped = line.strip()
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
                    }
                elif stripped.startswith("| CHAT:") and current_entry:
                    current_entry["chat"] = stripped[7:].strip()
                elif stripped.startswith("| DIFF:") and current_entry:
                    current_entry["diff"] = stripped[7:].strip()

            if current_entry:
                entries.append(current_entry)

            # Calculate base number for new proposals
            base_num = selected_entry_num - 1

            # Separate entries into categories
            numeric_entries = [e for e in entries if e["letter"] is None]
            proposal_entries = [e for e in entries if e["letter"] is not None]

            # Find entries to keep, convert, and delete
            entries_to_keep = [
                e for e in numeric_entries if e["number"] < selected_entry_num
            ]
            entry_after = next(
                (e for e in numeric_entries if e["number"] == selected_entry_num + 1),
                None,
            )
            selected_entry = next(
                (e for e in numeric_entries if e["number"] == selected_entry_num),
                None,
            )
            entries_to_delete = [
                e for e in numeric_entries if e["number"] > selected_entry_num + 1
            ]
            existing_proposals = [
                e for e in proposal_entries if e["number"] == selected_entry_num
            ]

            if not entry_after or not selected_entry:
                return False

            # Build ID mapping
            id_mapping: dict[str, str | None] = {}

            # Entries to keep - no change
            for e in entries_to_keep:
                old_id = _get_entry_id(e)
                id_mapping[old_id] = old_id

            # Entries to delete - map to None
            for e in entries_to_delete:
                old_id = _get_entry_id(e)
                id_mapping[old_id] = None

            # Track used letters for the new base
            used_letters: set[str] = set()

            # Entry after -> lowest letter proposal
            entry_after_new_letter = _get_lowest_available_letter(
                base_num, used_letters
            )
            used_letters.add(entry_after_new_letter)
            old_id = _get_entry_id(entry_after)
            new_id = f"{base_num}{entry_after_new_letter}"
            id_mapping[old_id] = new_id

            # Existing proposals -> next available letters
            for e in sorted(existing_proposals, key=lambda x: x["letter"] or ""):
                new_letter = _get_lowest_available_letter(base_num, used_letters)
                used_letters.add(new_letter)
                old_id = _get_entry_id(e)
                new_id = f"{base_num}{new_letter}"
                id_mapping[old_id] = new_id

            # Selected entry -> next available letter
            selected_new_letter = _get_lowest_available_letter(base_num, used_letters)
            used_letters.add(selected_new_letter)
            old_id = _get_entry_id(selected_entry)
            new_id = f"{base_num}{selected_new_letter}"
            id_mapping[old_id] = new_id

            # Build new entries list
            new_entries: list[dict[str, Any]] = []

            # Keep entries before selected
            for e in entries_to_keep:
                new_entries.append(e.copy())

            # Entry after -> proposal
            new_entry = entry_after.copy()
            new_entry["number"] = base_num
            new_entry["letter"] = entry_after_new_letter
            # Strip any existing suffix
            new_entry["note"] = re.sub(
                r" - \([!~@$%?]: [^)]+\)$", "", new_entry["note"]
            )
            # Add NEW PROPOSAL suffix
            new_entry["note"] = f"{new_entry['note']} - (!: NEW PROPOSAL)"
            new_entries.append(new_entry)

            # Existing proposals -> renumbered proposals
            for e in sorted(existing_proposals, key=lambda x: x["letter"] or ""):
                new_entry = e.copy()
                new_entry["number"] = base_num
                old_id = _get_entry_id(e)
                mapped_id = id_mapping.get(old_id)
                # Extract the letter from the mapped ID (e.g., "2b" -> "b")
                if mapped_id and len(mapped_id) > 1:
                    new_entry["letter"] = mapped_id[-1]
                else:
                    new_entry["letter"] = e["letter"]
                new_entries.append(new_entry)

            # Selected entry -> proposal
            new_entry = selected_entry.copy()
            new_entry["number"] = base_num
            new_entry["letter"] = selected_new_letter
            # Strip any existing suffix
            new_entry["note"] = re.sub(
                r" - \([!~@$%?]: [^)]+\)$", "", new_entry["note"]
            )
            # Add NEW PROPOSAL suffix
            new_entry["note"] = f"{new_entry['note']} - (!: NEW PROPOSAL)"
            new_entries.append(new_entry)

            # Sort entries
            new_entries = _sort_entries_by_id(new_entries)

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

            # Update hooks, mentors, comments with ID mapping
            new_lines = _update_hooks_with_id_mapping(new_lines, cl_name, id_mapping)
            new_lines = _update_mentors_with_id_mapping(new_lines, cl_name, id_mapping)
            new_lines = _update_comments_with_id_mapping(new_lines, cl_name, id_mapping)

            # Sort hook status lines
            new_lines = _sort_hook_status_lines(new_lines, cl_name)

            # Write atomically
            commit_msg = f"Rewind {cl_name} to entry ({selected_entry_num})"
            write_changespec_atomic(
                project_file,
                "".join(new_lines),
                commit_msg,
            )
            return True

    except Exception:
        return False
