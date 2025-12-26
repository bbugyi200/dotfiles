"""Core ChangeSpec operations for updating, extracting, and validating."""

import os
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from running_field import (
    get_first_available_workspace,
    get_workspace_directory_for_num,
)
from running_field import (
    get_workspace_directory as get_workspace_dir_from_project,
)

from .changespec import ChangeSpec
from .hooks import has_failing_hooks_for_fix, has_failing_test_target_hooks


def get_workspace_directory(
    changespec: ChangeSpec, all_changespecs: list[ChangeSpec] | None = None
) -> tuple[str, str | None]:
    """Determine which workspace directory to use for a ChangeSpec.

    Uses the RUNNING field in the ProjectSpec file to track which workspaces
    are currently in use. Finds the first available (unclaimed) workspace.

    Args:
        changespec: The ChangeSpec to determine workspace for
        all_changespecs: Unused, kept for backwards compatibility

    Returns:
        Tuple of (workspace_directory, workspace_suffix)
        - workspace_directory: Full path to workspace directory
        - workspace_suffix: Suffix like "fig_3" or None for main workspace
    """
    # Extract project basename from file path
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Find first available workspace using RUNNING field
    workspace_num = get_first_available_workspace(
        changespec.file_path, project_basename
    )

    return get_workspace_directory_for_num(workspace_num, project_basename)


def _has_failing_test_target_hooks(changespec: ChangeSpec) -> bool:
    """Check if a ChangeSpec has any test target hooks with FAILED status.

    Args:
        changespec: The ChangeSpec to check

    Returns:
        True if any test target hooks have FAILED status
    """
    return has_failing_test_target_hooks(changespec.hooks)


def _has_failing_hooks_for_fix(changespec: ChangeSpec) -> bool:
    """Check if a ChangeSpec has any hooks eligible for fix-hook workflow.

    This excludes hooks that already have a fix-hook agent running (timestamp suffix)
    or hooks that the user has marked to skip (! suffix).

    Args:
        changespec: The ChangeSpec to check

    Returns:
        True if any hooks are eligible for fix-hook workflow
    """
    return has_failing_hooks_for_fix(changespec.hooks)


def get_available_workflows(changespec: ChangeSpec) -> list[str]:
    """Get all available workflows for this ChangeSpec.

    Returns a list of workflow names that are applicable for this ChangeSpec based on:
    - Any HOOKS have FAILED status - Runs fix-hook workflow
    - Test target HOOKS have FAILED status - Runs fix-tests workflow
    - COMMENTS has [reviewer] entry without suffix - Runs crs workflow

    Note: QA workflow can be run manually via `gai run qa` from any status.

    Args:
        changespec: The ChangeSpec object to check

    Returns:
        List of workflow names (e.g., ["fix-hook", "fix-tests", "crs"])
    """
    workflows = []

    # Add fix-hook workflow if there are any failing hooks eligible for fix
    if _has_failing_hooks_for_fix(changespec):
        workflows.append("fix-hook")

    # Add fix-tests workflow if there are failing test target hooks
    if _has_failing_test_target_hooks(changespec):
        workflows.append("fix-tests")

    # Add crs workflow if there's a [reviewer] comment entry without suffix
    if changespec.comments:
        for entry in changespec.comments:
            if entry.reviewer == "reviewer" and entry.suffix is None:
                workflows.append("crs")
                break

    return workflows


def update_to_changespec(
    changespec: ChangeSpec,
    console: Console | None = None,
    revision: str | None = None,
    workspace_dir: str | None = None,
) -> tuple[bool, str | None]:
    """Update working directory to the specified ChangeSpec.

    This function:
    1. Changes to workspace directory (uses bb_get_workspace to determine path)
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

        try:
            target_dir = get_workspace_dir_from_project(project_basename)
        except RuntimeError as e:
            return (False, str(e))

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
