"""Core ChangeSpec operations for updating, extracting, and validating."""

import os
import re
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import remove_workspace_suffix

from .changespec import ChangeSpec


def _get_workspace_suffix(status: str) -> str | None:
    """Extract workspace share suffix from a status value.

    Args:
        status: STATUS value, possibly with workspace suffix (e.g., "Creating EZ CL... (fig_3)")

    Returns:
        Workspace suffix (e.g., "fig_3") or None if no suffix present
    """
    # Match pattern: " (<project>_<N>)" at the end of the status
    match = re.search(r" \(([a-zA-Z0-9_-]+_\d+)\)$", status)
    if match:
        return match.group(1)
    return None


def _is_in_progress_status(status: str) -> bool:
    """Check if a status represents an in-progress state.

    In-progress statuses are those ending with "..." (after removing workspace suffix).

    Args:
        status: STATUS value to check

    Returns:
        True if status is in-progress, False otherwise
    """
    # Remove workspace suffix first, then check if it ends with "..."
    base_status = remove_workspace_suffix(status)
    return base_status.endswith("...")


def get_workspace_directory(
    changespec: ChangeSpec, all_changespecs: list[ChangeSpec]
) -> tuple[str, str | None]:
    """Determine which workspace directory to use for a ChangeSpec.

    Logic:
    1. If NO ChangeSpec has in-progress status → use main workspace
    2. If a ChangeSpec has in-progress status without suffix → main workspace is in use
    3. Find lowest N (2-100) where no ChangeSpec has suffix (<project>_<N>)

    Args:
        changespec: The ChangeSpec to determine workspace for
        all_changespecs: All ChangeSpecs across all projects

    Returns:
        Tuple of (workspace_directory, workspace_suffix)
        - workspace_directory: Full path to workspace directory
        - workspace_suffix: Suffix like "fig_3" or None for main workspace
    """
    # Extract project basename from file path
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Get required environment variables
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

    if not goog_cloud_dir or not goog_src_dir_base:
        # Fall back to main workspace if env vars not set
        main_dir = os.path.join(
            goog_cloud_dir or "", project_basename, goog_src_dir_base or ""
        )
        return (main_dir, None)

    # Filter changespecs for the same project
    project_changespecs = [
        cs
        for cs in all_changespecs
        if os.path.splitext(os.path.basename(cs.file_path))[0] == project_basename
    ]

    # Find all in-progress changespecs with their workspace suffixes
    in_progress_workspaces: set[str | None] = set()
    for cs in project_changespecs:
        if _is_in_progress_status(cs.status):
            suffix = _get_workspace_suffix(cs.status)
            in_progress_workspaces.add(suffix)

    # Case 1: No in-progress changespecs → use main workspace
    if not in_progress_workspaces:
        main_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)
        return (main_dir, None)

    # Case 2: Main workspace is available (no None in the set)
    if None not in in_progress_workspaces:
        main_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)
        return (main_dir, None)

    # Case 3: Main workspace is in use, find available workspace share
    # Check N from 2 to 100
    for n in range(2, 101):
        workspace_suffix = f"{project_basename}_{n}"
        if workspace_suffix not in in_progress_workspaces:
            # Check if this workspace directory exists
            workspace_dir = os.path.join(
                goog_cloud_dir, workspace_suffix, goog_src_dir_base
            )
            if os.path.exists(workspace_dir) and os.path.isdir(workspace_dir):
                return (workspace_dir, workspace_suffix)

    # No available workspace found - fall back to main workspace
    # (this shouldn't happen in normal usage, but provides a safe fallback)
    main_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)
    return (main_dir, None)


def get_available_workflows(changespec: ChangeSpec) -> list[str]:
    """Get all available workflows for this ChangeSpec.

    Returns a list of workflow names that are applicable for this ChangeSpec based on:
    - STATUS = "Failing Tests" - Runs fix-tests workflow
    - STATUS = "Changes Requested" - Runs crs workflow

    Note: QA workflow can be run manually via `gai run qa` from any status.

    Args:
        changespec: The ChangeSpec object to check

    Returns:
        List of workflow names (e.g., ["fix-tests", "crs"])
    """
    workflows = []

    # Add workflows based on status
    if changespec.status == "Failing Tests":
        workflows.append("fix-tests")
    elif changespec.status == "Changes Requested":
        workflows.append("crs")

    return workflows


def has_failed_presubmit(changespec: ChangeSpec) -> bool:
    """Check if a ChangeSpec has a failed presubmit.

    Args:
        changespec: The ChangeSpec to check

    Returns:
        True if PRESUBMIT field contains "(FAILED)" tag
    """
    if not changespec.presubmit:
        return False
    return "(FAILED)" in changespec.presubmit


def update_to_changespec(
    changespec: ChangeSpec,
    console: Console | None = None,
    revision: str | None = None,
    workspace_dir: str | None = None,
) -> tuple[bool, str | None]:
    """Update working directory to the specified ChangeSpec.

    This function:
    1. Changes to workspace directory (or $GOOG_CLOUD_DIR/<project>/$GOOG_SRC_DIR_BASE if not specified)
    2. Runs bb_hg_update <revision>

    Args:
        changespec: The ChangeSpec object to update to
        console: Optional Rich Console object for error output
        revision: Specific revision to update to. If None, uses parent or p4head.
                  Common values: changespec.name (for diff), changespec.parent (for workflow)
        workspace_dir: Optional workspace directory to use. If None, uses main workspace.

    Returns:
        Tuple of (success, error_message)
    """
    # Determine target directory
    if workspace_dir:
        target_dir = workspace_dir
    else:
        # Extract project basename from file path
        # e.g., /path/to/foobar.md -> foobar
        project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

        # Get required environment variables
        goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
        goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

        if not goog_cloud_dir:
            return (False, "GOOG_CLOUD_DIR environment variable is not set")
        if not goog_src_dir_base:
            return (False, "GOOG_SRC_DIR_BASE environment variable is not set")

        # Build target directory path
        target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    # Verify directory exists
    if not os.path.exists(target_dir):
        return (False, f"Target directory does not exist: {target_dir}")
    if not os.path.isdir(target_dir):
        return (False, f"Target path is not a directory: {target_dir}")

    # Determine which revision to update to
    if revision is not None:
        update_target = revision
    else:
        # Default: Use PARENT field if set, otherwise use p4head
        update_target = changespec.parent if changespec.parent else "p4head"

    # Run bb_hg_update command
    try:
        subprocess.run(
            ["bb_hg_update", update_target],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return (True, None)
    except subprocess.CalledProcessError as e:
        error_msg = f"bb_hg_update failed (exit code {e.returncode})"
        if e.stderr:
            error_msg += f": {e.stderr.strip()}"
        elif e.stdout:
            error_msg += f": {e.stdout.strip()}"
        return (False, error_msg)
    except FileNotFoundError:
        return (False, "bb_hg_update command not found")
    except Exception as e:
        return (False, f"Unexpected error running bb_hg_update: {str(e)}")
