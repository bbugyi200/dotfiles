"""Shared utility functions for workflow modules."""

import os
import subprocess

from ace.changespec import ChangeSpec, parse_project_file
from shared_utils import run_shell_command


def get_project_file_path(project: str) -> str:
    """Get the path to the project file for a given project.

    Args:
        project: Project name.

    Returns:
        Path to the project file (~/.gai/projects/<project>/<project>.gp).
    """
    return os.path.expanduser(f"~/.gai/projects/{project}/{project}.gp")


def get_cl_name_from_branch() -> str | None:
    """Get the current CL name from branch_name command.

    Returns:
        The CL name, or None if not on a branch.
    """
    result = run_shell_command("branch_name", capture_output=True)
    if result.returncode != 0:
        return None
    branch_name = result.stdout.strip()
    return branch_name if branch_name else None


def get_project_from_workspace() -> str | None:
    """Get the current project name from workspace_name command.

    Returns:
        The project name, or None if command fails.
    """
    result = run_shell_command("workspace_name", capture_output=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _get_changed_test_targets(verbose: bool = False) -> str | None:
    """Get test targets from changed files in the current branch.

    Calls the `changed_test_targets` script to get Blaze test targets
    for files that have changed in the current branch.

    Args:
        verbose: If True, print diagnostic messages when command fails.

    Returns:
        Space-separated test targets string, or None if no targets found
        or the command fails.
    """
    from rich_utils import print_status

    try:
        result = subprocess.run(
            ["changed_test_targets"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            targets = result.stdout.strip()
            if targets:
                return targets
            if verbose:
                print_status("changed_test_targets returned empty output.", "info")
        elif verbose:
            stderr_preview = result.stderr.strip()[:100] if result.stderr else ""
            print_status(
                f"changed_test_targets failed (exit {result.returncode})"
                + (f": {stderr_preview}" if stderr_preview else ""),
                "warning",
            )
    except FileNotFoundError:
        if verbose:
            print_status("changed_test_targets command not found.", "warning")
    except Exception as e:
        if verbose:
            print_status(f"changed_test_targets error: {e}", "warning")
    return None


def get_changespec_from_file(project_file: str, cl_name: str) -> ChangeSpec | None:
    """Get a ChangeSpec from a project file by name.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to look for.

    Returns:
        The ChangeSpec if found, None otherwise.
    """
    changespecs = parse_project_file(project_file)
    for cs in changespecs:
        if cs.name == cl_name:
            return cs
    return None


def add_test_hooks_if_available(
    project_file: str,
    cl_name: str,
    workspace_dir: str | None = None,
    verbose: bool = True,
) -> bool:
    """Add test target hooks from changed_test_targets if available.

    This centralizes the logic for adding test target hooks, which is used by:
    - commit_workflow
    - amend_workflow
    - accept_workflow
    - _auto_accept_proposal (completer)

    Args:
        project_file: Path to the project file.
        cl_name: The CL name.
        workspace_dir: Optional workspace directory to run the command in.
                       If provided, changes to this directory before running
                       changed_test_targets, then restores the original directory.
        verbose: If True, print status messages.

    Returns:
        True if test hooks were added or none were needed, False on error.
    """
    from ace.hooks import add_test_target_hooks_to_changespec
    from rich_utils import print_status

    # Run changed_test_targets in the specified directory if provided
    original_dir = None
    if workspace_dir:
        original_dir = os.getcwd()
        os.chdir(workspace_dir)

    try:
        test_targets = _get_changed_test_targets(verbose=verbose)
    finally:
        if original_dir:
            os.chdir(original_dir)

    if not test_targets:
        return True  # No targets to add, not an error

    if verbose:
        print_status("Checking for new test target hooks...", "progress")

    target_list = test_targets.split()
    changespec = get_changespec_from_file(project_file, cl_name)
    existing_hooks = changespec.hooks if changespec else None

    if add_test_target_hooks_to_changespec(
        project_file, cl_name, target_list, existing_hooks
    ):
        if verbose:
            print_status(f"Added {len(target_list)} test target hook(s).", "success")
        return True
    else:
        if verbose:
            print_status("Failed to add test target hooks.", "warning")
        return False
