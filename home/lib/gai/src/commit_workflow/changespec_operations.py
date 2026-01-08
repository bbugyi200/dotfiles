"""Functions for manipulating ChangeSpec files."""

import os

from ace.changespec import changespec_lock, write_changespec_atomic
from rich_utils import print_status
from workflow_utils import get_project_file_path


def update_existing_changespec(project: str, cl_name: str, cl_url: str) -> bool:
    """Update an existing ChangeSpec's STATUS and CL fields.

    Args:
        project: Project name.
        cl_name: CL name to update.
        cl_url: New CL URL.

    Returns:
        True if update succeeded, False otherwise.
    """
    import sys as _sys

    _sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from status_state_machine import (
        transition_changespec_status,
        update_changespec_cl_atomic,
    )

    project_file = get_project_file_path(project)
    if not os.path.isfile(project_file):
        return False

    try:
        # Update CL field
        update_changespec_cl_atomic(project_file, cl_name, cl_url)

        # Update STATUS to "WIP"
        success, _, _ = transition_changespec_status(
            project_file, cl_name, "WIP", validate=False
        )
        return success
    except Exception as e:
        print_status(f"Failed to update existing ChangeSpec: {e}", "warning")
        return False


def _find_changespec_end_line(lines: list[str], changespec_name: str) -> int | None:
    """Find the line number where a ChangeSpec ends.

    A ChangeSpec ends at the last non-empty line before either:
    - The next NAME: field
    - The end of the file

    Args:
        lines: List of lines from the project file.
        changespec_name: NAME of the ChangeSpec to find.

    Returns:
        The line index (0-based) of the last line of the ChangeSpec,
        or None if the ChangeSpec is not found.
    """
    in_target_changespec = False
    changespec_end = None

    for i, line in enumerate(lines):
        if line.startswith("NAME: "):
            if in_target_changespec:
                # We hit the next ChangeSpec, so the previous one ended
                # Find the last non-empty line before this
                for j in range(i - 1, -1, -1):
                    if lines[j].strip():
                        return j
                return i - 1

            # Check if this is the target ChangeSpec
            current_name = line[6:].strip()
            if current_name == changespec_name:
                in_target_changespec = True
                changespec_end = i

        elif in_target_changespec and line.strip():
            # Track the last non-empty line in the target ChangeSpec
            changespec_end = i

    # If we're still in the target ChangeSpec at the end of file
    if in_target_changespec:
        return changespec_end

    return None


def add_changespec_to_project_file(
    project: str,
    cl_name: str,
    description: str,
    parent: str | None,
    cl_url: str,
    initial_hooks: list[str] | None = None,
) -> bool:
    """Add a new ChangeSpec to the project file.

    The ChangeSpec is placed:
    - Directly after the parent ChangeSpec if parent is specified
    - At the top of the file (after BUG: header) if no parent

    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project: Project name.
        cl_name: NAME field value.
        description: DESCRIPTION field value (raw, will be indented).
        parent: PARENT field value (or None for "None").
        cl_url: CL field value (e.g., "http://cl/12345").
        initial_hooks: List of hook commands to include in the HOOKS field.
            If None or empty, no HOOKS field is added.

    Returns:
        True if the ChangeSpec was added successfully, False otherwise.
    """
    project_file = get_project_file_path(project)

    # Format the description with 2-space indent
    description_lines = description.strip().split("\n")
    formatted_description = "\n".join(f"  {line}" for line in description_lines)

    # Build the ChangeSpec block (with leading newlines for separation)
    # Only include PARENT line if parent is specified
    parent_line = f"PARENT: {parent}\n" if parent else ""

    # Build HOOKS field if initial_hooks provided
    hooks_block = ""
    if initial_hooks:
        hooks_lines = ["HOOKS:\n"]
        for hook_cmd in initial_hooks:
            hooks_lines.append(f"  {hook_cmd}\n")
        hooks_block = "".join(hooks_lines)

    changespec_block = f"""

NAME: {cl_name}
DESCRIPTION:
{formatted_description}
{parent_line}CL: {cl_url}
STATUS: WIP
{hooks_block}"""

    try:
        with changespec_lock(project_file):
            with open(project_file, encoding="utf-8") as f:
                lines = f.readlines()

            # Determine insertion point
            if parent:
                # Find the end of the parent ChangeSpec
                parent_end = _find_changespec_end_line(lines, parent)
                if parent_end is not None:
                    # Insert after parent ChangeSpec
                    insert_index = parent_end + 1
                else:
                    # Parent not found, append to end
                    print_status(
                        f"Parent ChangeSpec '{parent}' not found. "
                        "Appending to end of file.",
                        "warning",
                    )
                    insert_index = len(lines)
            else:
                # No parent - append to end of file
                insert_index = len(lines)

            # Insert the new ChangeSpec
            lines.insert(insert_index, changespec_block)

            # Write atomically
            write_changespec_atomic(
                project_file,
                "".join(lines),
                f"Add ChangeSpec {cl_name}",
            )

        return True
    except Exception as e:
        print_status(f"Failed to add ChangeSpec to project file: {e}", "warning")
        return False


def ensure_required_hooks(
    project_file: str,
    changespec_name: str,
    required_hooks: tuple[str, ...],
) -> bool:
    """Ensure required hooks are present in a ChangeSpec.

    Used for backward compatibility when restoring old ChangeSpecs
    that may be missing required hooks.

    Args:
        project_file: Path to the project file.
        changespec_name: NAME of the ChangeSpec.
        required_hooks: Tuple of required hook commands.

    Returns:
        True if all hooks are present/added, False on error.
    """
    from ace.hooks import add_hook_to_changespec

    for hook_cmd in required_hooks:
        if not add_hook_to_changespec(project_file, changespec_name, hook_cmd):
            return False
    return True
