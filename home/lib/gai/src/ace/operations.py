"""Core ChangeSpec operations for updating, extracting, and validating."""

import os
import sys
from pathlib import Path

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gai_utils import (
    get_next_suffix_number,
    has_suffix,
)
from running_field import (
    get_first_available_workspace,
    get_workspace_directory_for_num,
    update_running_field_cl_name,
)
from running_field import (
    get_workspace_directory as get_workspace_dir_from_project,
)
from status_state_machine import update_parent_references_atomic

from .changespec import ChangeSpec
from .hooks import has_failing_hooks_for_fix


def get_workspace_directory(changespec: ChangeSpec) -> tuple[str, str | None]:
    """Determine which workspace directory to use for a ChangeSpec.

    Uses the RUNNING field in the ProjectSpec file to track which workspaces
    are currently in use. Finds the first available (unclaimed) workspace.

    Args:
        changespec: The ChangeSpec to determine workspace for

    Returns:
        Tuple of (workspace_directory, workspace_suffix)
        - workspace_directory: Full path to workspace directory
        - workspace_suffix: Suffix like "fig_3" or None for main workspace
    """
    # Find first available workspace using RUNNING field
    workspace_num = get_first_available_workspace(changespec.file_path)

    return get_workspace_directory_for_num(workspace_num, changespec.project_basename)


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
    - COMMENTS has [reviewer] entry without suffix - Runs crs workflow

    Args:
        changespec: The ChangeSpec object to check

    Returns:
        List of workflow names (e.g., ["fix-hook", "crs"])
    """
    workflows = []

    # Add fix-hook workflow if there are any failing hooks eligible for fix
    if _has_failing_hooks_for_fix(changespec):
        workflows.append("fix-hook")

    # Add crs workflow if there's a [critique] comment entry without suffix
    if changespec.comments:
        for entry in changespec.comments:
            if entry.reviewer == "critique" and entry.suffix is None:
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
        try:
            target_dir = get_workspace_dir_from_project(changespec.project_basename)
        except RuntimeError as e:
            return (False, str(e))

    # Verify directory exists
    if not os.path.exists(target_dir):
        return (False, f"Target directory does not exist: {target_dir}")
    if not os.path.isdir(target_dir):
        return (False, f"Target path is not a directory: {target_dir}")

    # Run checkout via VCS provider
    from vcs_provider import get_vcs_provider

    provider = get_vcs_provider(target_dir)

    # Determine which revision to update to
    if revision is not None:
        update_target = revision
    else:
        # Default: Use PARENT field if set, otherwise use VCS default
        update_target = (
            changespec.parent
            if changespec.parent
            else provider.get_default_parent_revision(target_dir)
        )

    return provider.checkout(update_target, target_dir)


def has_active_children(
    changespec: ChangeSpec,
    all_changespecs: list[ChangeSpec],
    terminal_statuses: tuple[str, ...] = ("Reverted",),
) -> bool:
    """Check if any ChangeSpec has this one as a parent and is not in a terminal status.

    Args:
        changespec: The ChangeSpec to check for children.
        all_changespecs: All ChangeSpecs to search through.
        terminal_statuses: Statuses considered terminal (children with these
            statuses are ignored). Defaults to ("Reverted",) for revert.
            Archive uses ("Archived", "Reverted").

    Returns:
        True if any ChangeSpec has this one as parent and is not terminal.
    """
    for cs in all_changespecs:
        if cs.parent == changespec.name and cs.status not in terminal_statuses:
            return True
    return False


def calculate_lifecycle_new_name(
    changespec: ChangeSpec,
    all_changespecs: list[ChangeSpec],
) -> str:
    """Calculate the new name for a lifecycle operation (archive/revert).

    Appends a `__<N>` suffix, skipping if the ChangeSpec is WIP and already
    has a suffix.

    Args:
        changespec: The ChangeSpec being renamed.
        all_changespecs: All ChangeSpecs (used to find next available suffix).

    Returns:
        The new name (may be unchanged if WIP with existing suffix).
    """
    if changespec.status == "WIP" and has_suffix(changespec.name):
        return changespec.name
    existing_names = {cs.name for cs in all_changespecs}
    suffix = get_next_suffix_number(changespec.name, existing_names)
    return f"{changespec.name}__{suffix}"


def rename_changespec_with_references(
    project_file: str,
    old_name: str,
    new_name: str,
) -> None:
    """Rename a ChangeSpec and update all references (RUNNING, PARENT fields).

    Args:
        project_file: Path to the project file.
        old_name: Current name of the ChangeSpec.
        new_name: New name for the ChangeSpec.

    Raises:
        Exception: If any of the rename operations fail.
    """
    # Lazy import to avoid circular dependency
    from .revert import update_changespec_name_atomic

    update_changespec_name_atomic(project_file, old_name, new_name)
    update_running_field_cl_name(project_file, old_name, new_name)
    update_parent_references_atomic(project_file, old_name, new_name)


def save_diff_to_file(
    changespec: ChangeSpec, new_name: str, workspace_dir: str, subdir: str
) -> tuple[bool, str | None]:
    """Save the diff of a ChangeSpec to a subdirectory under ~/.gai/.

    Runs `hg diff -c <name>` in the workspace directory and saves
    the output to `~/.gai/<subdir>/<new_name>.diff`.

    Args:
        changespec: The ChangeSpec to save diff for.
        new_name: The new name (with suffix) for the diff file.
        workspace_dir: The workspace directory to run hg diff in.
        subdir: The subdirectory under ~/.gai/ (e.g., "reverted" or "archived").

    Returns:
        Tuple of (success, error_message).
    """
    target_dir = Path.home() / ".gai" / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    diff_file = target_dir / f"{new_name}.diff"

    try:
        from vcs_provider import get_vcs_provider

        provider = get_vcs_provider(workspace_dir)
        success, diff_text = provider.diff_revision(changespec.name, workspace_dir)

        if not success:
            return (False, f"hg diff failed: {diff_text}")

        with open(diff_file, "w", encoding="utf-8") as f:
            f.write(diff_text if diff_text else "")

        return (True, None)
    except Exception as e:
        return (False, f"Error saving diff: {e}")
