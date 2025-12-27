"""Shared utility functions for workflow modules."""

import os
import subprocess

from shared_utils import run_shell_command
from work.changespec import ChangeSpec, parse_project_file


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


def get_changed_test_targets() -> str | None:
    """Get test targets from changed files in the current branch.

    Calls the `changed_test_targets` script to get Blaze test targets
    for files that have changed in the current branch.

    Returns:
        Space-separated test targets string, or None if no targets found
        or the command fails.
    """
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
    except Exception:
        pass
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
