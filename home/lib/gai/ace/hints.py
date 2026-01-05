"""Hint parsing utilities for TUI.

This module provides functions to parse hint input from users.
"""

import os


def is_rerun_input(user_input: str) -> bool:
    """Check if user input is a rerun/delete command (list of integers with optional suffix).

    Suffixes:
        - No suffix: rerun the hook (clear status for last history entry)
        - '@' suffix: delete the hook entirely

    Args:
        user_input: The user's input string

    Returns:
        True if input looks like a rerun command (e.g., "1 2 3", "1@", "2@ 3")
    """
    if not user_input:
        return False

    for part in user_input.split():
        # Reject '@@' suffix (no longer supported)
        if part.endswith("@@"):
            return False
        # Strip optional '@' suffix
        part_stripped = part.rstrip("@")
        # Check if it's a valid integer
        if not part_stripped.isdigit():
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
        user_input: The user's input string (e.g., "1 2 3@")
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

        try:
            hint_num = int(part)
            if hint_num in hint_mappings:
                file_path = os.path.expanduser(hint_mappings[hint_num])
                files_to_view.append(file_path)
            else:
                invalid_hints.append(hint_num)
        except ValueError:
            # Not a number, skip
            pass

    return files_to_view, open_in_editor, invalid_hints


def parse_edit_hooks_input(
    user_input: str, hint_mappings: dict[int, str]
) -> tuple[list[int], list[int], list[int]]:
    """Parse user input for rerun/delete hooks.

    Args:
        user_input: The user's input string (e.g., "1 2@ 3")
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

        try:
            hint_num = int(part)
            if hint_num in hint_mappings:
                if action == "delete":
                    hints_to_delete.append(hint_num)
                else:
                    hints_to_rerun.append(hint_num)
            else:
                invalid_hints.append(hint_num)
        except ValueError:
            # Not a number
            pass

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
