"""Utility functions for managing HISTORY entries in ChangeSpecs."""

import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def _get_diffs_directory() -> str:
    """Get the path to the diffs directory (~/.gai/diffs/)."""
    return os.path.expanduser("~/.gai/diffs")


def _ensure_diffs_directory() -> None:
    """Ensure the diffs directory exists."""
    diffs_dir = _get_diffs_directory()
    Path(diffs_dir).mkdir(parents=True, exist_ok=True)


def generate_timestamp() -> str:
    """Generate a timestamp in YYmmddHHMMSS format (2-digit year)."""
    eastern = ZoneInfo("America/New_York")
    return datetime.now(eastern).strftime("%y%m%d%H%M%S")


def save_diff(
    cl_name: str,
    target_dir: str | None = None,
    timestamp: str | None = None,
) -> str | None:
    """Save the current hg diff to a file.

    Args:
        cl_name: The CL name (used in filename).
        target_dir: Optional directory to run hg diff in.
        timestamp: Optional timestamp for filename (YYmmddHHMMSS format).

    Returns:
        Path to the saved diff file (with ~ for home), or None if no changes.
    """
    _ensure_diffs_directory()

    # Run hg diff
    try:
        result = subprocess.run(
            ["hg", "diff"],
            capture_output=True,
            text=True,
            cwd=target_dir,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        diff_content = result.stdout
    except Exception:
        return None

    # Generate filename: cl_name_timestamp.diff
    # Replace non-alphanumeric chars with underscore for safe filename
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", cl_name)
    if timestamp is None:
        timestamp = generate_timestamp()
    filename = f"{safe_name}_{timestamp}.diff"

    # Save the diff
    diffs_dir = _get_diffs_directory()
    diff_path = os.path.join(diffs_dir, filename)

    with open(diff_path, "w", encoding="utf-8") as f:
        f.write(diff_content)

    # Return path with ~ for home directory
    return diff_path.replace(str(Path.home()), "~")


def get_next_history_number(lines: list[str], cl_name: str) -> int:
    """Get the next history entry number for a ChangeSpec.

    Only counts regular entries (not proposed entries with letter suffixes).

    Args:
        lines: Lines from the project file.
        cl_name: The CL name to find.

    Returns:
        The next history entry number (1 if no entries exist).
    """
    in_target_changespec = False
    in_history = False
    max_number = 0

    for line in lines:
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            in_history = False
        elif in_target_changespec:
            if line.startswith("HISTORY:"):
                in_history = True
            elif line.startswith(
                (
                    "NAME:",
                    "DESCRIPTION:",
                    "PARENT:",
                    "CL:",
                    "STATUS:",
                    "TEST TARGETS:",
                    "KICKSTART:",
                )
            ):
                in_history = False
                if line.startswith("NAME:"):
                    in_target_changespec = False
            elif in_history:
                # Check for regular history entry: (N) Note text (no letter suffix)
                # Skip proposed entries like (2a)
                match = re.match(r"^\s*\((\d+)\)\s+", line)
                if match:
                    num = int(match.group(1))
                    max_number = max(max_number, num)

    return max_number + 1


def _get_last_regular_history_number(lines: list[str], cl_name: str) -> int:
    """Get the last regular (non-proposed) history entry number.

    Args:
        lines: Lines from the project file.
        cl_name: The CL name to find.

    Returns:
        The last regular history entry number (0 if no entries exist).
    """
    return get_next_history_number(lines, cl_name) - 1


def _get_next_proposal_letter(lines: list[str], cl_name: str, base_number: int) -> str:
    """Get the next available proposal letter for a base number.

    Args:
        lines: Lines from the project file.
        cl_name: The CL name to find.
        base_number: The base history number (e.g., 2 for 2a, 2b, etc.).

    Returns:
        The next available letter ('a' if none exist, 'b' if 'a' exists, etc.).
    """
    in_target_changespec = False
    in_history = False
    used_letters: set[str] = set()

    for line in lines:
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            in_history = False
        elif in_target_changespec:
            if line.startswith("HISTORY:"):
                in_history = True
            elif line.startswith(
                (
                    "NAME:",
                    "DESCRIPTION:",
                    "PARENT:",
                    "CL:",
                    "STATUS:",
                    "TEST TARGETS:",
                    "KICKSTART:",
                )
            ):
                in_history = False
                if line.startswith("NAME:"):
                    in_target_changespec = False
            elif in_history:
                # Check for proposed entry: (Na) where N is base_number
                match = re.match(r"^\s*\((\d+)([a-z])\)\s+", line)
                if match and int(match.group(1)) == base_number:
                    used_letters.add(match.group(2))

    # Find the first unused letter
    for letter in "abcdefghijklmnopqrstuvwxyz":
        if letter not in used_letters:
            return letter

    # Should never happen in practice (26 proposals max)
    raise ValueError(f"No available proposal letters for base number {base_number}")


def add_proposed_history_entry(
    project_file: str,
    cl_name: str,
    note: str,
    diff_path: str | None = None,
    chat_path: str | None = None,
) -> tuple[bool, str | None]:
    """Add a proposed HISTORY entry to a ChangeSpec.

    Proposed entries have format (Na) where N is the last regular entry number.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to add history to.
        note: The note for this history entry.
        diff_path: Optional path to the diff file.
        chat_path: Optional path to the chat file.

    Returns:
        Tuple of (success, entry_id). entry_id is like "2a" if successful.
    """
    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return False, None

    # Get the last regular history number and next proposal letter
    base_number = _get_last_regular_history_number(lines, cl_name)
    if base_number == 0:
        # No regular history entries yet - use 0 as base
        # This handles the edge case where propose is used before any commits
        base_number = 0
    proposal_letter = _get_next_proposal_letter(lines, cl_name, base_number)
    entry_id = f"{base_number}{proposal_letter}"

    # Find the ChangeSpec and determine where to add the history entry
    in_target_changespec = False
    history_field_line = -1
    last_history_entry_line = -1
    changespec_end_line = -1

    in_history_section = False
    for i, line in enumerate(lines):
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            if in_target_changespec:
                # We hit the next ChangeSpec, stop here
                changespec_end_line = i
                break
            in_target_changespec = current_name == cl_name
        elif in_target_changespec:
            if line.startswith("HISTORY:"):
                history_field_line = i
                in_history_section = True
            elif in_history_section:
                # Check if this is a history entry line or continuation
                stripped = line.strip()
                # Match both regular (N) and proposed (Na) entries
                if re.match(r"^\(\d+[a-z]?\)", stripped) or stripped.startswith("| "):
                    last_history_entry_line = i
                elif stripped and not stripped.startswith("#"):
                    # Non-history, non-empty line - history section ended
                    in_history_section = False
                    if changespec_end_line < 0:
                        changespec_end_line = i

    # Handle end of file
    if in_target_changespec and changespec_end_line < 0:
        changespec_end_line = len(lines)

    if not in_target_changespec and changespec_end_line < 0:
        # ChangeSpec not found
        return False, None

    # Build the history entry (2-space indented, sub-fields 6-space indented)
    entry_lines = [f"  ({entry_id}) {note}\n"]
    if chat_path:
        entry_lines.append(f"      | CHAT: {chat_path}\n")
    if diff_path:
        entry_lines.append(f"      | DIFF: {diff_path}\n")

    # Determine insertion point
    if history_field_line >= 0:
        # HISTORY field exists - add after last entry
        if last_history_entry_line >= 0:
            insert_idx = last_history_entry_line + 1
        else:
            insert_idx = history_field_line + 1
    else:
        # No HISTORY field - need to add one
        # Find where to insert (before STATUS or at end of changespec)
        insert_idx = changespec_end_line
        for i, line in enumerate(lines):
            if in_target_changespec and line.startswith("STATUS:"):
                insert_idx = i
                break
            if line.startswith("NAME: "):
                current_name = line[6:].strip()
                in_target_changespec = current_name == cl_name

        # Add HISTORY: header
        entry_lines.insert(0, "HISTORY:\n")

    # Insert the entry
    for j, entry_line in enumerate(entry_lines):
        lines.insert(insert_idx + j, entry_line)

    # Write back to file atomically
    project_dir = os.path.dirname(project_file)
    fd, temp_path = tempfile.mkstemp(dir=project_dir, prefix=".tmp_", suffix=".gp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.replace(temp_path, project_file)
        return True, entry_id
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        return False, None


def apply_diff_to_workspace(workspace_dir: str, diff_path: str) -> tuple[bool, str]:
    """Apply a saved diff to the workspace using hg import.

    Args:
        workspace_dir: The workspace directory to apply the diff in.
        diff_path: Path to the diff file (may use ~ for home).

    Returns:
        Tuple of (success, error_message). error_message is empty on success.
    """
    expanded_path = os.path.expanduser(diff_path)
    if not os.path.exists(expanded_path):
        return False, f"Diff file not found: {diff_path}"

    try:
        result = subprocess.run(
            ["hg", "import", "--no-commit", expanded_path],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or "hg import failed"
        return True, ""
    except Exception as e:
        return False, str(e)


def clean_workspace(workspace_dir: str) -> bool:
    """Clean the workspace by reverting all uncommitted changes.

    Args:
        workspace_dir: The workspace directory to clean.

    Returns:
        True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            ["hg", "update", "--clean", "."],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def add_history_entry(
    project_file: str,
    cl_name: str,
    note: str,
    diff_path: str | None = None,
    chat_path: str | None = None,
) -> bool:
    """Add a new HISTORY entry to a ChangeSpec.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to add history to.
        note: The note for this history entry.
        diff_path: Optional path to the diff file.
        chat_path: Optional path to the chat file.

    Returns:
        True if successful, False otherwise.
    """
    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return False

    # Find the ChangeSpec and determine where to add the history entry
    in_target_changespec = False
    history_field_line = -1
    last_history_entry_line = -1
    changespec_end_line = -1

    for i, line in enumerate(lines):
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            if in_target_changespec:
                # We hit the next ChangeSpec, stop here
                changespec_end_line = i
                break
            in_target_changespec = current_name == cl_name
        elif in_target_changespec:
            if line.startswith("HISTORY:"):
                history_field_line = i
            elif history_field_line >= 0:
                # Check if this is a history entry line or continuation
                stripped = line.strip()
                if re.match(r"^\(\d+\)", stripped) or stripped.startswith("| "):
                    last_history_entry_line = i
                elif stripped and not stripped.startswith("#"):
                    # Non-history, non-empty line - history section ended
                    if changespec_end_line < 0:
                        changespec_end_line = i

    # Handle end of file
    if in_target_changespec and changespec_end_line < 0:
        changespec_end_line = len(lines)

    if not in_target_changespec and changespec_end_line < 0:
        # ChangeSpec not found
        return False

    # Get the next history number
    next_num = get_next_history_number(lines, cl_name)

    # Build the history entry (2-space indented, sub-fields 6-space indented)
    entry_lines = [f"  ({next_num}) {note}\n"]
    if chat_path:
        entry_lines.append(f"      | CHAT: {chat_path}\n")
    if diff_path:
        entry_lines.append(f"      | DIFF: {diff_path}\n")

    # Determine insertion point
    if history_field_line >= 0:
        # HISTORY field exists - add after last entry
        if last_history_entry_line >= 0:
            insert_idx = last_history_entry_line + 1
        else:
            insert_idx = history_field_line + 1
    else:
        # No HISTORY field - need to add one
        # Find where to insert (before STATUS or at end of changespec)
        insert_idx = changespec_end_line
        for i, line in enumerate(lines):
            if in_target_changespec and line.startswith("STATUS:"):
                insert_idx = i
                break
            if line.startswith("NAME: "):
                current_name = line[6:].strip()
                in_target_changespec = current_name == cl_name

        # Add HISTORY: header
        entry_lines.insert(0, "HISTORY:\n")

    # Insert the entry
    for j, entry_line in enumerate(entry_lines):
        lines.insert(insert_idx + j, entry_line)

    # Write back to file atomically
    project_dir = os.path.dirname(project_file)
    fd, temp_path = tempfile.mkstemp(dir=project_dir, prefix=".tmp_", suffix=".gp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.replace(temp_path, project_file)
        return True
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        return False
