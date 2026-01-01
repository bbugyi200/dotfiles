"""Utility functions for managing COMMITS entries in ChangeSpecs."""

import os
import re
import subprocess
import tempfile
from pathlib import Path

from gai_utils import ensure_gai_directory, generate_timestamp, make_safe_filename


def _extract_timestamp_from_chat_path(chat_path: str) -> str | None:
    """Extract the timestamp from a chat file path.

    Chat filenames have format: <branch>-<workflow>[-<agent>]-<timestamp>.md
    The timestamp is always the last 13 characters before the .md extension.

    Args:
        chat_path: Path to the chat file (e.g., "~/.gai/chats/mybranch-fix_tests-251227_143052.md")

    Returns:
        The timestamp string (e.g., "251227_143052") or None if extraction fails.
    """
    if not chat_path or not chat_path.endswith(".md"):
        return None

    # Get the basename and remove .md extension
    basename = os.path.basename(chat_path)
    name_without_ext = basename[:-3]  # Remove ".md"

    # Timestamp is last 13 characters (YYmmdd_HHMMSS format)
    if len(name_without_ext) < 13:
        return None

    timestamp = name_without_ext[-13:]

    # Validate format: 6 digits + underscore + 6 digits
    if (
        len(timestamp) == 13
        and timestamp[6] == "_"
        and timestamp[:6].isdigit()
        and timestamp[7:].isdigit()
    ):
        return timestamp

    return None


def _format_chat_line_with_duration(chat_path: str) -> str:
    """Format a CHAT line with optional duration suffix.

    Args:
        chat_path: Path to the chat file.

    Returns:
        Formatted CHAT line like "      | CHAT: <path> (1m23s)\n" or
        "      | CHAT: <path>\n" if duration cannot be calculated.
    """
    from ace.hooks.core import calculate_duration_from_timestamps, format_duration

    timestamp = _extract_timestamp_from_chat_path(chat_path)
    if timestamp is None:
        return f"      | CHAT: {chat_path}\n"

    # Get current timestamp
    current_timestamp = generate_timestamp()

    # Calculate duration
    duration_seconds = calculate_duration_from_timestamps(timestamp, current_timestamp)
    if duration_seconds is None or duration_seconds < 0:
        return f"      | CHAT: {chat_path}\n"

    duration_str = format_duration(duration_seconds)
    return f"      | CHAT: {chat_path} ({duration_str})\n"


def save_diff(
    cl_name: str,
    target_dir: str | None = None,
    timestamp: str | None = None,
) -> str | None:
    """Save the current hg diff to a file.

    Args:
        cl_name: The CL name (used in filename).
        target_dir: Optional directory to run hg diff in.
        timestamp: Optional timestamp for filename (YYmmdd_HHMMSS format).

    Returns:
        Path to the saved diff file (with ~ for home), or None if no changes.
    """
    diffs_dir = ensure_gai_directory("diffs")

    # Run hg addremove to track new/deleted files before creating diff
    try:
        subprocess.run(
            ["hg", "addremove"],
            capture_output=True,
            text=True,
            cwd=target_dir,
        )
    except Exception:
        pass  # Continue even if addremove fails

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

    # Generate filename: cl_name-timestamp.diff
    safe_name = make_safe_filename(cl_name)
    if timestamp is None:
        timestamp = generate_timestamp()
    filename = f"{safe_name}-{timestamp}.diff"

    # Save the diff
    diff_path = os.path.join(diffs_dir, filename)

    with open(diff_path, "w", encoding="utf-8") as f:
        f.write(diff_content)

    # Return path with ~ for home directory
    return diff_path.replace(str(Path.home()), "~")


def get_next_commit_number(lines: list[str], cl_name: str) -> int:
    """Get the next commit entry number for a ChangeSpec.

    Only counts regular entries (not proposed entries with letter suffixes).

    Args:
        lines: Lines from the project file.
        cl_name: The CL name to find.

    Returns:
        The next commit entry number (1 if no entries exist).
    """
    in_target_changespec = False
    in_commits = False
    max_number = 0

    for line in lines:
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            in_commits = False
        elif in_target_changespec:
            if line.startswith("COMMITS:"):
                in_commits = True
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
                in_commits = False
                if line.startswith("NAME:"):
                    in_target_changespec = False
            elif in_commits:
                # Check for regular commit entry: (N) Note text (no letter suffix)
                # Skip proposed entries like (2a)
                match = re.match(r"^\s*\((\d+)\)\s+", line)
                if match:
                    num = int(match.group(1))
                    max_number = max(max_number, num)

    return max_number + 1


