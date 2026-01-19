"""Functions for querying ChangeSpec existence."""

import os

from workflow_utils import get_project_file_path


def project_file_exists(project: str) -> bool:
    """Check if a project file exists for the given project.

    Args:
        project: Project name.

    Returns:
        True if the project file exists, False otherwise.
    """
    return os.path.isfile(get_project_file_path(project))


def changespec_exists(project: str, cl_name: str) -> bool:
    """Check if a ChangeSpec with the given name already exists in the project file.

    Args:
        project: Project name.
        cl_name: CL name to check for.

    Returns:
        True if a ChangeSpec with the given NAME exists, False otherwise.
    """
    project_file = get_project_file_path(project)
    if not os.path.isfile(project_file):
        return False

    try:
        with open(project_file, encoding="utf-8") as f:
            for line in f:
                if line.startswith("NAME: "):
                    existing_name = line[6:].strip()
                    if existing_name == cl_name:
                        return True
        return False
    except Exception:
        return False


def get_conflicting_changespec(project: str, cl_name: str) -> tuple[str, str] | None:
    """Check if cl_name conflicts with an existing non-revertable ChangeSpec.

    A conflict exists if any ChangeSpec has the same base name (after stripping
    the __<N> suffix) and has a status NOT in {"WIP", "Reverted"}. This prevents
    creating CLs that would conflict with existing active ChangeSpecs.

    Args:
        project: Project name.
        cl_name: CL name to check (with or without project prefix).

    Returns:
        Tuple of (conflicting_name, status) if conflict exists, None otherwise.
    """
    from ace.changespec import parse_project_file
    from gai_utils import strip_reverted_suffix

    project_file = get_project_file_path(project)
    if not os.path.isfile(project_file):
        return None

    # Normalize: ensure project prefix
    full_name = cl_name
    if not cl_name.startswith(f"{project}_"):
        full_name = f"{project}_{cl_name}"

    # Get base name (strip any existing suffix)
    base_name = strip_reverted_suffix(full_name)

    changespecs = parse_project_file(project_file)
    for cs in changespecs:
        cs_base = strip_reverted_suffix(cs.name)
        if cs_base == base_name and cs.status not in {"WIP", "Reverted"}:
            return (cs.name, cs.status)

    return None
