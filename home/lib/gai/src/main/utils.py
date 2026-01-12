"""Utility functions for the main entry point."""

import os

from shared_utils import run_shell_command

# Type alias for project info return type
ProjectInfo = tuple[str | None, int | None, str | None]


def _get_project_name() -> str | None:
    """Get the project name from the workspace_name command.

    Returns:
        The project name, or None if not in a recognized workspace.
    """
    try:
        result = run_shell_command("workspace_name", capture_output=True)
        if result.returncode != 0:
            return None
        project_name = result.stdout.strip()
        return project_name if project_name else None
    except Exception:
        return None


def _get_workspace_num(project_name: str) -> int:
    """Determine workspace number from current directory.

    Args:
        project_name: The project name to check for.

    Returns:
        The workspace number (1 for main workspace, 2+ for workspace shares).
    """
    cwd = os.getcwd()
    for n in range(2, 101):
        workspace_suffix = f"{project_name}_{n}"
        if workspace_suffix in cwd:
            return n
    return 1


def ensure_project_file_and_get_workspace_num() -> ProjectInfo:
    """Get project file and workspace num, creating project file if needed.

    This function will create the project file if it doesn't exist yet
    (without a BUG field, which can be added later via `gai ace`).

    Returns:
        Tuple of (project_file, workspace_num, project_name)
        All None if not in a recognized workspace or creation failed.
    """
    from commit_workflow.project_file_utils import create_project_file

    project_name = _get_project_name()
    if not project_name:
        return (None, None, None)

    # Construct project file path
    project_file = os.path.expanduser(
        f"~/.gai/projects/{project_name}/{project_name}.gp"
    )

    # Create project file if it doesn't exist
    if not os.path.exists(project_file):
        if not create_project_file(project_name):
            return (None, None, None)

    workspace_num = _get_workspace_num(project_name)
    return (project_file, workspace_num, project_name)
