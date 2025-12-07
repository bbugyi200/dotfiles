"""Workflow for creating Mercurial commits with formatted CL descriptions."""

import os
import subprocess
import sys
import tempfile
from typing import NoReturn

from rich_utils import print_status
from shared_utils import run_shell_command
from workflow_base import BaseWorkflow


def _get_editor() -> str:
    """Get the editor to use for commit messages.

    Returns:
        The editor command to use. Checks $EDITOR first, then falls back to
        nvim if available, otherwise vim.
    """
    # Check EDITOR environment variable first
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

    # Default to vim
    return "vim"


def _open_editor_for_commit_message() -> str | None:
    """Open the user's editor with a temporary file for the commit message.

    Returns:
        Path to the temporary file containing the commit message, or None if
        the user didn't write anything or the editor failed.
    """
    # Create a temporary file that won't be automatically deleted
    fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="gai_commit_")
    os.close(fd)

    editor = _get_editor()

    try:
        # Open editor with the temporary file
        result = subprocess.run([editor, temp_path], check=False)
        if result.returncode != 0:
            print_status("Editor exited with non-zero status.", "error")
            os.unlink(temp_path)
            return None

        # Check if the user wrote anything
        with open(temp_path, encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            print_status("No commit message provided. Aborting.", "error")
            os.unlink(temp_path)
            return None

        return temp_path

    except Exception as e:
        print_status(f"Failed to open editor: {e}", "error")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return None


def _get_project_file_path(project: str) -> str:
    """Get the path to the project file for a given project.

    Args:
        project: Project name.

    Returns:
        Path to the project file (~/.gai/projects/<project>/<project>.gp).
    """
    return os.path.expanduser(f"~/.gai/projects/{project}/{project}.gp")


def _project_file_exists(project: str) -> bool:
    """Check if a project file exists for the given project.

    Args:
        project: Project name.

    Returns:
        True if the project file exists, False otherwise.
    """
    return os.path.isfile(_get_project_file_path(project))


def _changespec_exists(project: str, cl_name: str) -> bool:
    """Check if a ChangeSpec with the given name already exists in the project file.

    Args:
        project: Project name.
        cl_name: CL name to check for.

    Returns:
        True if a ChangeSpec with the given NAME exists, False otherwise.
    """
    project_file = _get_project_file_path(project)
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


def _get_parent_branch_name() -> str | None:
    """Get the parent branch name using the branch_name command.

    Returns:
        The parent branch name, or None if the command fails or returns empty.
    """
    result = run_shell_command("branch_name", capture_output=True)
    if result.returncode != 0:
        return None
    parent_name = result.stdout.strip()
    return parent_name if parent_name else None


def _get_cl_number() -> str | None:
    """Get the CL number using the branch_number command.

    Returns:
        The CL number, or None if the command fails.
    """
    result = run_shell_command("branch_number", capture_output=True)
    if result.returncode != 0:
        return None
    cl_number = result.stdout.strip()
    return cl_number if cl_number and cl_number.isdigit() else None


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


def _add_changespec_to_project_file(
    project: str,
    cl_name: str,
    description: str,
    parent: str | None,
    cl_url: str,
) -> bool:
    """Add a new ChangeSpec to the project file.

    The ChangeSpec is placed:
    - Directly after the parent ChangeSpec if parent is specified
    - At the top of the file (after BUG: header) if no parent

    Args:
        project: Project name.
        cl_name: NAME field value.
        description: DESCRIPTION field value (raw, will be indented).
        parent: PARENT field value (or None for "None").
        cl_url: CL field value (e.g., "http://cl/12345").

    Returns:
        True if the ChangeSpec was added successfully, False otherwise.
    """
    project_file = _get_project_file_path(project)

    # Format the description with 2-space indent
    description_lines = description.strip().split("\n")
    formatted_description = "\n".join(f"  {line}" for line in description_lines)

    # Build the ChangeSpec block (with leading newlines for separation)
    parent_value = parent if parent else "None"
    changespec_block = f"""

NAME: {cl_name}
DESCRIPTION:
{formatted_description}
PARENT: {parent_value}
CL: {cl_url}
STATUS: Needs Presubmit
"""

    try:
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

        # Write back to file
        with open(project_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return True
    except Exception as e:
        print_status(f"Failed to add ChangeSpec to project file: {e}", "warning")
        return False


def _format_cl_description(file_path: str, project: str, bug: str) -> None:
    """Format the CL description file with project tag and metadata.

    Args:
        file_path: Path to the file containing the CL description.
        project: Project name to prepend to the description.
        bug: Bug number to include in metadata.
    """
    # Read the original content
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Write the formatted content
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"[{project}] {content}\n")
        f.write("\n")
        f.write("AUTOSUBMIT_BEHAVIOR=SYNC_SUBMIT\n")
        f.write(f"BUG={bug}\n")
        f.write("MARKDOWN=true\n")
        f.write("R=startblock\n")
        f.write("STARTBLOCK_AUTOSUBMIT=yes\n")
        f.write("WANT_LGTM=all\n")


class CommitWorkflow(BaseWorkflow):
    """A workflow for creating Mercurial commits with formatted CL descriptions."""

    def __init__(
        self,
        cl_name: str,
        file_path: str | None = None,
        bug: str | None = None,
        project: str | None = None,
    ) -> None:
        """Initialize the commit workflow.

        Args:
            cl_name: CL name to use for the commit (e.g., "baz_feature").
            file_path: Path to the file containing the CL description. If None,
                vim will be opened for the user to write a commit message.
            bug: Bug number to include in metadata. Defaults to output of 'branch_bug'.
            project: Project name to prepend. Defaults to output of 'workspace_name'.
        """
        self.cl_name = cl_name
        self._file_path = file_path
        self._bug = bug
        self._project = project
        self._temp_file_created = False

    @property
    def name(self) -> str:
        return "commit"

    @property
    def description(self) -> str:
        return "Create a Mercurial commit with formatted CL description and metadata"

    def _get_bug(self) -> str:
        """Get the bug number, either from init or from branch_bug command."""
        if self._bug:
            return self._bug

        result = run_shell_command("branch_bug", capture_output=True)
        if result.returncode != 0:
            print_status(
                "Failed to get bug number from 'branch_bug' command. "
                "Use -b to specify manually.",
                "error",
            )
            sys.exit(1)
        return result.stdout.strip()

    def _get_project(self) -> str:
        """Get the project name, either from init or from workspace_name command."""
        if self._project:
            return self._project

        result = run_shell_command("workspace_name", capture_output=True)
        if result.returncode != 0:
            print_status(
                "Failed to get project name from 'workspace_name' command. "
                "Use -p to specify manually.",
                "error",
            )
            sys.exit(1)
        return result.stdout.strip()

    def run(self) -> bool:
        """Run the commit workflow.

        Returns:
            True if the workflow completed successfully, False otherwise.
        """
        # Get file path - either from argument or by opening vim
        file_path = self._file_path
        if file_path is None:
            file_path = _open_editor_for_commit_message()
            if file_path is None:
                return False
            self._temp_file_created = True
        elif not os.path.isfile(file_path):
            print_status(f"File does not exist: {file_path}", "error")
            return False

        # Get bug and project
        bug = self._get_bug()
        project = self._get_project()

        # Read the original description content BEFORE formatting
        # (for use in ChangeSpec DESCRIPTION field)
        with open(file_path, encoding="utf-8") as f:
            original_description = f.read().strip()

        # Get parent branch name BEFORE creating the commit
        parent_branch = _get_parent_branch_name()

        # Determine the full CL name (with project prefix)
        full_name = self.cl_name
        if not self.cl_name.startswith(f"{project}_"):
            full_name = f"{project}_{self.cl_name}"

        # Check if we should add a ChangeSpec after commit
        should_add_changespec = _project_file_exists(
            project
        ) and not _changespec_exists(project, full_name)

        # Format CL description
        print_status(
            "Formatting CL description with project tag and metadata.", "progress"
        )
        _format_cl_description(file_path, project, bug)

        # Run hg addremove (necessary when adding new / deleting old files)
        print_status("Running hg addremove...", "progress")
        addremove_result = run_shell_command("hg addremove", capture_output=True)
        if addremove_result.returncode != 0:
            print_status(f"hg addremove failed: {addremove_result.stderr}", "warning")
            # Continue anyway, as this is not always required

        # Create the commit
        print_status(f"Creating Mercurial commit with name: {full_name}", "progress")
        commit_cmd = f'hg commit --name "{full_name}" --logfile "{file_path}"'
        commit_result = run_shell_command(commit_cmd, capture_output=True)

        if commit_result.returncode != 0:
            print_status(
                f"Failed to create Mercurial commit: {commit_result.stderr}", "error"
            )
            self._cleanup_temp_file(file_path)
            return False

        # Run hg fix
        print_status("Running hg fix...", "progress")
        fix_result = run_shell_command("hg fix", capture_output=True)
        if fix_result.returncode != 0:
            print_status(f"hg fix failed: {fix_result.stderr}", "warning")
            # Continue anyway

        # Run hg upload tree
        print_status("Running hg upload tree...", "progress")
        upload_result = run_shell_command("hg upload tree", capture_output=True)
        if upload_result.returncode != 0:
            print_status(f"hg upload tree failed: {upload_result.stderr}", "warning")
            # Continue anyway

        # Remove bb/branch_name.txt if it exists
        branch_name_file = "bb/branch_name.txt"
        if os.path.exists(branch_name_file):
            os.remove(branch_name_file)
            print_status(f"Removed {branch_name_file}", "info")

        # Retrieve CL number (display to user)
        print_status("Retrieving CL number...", "progress")
        branch_number_result = run_shell_command("branch_number", capture_output=False)
        if branch_number_result.returncode != 0:
            print_status("Failed to retrieve CL number.", "error")
            self._cleanup_temp_file(file_path)
            return False

        # Add ChangeSpec to project file if conditions are met
        if should_add_changespec:
            cl_number = _get_cl_number()
            if cl_number:
                cl_url = f"http://cl/{cl_number}"
                print_status(
                    f"Adding ChangeSpec to project file for {project}...", "progress"
                )
                if _add_changespec_to_project_file(
                    project=project,
                    cl_name=full_name,
                    description=original_description,
                    parent=parent_branch,
                    cl_url=cl_url,
                ):
                    print_status(
                        f"ChangeSpec '{full_name}' added to project file.", "success"
                    )
                else:
                    print_status("Failed to add ChangeSpec to project file.", "warning")
            else:
                print_status(
                    "Could not get CL number for ChangeSpec creation.", "warning"
                )

        # Clean up temp file on success
        self._cleanup_temp_file(file_path)

        print_status("Commit workflow completed successfully!", "success")
        return True

    def _cleanup_temp_file(self, file_path: str) -> None:
        """Clean up the temporary file if we created one."""
        if self._temp_file_created and os.path.exists(file_path):
            os.unlink(file_path)


def main() -> NoReturn:
    """Main entry point for the commit workflow (standalone execution)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Create a Mercurial commit with formatted CL description and metadata tags."
    )
    parser.add_argument(
        "cl_name",
        help='CL name to use for the commit (e.g., "baz_feature"). The project name '
        'will be automatically prepended if not already present (e.g., "foobar_baz_feature").',
    )
    parser.add_argument(
        "file_path",
        nargs="?",
        help="Path to the file containing the CL description. "
        "If not provided, vim will be opened to write the commit message.",
    )
    parser.add_argument(
        "-b",
        "--bug",
        help="Bug number to include in the metadata tags (e.g., '12345'). "
        "Defaults to the output of the 'branch_bug' command.",
    )
    parser.add_argument(
        "-p",
        "--project",
        help="Project name to prepend to the CL description (e.g., 'foobar'). "
        "Defaults to the output of the 'workspace_name' command.",
    )

    args = parser.parse_args()

    workflow = CommitWorkflow(
        cl_name=args.cl_name,
        file_path=args.file_path,
        bug=args.bug,
        project=args.project,
    )
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
