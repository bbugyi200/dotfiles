"""Hint parsing utilities for TUI.

This module provides functions to parse hint input from users.
"""

import os


def _expand_hint_part(part: str) -> list[int]:
    """Expand a hint part which may be a single number or a range.

    Args:
        part: A string like "5" or "1-10"

    Returns:
        List of integers (empty if invalid)
    """
    if "-" in part and not part.startswith("-"):
        # Range format: "1-10"
        range_parts = part.split("-", 1)
        if len(range_parts) == 2:
            try:
                start = int(range_parts[0])
                end = int(range_parts[1])
                if start <= end:
                    return list(range(start, end + 1))
            except ValueError:
                pass
        return []
    else:
        # Single number
        try:
            return [int(part)]
        except ValueError:
            return []


def _is_valid_hint_part(part: str) -> bool:
    """Check if a hint part is valid (single number or range).

    Args:
        part: A string like "5" or "1-10"

    Returns:
        True if the part is a valid hint (number or range)
    """
    if "-" in part and not part.startswith("-"):
        # Range format: check both parts are digits
        range_parts = part.split("-", 1)
        if len(range_parts) != 2:
            return False
        return range_parts[0].isdigit() and range_parts[1].isdigit()
    else:
        return part.isdigit()


def is_rerun_input(user_input: str) -> bool:
    """Check if user input is a rerun/delete command (list of integers/ranges with optional suffix).

    Suffixes:
        - No suffix: rerun the hook (clear status for last history entry)
        - '@' suffix: delete the hook entirely

    Args:
        user_input: The user's input string

    Returns:
        True if input looks like a rerun command (e.g., "1 2 3", "1@", "2@ 3", "1-5")
    """
    if not user_input:
        return False

    for part in user_input.split():
        # Reject '@@' suffix (no longer supported)
        if part.endswith("@@"):
            return False
        # Strip optional '@' suffix
        part_stripped = part.rstrip("@")
        # Check if it's a valid integer or range
        if not _is_valid_hint_part(part_stripped):
            return False

    return True


def build_editor_args(editor: str, files: list[str]) -> list[str]:
    """Build editor command arguments.

    Args:
        editor: The editor command (e.g., from $EDITOR)
        files: List of file paths to open

    Returns:
        List of command arguments for subprocess.run
    """
    return [editor] + files


def parse_view_input(
    user_input: str, hint_mappings: dict[int, str]
) -> tuple[list[str], bool, list[int]]:
    """Parse user input for view files modal.

    Args:
        user_input: The user's input string (e.g., "1 2 3@" or "1-5@")
        hint_mappings: Dict mapping hint numbers to file paths

    Returns:
        Tuple of:
        - List of valid file paths to view/edit
        - Whether to open in editor (@ suffix detected)
        - List of invalid hint numbers (for error messages)
    """
    parts = user_input.split()
    if not parts:
        return [], False, []

    open_in_editor = False
    files_to_view: list[str] = []
    invalid_hints: list[int] = []

    for part in parts:
        # Check for '@' suffix
        if part.endswith("@"):
            open_in_editor = True
            part = part[:-1]

        # Skip empty parts (standalone '@' is no longer supported)
        if not part:
            continue

        # Expand the part (handles both single numbers and ranges)
        hint_nums = _expand_hint_part(part)

        for hint_num in hint_nums:
            if hint_num in hint_mappings:
                file_path = os.path.expanduser(hint_mappings[hint_num])
                if file_path not in files_to_view:  # Avoid duplicates
                    files_to_view.append(file_path)
            else:
                invalid_hints.append(hint_num)

    return files_to_view, open_in_editor, invalid_hints


def parse_edit_hooks_input(
    user_input: str, hint_mappings: dict[int, str]
) -> tuple[list[int], list[int], list[int]]:
    """Parse user input for rerun/delete hooks.

    Args:
        user_input: The user's input string (e.g., "1 2@ 3" or "1-5@")
        hint_mappings: Dict mapping hint numbers to file paths

    Returns:
        Tuple of:
        - List of hint numbers to rerun
        - List of hint numbers to delete
        - List of invalid hint numbers
    """
    hints_to_rerun: list[int] = []
    hints_to_delete: list[int] = []
    invalid_hints: list[int] = []

    for part in user_input.split():
        action = "rerun"
        if part.endswith("@"):
            action = "delete"
            part = part[:-1]

        # Expand the part (handles both single numbers and ranges)
        hint_nums = _expand_hint_part(part)

        for hint_num in hint_nums:
            if hint_num in hint_mappings:
                if action == "delete":
                    hints_to_delete.append(hint_num)
                else:
                    hints_to_rerun.append(hint_num)
            else:
                invalid_hints.append(hint_num)

    return hints_to_rerun, hints_to_delete, invalid_hints


def parse_test_targets(test_input: str) -> list[str]:
    """Parse test target input into a list of targets.

    Args:
        test_input: String starting with "//" containing test targets

    Returns:
        List of test targets, each prefixed with "//"
    """
    parts = test_input.split()
    targets = []
    for part in parts:
        part = part.strip()
        if part:
            # Ensure each target starts with "//"
            if not part.startswith("//"):
                part = "//" + part
            targets.append(part)
    return targets
