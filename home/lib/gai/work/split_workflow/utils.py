"""Utility functions for the split workflow."""

import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

from rich.console import Console
from running_field import (
    get_first_available_workspace,
    get_workspace_directory_for_num,
)
from shared_utils import run_shell_command

from work.changespec import find_all_changespecs
from work.revert import revert_changespec


def generate_timestamp() -> str:
    """Generate timestamp in YYmmdd_HHMMSS format."""
    eastern = ZoneInfo("America/New_York")
    return datetime.now(eastern).strftime("%y%m%d_%H%M%S")


def get_project_file_and_workspace_info(
    project_name: str,
) -> tuple[str | None, int | None, str | None]:
    """Get the project file path and first available workspace.

    Uses get_first_available_workspace() to find an unclaimed workspace,
    ensuring multiple workflows don't try to use the same workspace.

    Args:
        project_name: The project/workspace name.

    Returns:
        Tuple of (project_file, workspace_num, workspace_dir), or (None, None, None) if not found.
    """
    # Construct project file path
    project_file = os.path.expanduser(
        f"~/.gai/projects/{project_name}/{project_name}.gp"
    )
    if not os.path.exists(project_file):
        return (None, None, None)

    # Find first available (unclaimed) workspace
    workspace_num = get_first_available_workspace(project_file, project_name)
    workspace_dir, _ = get_workspace_directory_for_num(workspace_num, project_name)

    return (project_file, workspace_num, workspace_dir)


def get_splits_directory() -> str:
    """Get the path to the splits directory (~/.gai/splits/)."""
    return os.path.expanduser("~/.gai/splits")


def get_editor() -> str:
    """Get the editor to use for editing files.

    Returns:
        The editor command to use.
    """
    editor = os.environ.get("EDITOR")
    if editor:
        return editor

    # Fall back to nvim if it exists
    try:
        result = subprocess.run(
            ["which", "nvim"], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            return "nvim"
    except Exception:
        pass

    return "vim"


def has_children(name: str) -> bool:
    """Check if any non-reverted ChangeSpec has this one as a parent.

    Args:
        name: The ChangeSpec name to check.

    Returns:
        True if any non-reverted ChangeSpec has this one as parent.
    """
    all_cs = find_all_changespecs()
    for cs in all_cs:
        if cs.parent == name and cs.status != "Reverted":
            return True
    return False


def get_name_from_branch() -> str | None:
    """Get the CL name from the current branch.

    Returns:
        The branch name or None if not available.
    """
    result = run_shell_command("branch_name", capture_output=True)
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    return name if name else None


def prompt_for_revert(name: str, console: Console) -> bool:
    """Prompt user to revert the original CL and execute if confirmed.

    Args:
        name: The name of the ChangeSpec to revert.
        console: Rich console for output.

    Returns:
        True if revert was successful, False otherwise.
    """
    console.print(f"\n[yellow]Revert the original CL '{name}'?[/yellow]")
    response = input("(y/n): ").strip().lower()

    if response == "y":
        all_cs = find_all_changespecs()
        target = None
        for cs in all_cs:
            if cs.name == name:
                target = cs
                break

        if target:
            success, error = revert_changespec(target, console)
            if success:
                console.print("[green]Original CL reverted successfully[/green]")
                return True
            else:
                console.print(f"[red]Failed to revert: {error}[/red]")
                return False
        else:
            console.print(f"[red]ChangeSpec '{name}' not found[/red]")
            return False

    return False