def _get_last_regular_commit_number(lines: list[str], cl_name: str) -> int:
    """Get the last regular (non-proposed) commit entry number.

    Args:
        lines: Lines from the project file.
        cl_name: The CL name to find.

    Returns:
        The last regular commit entry number (0 if no entries exist).
    """
    return get_next_commit_number(lines, cl_name) - 1


def _get_next_proposal_letter(lines: list[str], cl_name: str, base_number: int) -> str:
    """Get the next available proposal letter for a base number.

    Args:
        lines: Lines from the project file.
        cl_name: The CL name to find.
        base_number: The base commit number (e.g., 2 for 2a, 2b, etc.).

    Returns:
        The next available letter ('a' if none exist, 'b' if 'a' exists, etc.).
    """
    in_target_changespec = False
    in_commits = False
    used_letters: set[str] = set()

    for line in lines:
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            in_commits = False
        elif in_target_changespec:
            if line.startswith("COMMITS:"):
                in_commits = True
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
                in_commits = False
                if line.startswith("NAME:"):
                    in_target_changespec = False
            elif in_commits:
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


def add_proposed_commit_entry(
    project_file: str,
    cl_name: str,
    note: str,
    diff_path: str | None = None,
    chat_path: str | None = None,
) -> tuple[bool, str | None]:
    """Add a proposed COMMITS entry to a ChangeSpec.

    Proposed entries have format (Na) where N is the last regular entry number.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to add commit entry to.
        note: The note for this commit entry.
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

    # Get the last regular commit number and next proposal letter
    base_number = _get_last_regular_commit_number(lines, cl_name)
    if base_number == 0:
        # No regular commit entries yet - use 0 as base
        # This handles the edge case where propose is used before any commits
        base_number = 0
    proposal_letter = _get_next_proposal_letter(lines, cl_name, base_number)
    entry_id = f"{base_number}{proposal_letter}"

    # Find the ChangeSpec and determine where to add the commit entry
    in_target_changespec = False
    commits_field_line = -1
    last_commit_entry_line = -1
    changespec_end_line = -1

    in_commits_section = False
    for i, line in enumerate(lines):
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            if in_target_changespec:
                # We hit the next ChangeSpec, stop here
                changespec_end_line = i
                break
            in_target_changespec = current_name == cl_name
        elif in_target_changespec:
            if line.startswith("COMMITS:"):
                commits_field_line = i
                in_commits_section = True
            elif in_commits_section:
                # Check if this is a commit entry line or continuation
                stripped = line.strip()
                # Match both regular (N) and proposed (Na) entries
                if re.match(r"^\(\d+[a-z]?\)", stripped) or stripped.startswith("| "):
                    last_commit_entry_line = i
                elif stripped and not stripped.startswith("#"):
                    # Non-commit, non-empty line - commits section ended
                    in_commits_section = False
                    if changespec_end_line < 0:
                        changespec_end_line = i

    # Handle end of file
    if in_target_changespec and changespec_end_line < 0:
        changespec_end_line = len(lines)

    if not in_target_changespec and changespec_end_line < 0:
        # ChangeSpec not found
        return False, None

    # Build the commit entry (2-space indented, sub-fields 6-space indented)
    # Add "(!: NEW PROPOSAL)" suffix to mark this as a new proposal needing attention
    entry_lines = [f"  ({entry_id}) {note} - (!: NEW PROPOSAL)\n"]
    if chat_path:
        entry_lines.append(_format_chat_line_with_duration(chat_path))
    if diff_path:
        entry_lines.append(f"      | DIFF: {diff_path}\n")

    # Determine insertion point
    if commits_field_line >= 0:
        # COMMITS field exists - add after last entry
        if last_commit_entry_line >= 0:
            insert_idx = last_commit_entry_line + 1
        else:
            insert_idx = commits_field_line + 1
    else:
        # No COMMITS field - need to add one
        # Find where to insert (before STATUS or at end of changespec)
        insert_idx = changespec_end_line
        for i, line in enumerate(lines):
            if in_target_changespec and line.startswith("STATUS:"):
                insert_idx = i
                break
            if line.startswith("NAME: "):
                current_name = line[6:].strip()
                in_target_changespec = current_name == cl_name

        # Add COMMITS: header
        entry_lines.insert(0, "COMMITS:\n")

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

    This runs `hg update --clean .` to revert tracked changes,
    followed by `hg clean` to remove untracked files.

    Args:
        workspace_dir: The workspace directory to clean.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Revert all tracked changes
        result = subprocess.run(
            ["hg", "update", "--clean", "."],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False

        # Remove untracked files
        result = subprocess.run(
            ["hg", "clean"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def run_bb_hg_clean(workspace_dir: str, diff_name: str) -> tuple[bool, str]:
    """Run bb_hg_clean to save changes and clean the workspace.

    This saves any uncommitted changes to a diff file before cleaning.
    Should be called BEFORE bb_hg_update when switching branches.

    Args:
        workspace_dir: The workspace directory to clean.
        diff_name: Name for the backup diff file (without .diff extension).

    Returns:
        Tuple of (success, error_message).
    """
    try:
        result = subprocess.run(
            ["bb_hg_clean", diff_name],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            error_output = (
                result.stderr.strip() or result.stdout.strip() or "no error output"
            )
            return False, error_output
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "bb_hg_clean timed out"
    except FileNotFoundError:
        return False, "bb_hg_clean command not found"
    except Exception as e:
        return False, str(e)


def add_commit_entry(
    project_file: str,
    cl_name: str,
    note: str,
    diff_path: str | None = None,
    chat_path: str | None = None,
) -> bool:
    """Add a new COMMITS entry to a ChangeSpec.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to add commit entry to.
        note: The note for this commit entry.
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

    # Find the ChangeSpec and determine where to add the commit entry
    in_target_changespec = False
    commits_field_line = -1
    last_commit_entry_line = -1
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
            if line.startswith("COMMITS:"):
                commits_field_line = i
            elif commits_field_line >= 0:
                # Check if this is a commit entry line or continuation
                stripped = line.strip()
                if re.match(r"^\(\d+\)", stripped) or stripped.startswith("| "):
                    last_commit_entry_line = i
                elif stripped and not stripped.startswith("#"):
                    # Non-commit, non-empty line - commits section ended
                    if changespec_end_line < 0:
                        changespec_end_line = i

    # Handle end of file
    if in_target_changespec and changespec_end_line < 0:
        changespec_end_line = len(lines)

    if not in_target_changespec and changespec_end_line < 0:
        # ChangeSpec not found
        return False

    # Get the next commit number
    next_num = get_next_commit_number(lines, cl_name)

    # Build the commit entry (2-space indented, sub-fields 6-space indented)
    entry_lines = [f"  ({next_num}) {note}\n"]
    if chat_path:
        entry_lines.append(_format_chat_line_with_duration(chat_path))
    if diff_path:
        entry_lines.append(f"      | DIFF: {diff_path}\n")

    # Determine insertion point
    if commits_field_line >= 0:
        # COMMITS field exists - add after last entry
        if last_commit_entry_line >= 0:
            insert_idx = last_commit_entry_line + 1
        else:
            insert_idx = commits_field_line + 1
    else:
        # No COMMITS field - need to add one
        # Find where to insert (before STATUS or at end of changespec)
        insert_idx = changespec_end_line
        for i, line in enumerate(lines):
            if in_target_changespec and line.startswith("STATUS:"):
                insert_idx = i
                break
            if line.startswith("NAME: "):
                current_name = line[6:].strip()
                in_target_changespec = current_name == cl_name

        # Add COMMITS: header
        entry_lines.insert(0, "COMMITS:\n")

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


