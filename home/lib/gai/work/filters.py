"""Filter validation and application for ChangeSpecs."""

import os
from pathlib import Path

from .changespec import ChangeSpec


def validate_filters(
    status_filters: list[str] | None, project_filters: list[str] | None
) -> tuple[bool, str | None]:
    """Validate status and project filters.

    Args:
        status_filters: List of status values to validate
        project_filters: List of project basenames to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Import here to avoid circular dependency
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from status_state_machine import VALID_STATUSES

    # Validate status filters
    if status_filters:
        for status in status_filters:
            if status not in VALID_STATUSES:
                valid_statuses_str = ", ".join(f'"{s}"' for s in VALID_STATUSES)
                return (
                    False,
                    f'Invalid status "{status}". Valid statuses: {valid_statuses_str}',
                )

    # Validate project filters
    if project_filters:
        projects_dir = os.path.expanduser("~/.gai/projects")
        for project in project_filters:
            project_file = os.path.join(projects_dir, project, f"{project}.gp")
            if not os.path.exists(project_file):
                return (
                    False,
                    f"Project file not found: {project_file}",
                )

    return (True, None)


def filter_changespecs(
    changespecs: list[ChangeSpec],
    status_filters: list[str] | None,
    project_filters: list[str] | None,
) -> list[ChangeSpec]:
    """Filter changespecs based on status and project filters.

    Args:
        changespecs: List of ChangeSpec objects to filter
        status_filters: List of status values to filter by (OR logic)
        project_filters: List of project basenames to filter by (OR logic)

    Returns:
        Filtered list of ChangeSpec objects
    """
    filtered = changespecs

    # Apply status filter (OR logic)
    if status_filters:
        filtered = [cs for cs in filtered if cs.status in status_filters]

    # Apply project filter (OR logic)
    if project_filters:
        # Convert project filters to set of full file paths for comparison
        projects_dir = Path.home() / ".gai" / "projects"
        project_paths = {
            str(projects_dir / proj / f"{proj}.gp") for proj in project_filters
        }
        filtered = [cs for cs in filtered if cs.file_path in project_paths]

    return filtered
