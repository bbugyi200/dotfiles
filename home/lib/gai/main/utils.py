"""Utility functions for the main entry point."""

import os

from shared_utils import run_shell_command


def get_project_file_and_workspace_num() -> tuple[str | None, int | None, str | None]:
    """Get the project file path and workspace number from the current directory.

    Returns:
        Tuple of (project_file, workspace_num, project_name)
        All None if not in a recognized workspace.
    """
    try:
        result = run_shell_command("workspace_name", capture_output=True)
        if result.returncode != 0:
            return (None, None, None)
        project_name = result.stdout.strip()
        if not project_name:
            return (None, None, None)
    except Exception:
        return (None, None, None)

    # Construct project file path
    project_file = os.path.expanduser(
        f"~/.gai/projects/{project_name}/{project_name}.gp"
    )
    if not os.path.exists(project_file):
        return (None, None, None)

    # Determine workspace number from current directory
    cwd = os.getcwd()

    # Check if we're in a numbered workspace share
    workspace_num = 1
    for n in range(2, 101):
        workspace_suffix = f"{project_name}_{n}"
        if workspace_suffix in cwd:
            workspace_num = n
            break

    return (project_file, workspace_num, project_name)