def update_commit_entry_suffix(
    project_file: str,
    cl_name: str,
    entry_id: str,
    new_suffix_type: str,
) -> bool:
    """Remove the suffix of a COMMITS entry.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to update.
        entry_id: The entry ID to update (e.g., "2a").
        new_suffix_type: The action - only "remove" is supported.

    Returns:
        True if successful, False otherwise.
    """
    if new_suffix_type != "remove":
        return False

    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return False

    # Find the target entry and update its suffix
    in_target_changespec = False
    in_commits = False
    updated = False

    for i, line in enumerate(lines):
        if line.startswith("NAME: "):
            current_name = line[6:].strip()
            in_target_changespec = current_name == cl_name
            in_commits = False
        elif in_target_changespec:
            if line.startswith("COMMITS:"):
                in_commits = True
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
                )
            ):
                in_commits = False
                if line.startswith("NAME:"):
                    in_target_changespec = False
            elif in_commits:
                stripped = line.strip()
                # Match entry with this ID: (Na) Note text - (!: MSG) or - (~: MSG)
                entry_match = re.match(
                    rf"^\(({re.escape(entry_id)})\)\s+(.+?)\s+-\s+\((!:|~:)\s*([^)]+)\)$",
                    stripped,
                )
                if entry_match:
                    matched_id = entry_match.group(1)
                    note_text = entry_match.group(2)
                    # Preserve leading whitespace
                    leading_ws = line[: len(line) - len(line.lstrip())]
                    # Remove the suffix entirely
                    new_line = f"{leading_ws}({matched_id}) {note_text}\n"
                    lines[i] = new_line
                    updated = True
                    break

    if not updated:
        return False

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
