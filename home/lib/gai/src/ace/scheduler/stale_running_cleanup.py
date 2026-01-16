"""Stale RUNNING entry cleanup utilities for the axe scheduler."""

from collections.abc import Callable
from pathlib import Path

from running_field import get_claimed_workspaces, release_workspace

from ..hooks.processes import is_process_running


def cleanup_stale_running_entries(
    log_fn: Callable[[str, str | None], None] | None = None,
) -> int:
    """Release workspace claims for processes that are no longer running.

    Iterates through all project files and checks each RUNNING entry's PID.
    If the process is no longer running, the workspace claim is released.

    Args:
        log_fn: Optional logging function (message, style).

    Returns:
        Number of stale workspace claims released.
    """
    released_count = 0

    for project_file in _get_all_project_files():
        claims = get_claimed_workspaces(project_file)

        for claim in claims:
            if is_process_running(claim.pid):
                continue

            release_workspace(
                project_file, claim.workspace_num, claim.workflow, claim.cl_name
            )
            released_count += 1

            if log_fn:
                cl_info = f" for CL {claim.cl_name}" if claim.cl_name else ""
                log_fn(
                    f"Released stale workspace #{claim.workspace_num} "
                    f"({claim.workflow}){cl_info} - PID {claim.pid} not running",
                    "cyan",
                )

    return released_count


def _get_all_project_files() -> list[str]:
    """Get all project file paths from ~/.gai/projects/.

    Returns:
        List of paths to .gp files for all projects.
    """
    projects_dir = Path.home() / ".gai" / "projects"
    if not projects_dir.exists():
        return []

    project_files: list[str] = []
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        gp_file = project_dir / f"{project_dir.name}.gp"
        if gp_file.exists():
            project_files.append(str(gp_file))

    return project_files
