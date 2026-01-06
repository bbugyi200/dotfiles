"""Functions for retrieving branch and CL information."""

import os

from shared_utils import run_shell_command
from workflow_utils import get_project_file_path


def get_parent_branch_name() -> str | None:
    """Get the parent branch name using the branch_name command.

    Returns:
        The parent branch name, or None if the command fails or returns empty.
    """
    result = run_shell_command("branch_name", capture_output=True)
    if result.returncode != 0:
        return None
    parent_name = result.stdout.strip()
    return parent_name if parent_name else None


def get_existing_changespec_description(project: str, cl_name: str) -> str | None:
    """Get the DESCRIPTION field from an existing ChangeSpec.

    Args:
        project: Project name.
        cl_name: CL name to look for.

    Returns:
        The description text if found, None otherwise.
    """
    project_file = get_project_file_path(project)
    if not os.path.isfile(project_file):
        return None

    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        in_target_changespec = False
        in_description = False
        description_lines: list[str] = []

        for line in lines:
            # Check for NAME field
            if line.startswith("NAME: "):
                existing_name = line[6:].strip()
                in_target_changespec = existing_name == cl_name
                in_description = False
                if in_target_changespec:
                    description_lines = []
            elif in_target_changespec:
                if line.startswith("DESCRIPTION:"):
                    in_description = True
                    # Check if description is on the same line
                    desc_inline = line[12:].strip()
                    if desc_inline:
                        description_lines.append(desc_inline)
                elif in_description and line.startswith("  "):
                    # Description continuation (2-space indented)
                    description_lines.append(line[2:].rstrip("\n"))
                elif in_description and line.strip() == "":
                    # Blank line in description
                    description_lines.append("")
                elif line.startswith(
                    ("PARENT:", "CL:", "STATUS:", "TEST TARGETS:", "KICKSTART:")
                ):
                    # Hit another field, stop reading description
                    if in_description:
                        break

        if description_lines:
            return "\n".join(description_lines).strip()
        return None
    except Exception:
        return None


def get_cl_number() -> str | None:
    """Get the CL number using the branch_number command.

    Returns:
        The CL number, or None if the command fails.
    """
    result = run_shell_command("branch_number", capture_output=True)
    if result.returncode != 0:
        return None
    cl_number = result.stdout.strip()
    return cl_number if cl_number and cl_number.isdigit() else None
