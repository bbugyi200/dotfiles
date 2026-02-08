"""Shared utilities for commit entry renumbering across workflow modules."""

import re
from typing import Any


def sort_hook_status_lines(lines: list[str], cl_name: str) -> list[str]:
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


def build_commits_section(entries: list[dict[str, Any]]) -> list[str]:
    """Build the COMMITS section lines from a list of entry dicts.

    Args:
        entries: List of entry dicts with keys: number, letter, note, chat, diff.

    Returns:
        List of lines including the "COMMITS:" header.
    """
    new_commit_lines = ["COMMITS:\n"]
    for entry in entries:
        num = entry["number"]
        letter = str(entry["letter"]) if entry["letter"] else ""
        note = entry["note"]
        new_commit_lines.append(f"  ({num}{letter}) {note}\n")
        if entry["chat"]:
            new_commit_lines.append(f"      | CHAT: {entry['chat']}\n")
        if entry["diff"]:
            new_commit_lines.append(f"      | DIFF: {entry['diff']}\n")
    return new_commit_lines


def sort_entries_by_id(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort entries by number, then by letter.

    Args:
        entries: List of entry dicts with keys: number, letter.

    Returns:
        Sorted list of entries.
    """

    def _sort_key(e: dict[str, Any]) -> tuple[int, str]:
        num = int(e["number"]) if e["number"] is not None else 0
        letter = str(e["letter"]) if e["letter"] else ""
        return (num, letter)

    return sorted(entries, key=_sort_key)


def parse_commit_entries(
    commit_lines: list[str],
    include_raw_lines: bool = False,
) -> list[dict[str, Any]]:
    """Parse commit entry lines into structured dicts.

    Args:
        commit_lines: Lines from the COMMITS section (excluding the header).
        include_raw_lines: If True, each entry dict will include a "raw_lines"
            key containing the original lines for that entry.

    Returns:
        List of entry dicts with keys: number, letter, note, chat, diff,
        and optionally raw_lines.
    """
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
            }
            if include_raw_lines:
                current_entry["raw_lines"] = [line]
        elif stripped.startswith("| CHAT:") and current_entry:
            current_entry["chat"] = stripped[7:].strip()
            if include_raw_lines:
                current_entry["raw_lines"].append(line)
        elif stripped.startswith("| DIFF:") and current_entry:
            current_entry["diff"] = stripped[7:].strip()
            if include_raw_lines:
                current_entry["raw_lines"].append(line)
        elif current_entry and stripped == "":
            # Blank line within commits section
            pass

    if current_entry:
        entries.append(current_entry)

    return entries


def find_commits_section(lines: list[str], cl_name: str) -> tuple[int, int]:
    """Find the start and end indices of the COMMITS section for a ChangeSpec.

    Args:
        lines: All lines from the project file.
        cl_name: The CL name to find.

    Returns:
        Tuple of (commits_start, commits_end) line indices.
        commits_start is the index of the "COMMITS:" line.
        commits_end is one past the last commit entry line.
        Returns (-1, -1) if the COMMITS section is not found.
    """
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
                if re.match(r"^\(\d+[a-z]?\)", stripped) or stripped.startswith("| "):
                    commits_end = i + 1  # Track last commit line
                elif stripped and not stripped.startswith("#"):
                    # Non-commit content
                    break

    if commits_start < 0:
        return (-1, -1)

    if commits_end < 0:
        commits_end = len(lines)

    return (commits_start, commits_end)
