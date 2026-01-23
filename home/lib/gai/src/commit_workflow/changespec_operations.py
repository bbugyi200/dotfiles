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
        success, _, _, _ = transition_changespec_status(
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
    initial_commits: list[tuple[int, str, str | None, str | None]] | None = None,
    bug: str | None = None,
) -> str | None:
    """Add a new ChangeSpec to the project file.

    The ChangeSpec is placed:
    - Directly after the parent ChangeSpec if parent is specified
    - At the top of the file (after BUG: header) if no parent

    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project: Project name.
        cl_name: NAME field value (will be suffixed with __<N> for uniqueness).
        description: DESCRIPTION field value (raw, will be indented).
        parent: PARENT field value (or None for "None").
        cl_url: CL field value (e.g., "http://cl/12345").
        initial_hooks: List of hook commands to include in the HOOKS field.
            If None or empty, no HOOKS field is added.
        initial_commits: List of (number, note, chat_path, diff_path) tuples
            for the COMMITS field. chat_path and diff_path are optional drawer
            paths. If None or empty, no COMMITS field is added.
        bug: BUG field value (e.g., "http://b/12345"). If None, no BUG field
            is added.

    Returns:
        The suffixed cl_name (e.g., "foo_bar__1") on success, None on failure.
    """
    project_file = get_project_file_path(project)

    # Format the description with 2-space indent
    description_lines = description.strip().split("\n")
    formatted_description = "\n".join(f"  {line}" for line in description_lines)

    # Build partial ChangeSpec components (name added after suffix computation)
    # Only include PARENT line if parent is specified
    parent_line = f"PARENT: {parent}\n" if parent else ""
    # BUG line is built later after potential parent inheritance

    # Build COMMITS field if initial_commits provided
    commits_block = ""
    if initial_commits:
        from commit_utils.entries import format_chat_line_with_duration

        commits_lines = ["COMMITS:\n"]
        for num, note, chat_path, diff_path in initial_commits:
            commits_lines.append(f"  ({num}) {note}\n")
            if chat_path:
                commits_lines.append(format_chat_line_with_duration(chat_path))
            if diff_path:
                commits_lines.append(f"      | DIFF: {diff_path}\n")
        commits_block = "".join(commits_lines)

    try:
        with changespec_lock(project_file):
            with open(project_file, encoding="utf-8") as f:
                lines = f.readlines()

            # Extract existing names to compute unique suffix
            existing_names = set()
            for line in lines:
                if line.startswith("NAME: "):
                    existing_names.add(line[6:].strip())

            # Add __<N> suffix to make name unique (for WIP ChangeSpecs)
            from gai_utils import get_next_suffix_number

            suffix_num = get_next_suffix_number(cl_name, existing_names)
            cl_name = f"{cl_name}__{suffix_num}"

            # Determine insertion point and collect parent hooks
            parent_hooks_to_add: list[str] = []
            if parent:
                # Find the end of the parent ChangeSpec
                parent_end = _find_changespec_end_line(lines, parent)
                if parent_end is not None:
                    # Insert after parent ChangeSpec
                    insert_index = parent_end + 1

                    # Get parent hooks and BUG to inherit
                    from ace.changespec import parse_project_file

                    changespecs = parse_project_file(project_file)
                    for cs in changespecs:
                        if cs.name == parent:
                            # Inherit hooks from parent
                            if cs.hooks:
                                # Collect existing hook commands to avoid duplicates
                                existing_hooks = (
                                    set(initial_hooks) if initial_hooks else set()
                                )
                                for hook_entry in cs.hooks:
                                    if hook_entry.command not in existing_hooks:
                                        parent_hooks_to_add.append(hook_entry.command)
                            # Inherit BUG from parent if not explicitly provided
                            if not bug and cs.bug:
                                bug = cs.bug
                            break
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

            # Build BUG line (may be inherited from parent)
            bug_line = f"BUG: {bug}\n" if bug else ""

            # Build HOOKS field with initial hooks + inherited parent hooks
            all_hooks = list(initial_hooks or []) + parent_hooks_to_add
            hooks_block = ""
            if all_hooks:
                hooks_lines = ["HOOKS:\n"]
                for hook_cmd in all_hooks:
                    hooks_lines.append(f"  {hook_cmd}\n")
                hooks_block = "".join(hooks_lines)

            # Build the ChangeSpec block with the suffixed name
            changespec_block = f"""

NAME: {cl_name}
DESCRIPTION:
{formatted_description}
{parent_line}{bug_line}CL: {cl_url}
STATUS: WIP
{commits_block}{hooks_block}"""

            # Insert the new ChangeSpec
            lines.insert(insert_index, changespec_block)

            # Write atomically
            write_changespec_atomic(
                project_file,
                "".join(lines),
                f"Add ChangeSpec {cl_name}",
            )

        return cl_name
    except Exception as e:
        print_status(f"Failed to add ChangeSpec to project file: {e}", "warning")
        return None


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
