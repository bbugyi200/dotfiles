"""Workspace and diff management utilities."""

import os
from pathlib import Path

from gai_utils import (
    ensure_gai_directory,
    generate_timestamp,
    make_safe_filename,
    strip_reverted_suffix,
)
from vcs_provider import get_vcs_provider


def save_diff(
    cl_name: str,
    target_dir: str | None = None,
    timestamp: str | None = None,
) -> str | None:
    """Save the current diff to a file.

    Args:
        cl_name: The CL name (used in filename).
        target_dir: Optional directory to run diff in.
        timestamp: Optional timestamp for filename (YYmmdd_HHMMSS format).

    Returns:
        Path to the saved diff file (with ~ for home), or None if no changes.
    """
    cwd = target_dir or os.getcwd()
    provider = get_vcs_provider(cwd)
    diffs_dir = ensure_gai_directory("diffs")

    # Run addremove to track new/deleted files before creating diff
    try:
        provider.add_remove(cwd)
    except Exception:
        pass  # Continue even if addremove fails

    # Run diff
    success, diff_content = provider.diff(cwd)
    if not success or not diff_content:
        return None

    # Generate filename: cl_name-timestamp.diff
    safe_name = make_safe_filename(strip_reverted_suffix(cl_name))
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
    """Apply a saved diff to the workspace.

    Args:
        workspace_dir: The workspace directory to apply the diff in.
        diff_path: Path to the diff file (may use ~ for home).

    Returns:
        Tuple of (success, error_message). error_message is empty on success.
    """
    provider = get_vcs_provider(workspace_dir)
    success, error = provider.apply_patch(diff_path, workspace_dir)
    if not success:
        return False, error or "apply_patch failed"
    return True, ""


def apply_diffs_to_workspace(
    workspace_dir: str, diff_paths: list[str]
) -> tuple[bool, str]:
    """Apply multiple saved diffs to the workspace.

    Args:
        workspace_dir: The workspace directory to apply the diffs in.
        diff_paths: List of paths to diff files (may use ~ for home).

    Returns:
        Tuple of (success, error_message). error_message is empty on success.
    """
    if not diff_paths:
        return True, ""
    provider = get_vcs_provider(workspace_dir)
    success, error = provider.apply_patches(diff_paths, workspace_dir)
    if not success:
        return False, error or "apply_patches failed"
    return True, ""


def clean_workspace(workspace_dir: str) -> bool:
    """Clean the workspace by reverting all uncommitted changes.

    Args:
        workspace_dir: The workspace directory to clean.

    Returns:
        True if successful, False otherwise.
    """
    try:
        provider = get_vcs_provider(workspace_dir)
        success, _ = provider.clean_workspace(workspace_dir)
        return success
    except Exception:
        return False


def run_bb_hg_clean(workspace_dir: str, diff_name: str) -> tuple[bool, str]:
    """Save changes and clean the workspace.

    This saves any uncommitted changes to a diff file before cleaning.
    Should be called BEFORE switching branches.

    Args:
        workspace_dir: The workspace directory to clean.
        diff_name: Name for the backup diff file (without .diff extension).

    Returns:
        Tuple of (success, error_message).
    """
    try:
        provider = get_vcs_provider(workspace_dir)
        success, error = provider.stash_and_clean(diff_name, workspace_dir)
        if not success:
            return False, error or "stash_and_clean failed"
        return True, ""
    except Exception as e:
        return False, str(e)
