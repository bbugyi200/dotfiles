"""Hint extraction utilities for TUI modals.

This module extracts hint information from ChangeSpecs for use in TUI modals,
separating the hint generation logic from the Rich-based display code.
"""

import os
import re
from pathlib import Path

from .changespec import ChangeSpec, get_current_and_proposal_entry_ids
from .hint_types import HintItem
from .hooks import get_hook_output_path


def extract_view_hints(
    changespec: ChangeSpec,
) -> tuple[list[HintItem], dict[int, str]]:
    """Extract all file hints from a ChangeSpec for view files modal.

    Returns hints for:
    - Project file (hint 0)
    - Note paths in COMMITS entries (e.g., "(~/path/to/file)")
    - CHAT paths in COMMITS entries
    - DIFF paths in COMMITS entries
    - Hook output files
    - Comment files

    Args:
        changespec: The ChangeSpec to extract hints from.

    Returns:
        Tuple of:
        - List of HintItem objects (hint 0 is always the project file)
        - Dict mapping hint numbers to file paths
    """
    hints: list[HintItem] = []
    hint_mappings: dict[int, str] = {}
    hint_counter = 1

    # Hint 0 is always the project file
    hint_mappings[0] = changespec.file_path
    project_display = changespec.file_path.replace(str(Path.home()), "~")
    hints.append(
        HintItem(
            hint_number=0,
            display_text=f"PROJECT: {project_display}",
            file_path=changespec.file_path,
            category="project",
        )
    )

    # COMMITS entries
    if changespec.commits:
        for entry in changespec.commits:
            # Check for file path in note (e.g., "(~/path/to/file)")
            note_path_match = re.search(r"\((~/[^)]+)\)", entry.note)
            if note_path_match:
                note_path = note_path_match.group(1)
                full_path = os.path.expanduser(note_path)
                hint_mappings[hint_counter] = full_path
                hints.append(
                    HintItem(
                        hint_number=hint_counter,
                        display_text=f"({entry.display_number}) NOTE: {note_path}",
                        file_path=full_path,
                        category="note_path",
                    )
                )
                hint_counter += 1

            # CHAT field
            if entry.chat:
                # Parse duration suffix from chat (e.g., "path (1h2m3s)")
                chat_duration_match = re.search(r" \((\d+[hms]+[^)]*)\)$", entry.chat)
                if chat_duration_match:
                    chat_path_raw = entry.chat[: chat_duration_match.start()]
                else:
                    chat_path_raw = entry.chat

                hint_mappings[hint_counter] = chat_path_raw
                chat_display = chat_path_raw.replace(str(Path.home()), "~")
                hints.append(
                    HintItem(
                        hint_number=hint_counter,
                        display_text=f"({entry.display_number}) CHAT: {chat_display}",
                        file_path=chat_path_raw,
                        category="chat",
                    )
                )
                hint_counter += 1

            # DIFF field
            if entry.diff:
                hint_mappings[hint_counter] = entry.diff
                diff_display = entry.diff.replace(str(Path.home()), "~")
                hints.append(
                    HintItem(
                        hint_number=hint_counter,
                        display_text=f"({entry.display_number}) DIFF: {diff_display}",
                        file_path=entry.diff,
                        category="diff",
                    )
                )
                hint_counter += 1

    # HOOKS entries - show all hook output files
    if changespec.hooks:
        for hook in changespec.hooks:
            if hook.status_lines:
                for sl in hook.status_lines:
                    hook_output_path = get_hook_output_path(
                        changespec.name, sl.timestamp
                    )
                    hint_mappings[hint_counter] = hook_output_path
                    # Shorten command for display
                    cmd_display = (
                        hook.display_command[:30] + "..."
                        if len(hook.display_command) > 33
                        else hook.display_command
                    )
                    hints.append(
                        HintItem(
                            hint_number=hint_counter,
                            display_text=f"({sl.commit_entry_num}) HOOK: {cmd_display} [{sl.status}]",
                            file_path=hook_output_path,
                            category="hook",
                        )
                    )
                    hint_counter += 1

    # COMMENTS entries
    if changespec.comments:
        for comment in changespec.comments:
            full_path = os.path.expanduser(comment.file_path)
            hint_mappings[hint_counter] = full_path
            display_path = comment.file_path.replace(str(Path.home()), "~")
            hints.append(
                HintItem(
                    hint_number=hint_counter,
                    display_text=f"[{comment.reviewer}] {display_path}",
                    file_path=full_path,
                    category="comment",
                )
            )
            hint_counter += 1

    return hints, hint_mappings


