"""Workspace and diff management utilities."""

import os
import subprocess
from pathlib import Path

from gai_utils import ensure_gai_directory, generate_timestamp, make_safe_filename


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


def apply_diffs_to_workspace(
    workspace_dir: str, diff_paths: list[str]
) -> tuple[bool, str]:
    """Apply multiple saved diffs to the workspace using a single hg import.

    Args:
        workspace_dir: The workspace directory to apply the diffs in.
        diff_paths: List of paths to diff files (may use ~ for home).

    Returns:
        Tuple of (success, error_message). error_message is empty on success.
    """
    if not diff_paths:
        return True, ""

    expanded_paths = []
    for diff_path in diff_paths:
        expanded = os.path.expanduser(diff_path)
        if not os.path.exists(expanded):
            return False, f"Diff file not found: {diff_path}"
        expanded_paths.append(expanded)

    try:
        result = subprocess.run(
            ["hg", "import", "--no-commit"] + expanded_paths,
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