def extract_edit_hooks_hints(
    changespec: ChangeSpec,
) -> tuple[list[HintItem], dict[int, str], dict[int, int]]:
    """Extract hook hints for hooks_latest_only mode.

    Only returns hints for hooks with status lines matching the current/proposal
    entry IDs (i.e., hooks that can be rerun).

    Args:
        changespec: The ChangeSpec to extract hints from.

    Returns:
        Tuple of:
        - List of HintItem objects for displayable hooks
        - Dict mapping hint numbers to file paths
        - Dict mapping hint numbers to hook indices
    """
    hints: list[HintItem] = []
    hint_mappings: dict[int, str] = {}
    hook_hint_to_idx: dict[int, int] = {}
    hint_counter = 1

    if not changespec.hooks:
        return hints, hint_mappings, hook_hint_to_idx

    # Get non-historical entry IDs for hint display
    non_historical_ids = get_current_and_proposal_entry_ids(changespec)

    for hook_idx, hook in enumerate(changespec.hooks):
        if hook.status_lines:
            for sl in hook.status_lines:
                # Only show hints for non-historical entries
                if sl.commit_entry_num in non_historical_ids:
                    hook_output_path = get_hook_output_path(
                        changespec.name, sl.timestamp
                    )
                    hint_mappings[hint_counter] = hook_output_path
                    hook_hint_to_idx[hint_counter] = hook_idx

                    # Shorten command for display
                    cmd_display = (
                        hook.display_command[:30] + "..."
                        if len(hook.display_command) > 33
                        else hook.display_command
                    )
                    hints.append(
                        HintItem(
                            hint_number=hint_counter,
                            display_text=f"({sl.commit_entry_num}) {cmd_display} [{sl.status}]",
                            file_path=hook_output_path,
                            category="hook",
                        )
                    )
                    hint_counter += 1

    return hints, hint_mappings, hook_hint_to_idx


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


def build_editor_args(
    editor: str, user_input: str, changespec_name: str, files: list[str]
) -> list[str]:
    """Build editor command arguments, with nvim-specific enhancements.

    When viewing the project file (hint 0) with nvim and '@' suffix,
    adds commands to jump to the current ChangeSpec's NAME field.

    Args:
        editor: The editor command (e.g., from $EDITOR)
        user_input: The raw user input string
        changespec_name: The NAME field of the current ChangeSpec
        files: List of file paths to open

    Returns:
        List of command arguments for subprocess.run
    """
    args = [editor]

    # Check if we should add nvim-specific args:
    # - Viewing project file: first char is "0", or just "@" (shorthand for "0@")
    # - Last char is "@" (opening in editor)
    # - Editor contains "/nvim"
    is_viewing_project_file = user_input and (user_input[0] == "0" or user_input == "@")
    if is_viewing_project_file and user_input[-1] == "@" and "/nvim" in editor:
        # Add nvim commands to jump to the ChangeSpec's NAME field
        args.extend(
            [
                "-c",
                f"/NAME: \\zs{changespec_name}$",
                "-c",
                "normal zz",
                "-c",
                "nohlsearch",
            ]
        )

    args.extend(files)
    return args


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
            # Allow standalone '@' as shorthand for '0@'
            if not part:
                part = "0"

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
