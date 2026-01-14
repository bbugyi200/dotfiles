"""CommitWorkflow class for creating Mercurial commits."""

import os
import sys
import tempfile

from ace.constants import REQUIRED_CHANGESPEC_HOOKS
from commit_utils import add_commit_entry, get_next_commit_number, save_diff
from rich_utils import print_status
from shared_utils import run_shell_command
from workflow_base import BaseWorkflow
from workflow_utils import get_initial_hooks_for_changespec, get_project_file_path

from .branch_info import (
    get_cl_number,
    get_existing_changespec_description,
    get_parent_branch_name,
)
from .changespec_operations import (
    add_changespec_to_project_file,
    ensure_required_hooks,
    update_existing_changespec,
)
from .changespec_queries import changespec_exists, project_file_exists
from .cl_formatting import format_cl_description
from .editor_utils import open_editor_for_commit_message
from .project_file_utils import create_project_file


class CommitWorkflow(BaseWorkflow):
    """A workflow for creating Mercurial commits with formatted CL descriptions."""

    def __init__(
        self,
        cl_name: str,
        file_path: str | None = None,
        bug: str | None = None,
        project: str | None = None,
        chat_path: str | None = None,
        timestamp: str | None = None,
        end_timestamp: str | None = None,
        note: str | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize the commit workflow.

        Args:
            cl_name: CL name to use for the commit (e.g., "baz_feature").
            file_path: Path to the file containing the CL description. If None,
                vim will be opened for the user to write a commit message.
            bug: Bug number to include in metadata. Defaults to output of 'branch_bug'.
            project: Project name to prepend. Defaults to output of 'workspace_name'.
            chat_path: Path to the chat file for COMMITS entry.
            timestamp: Shared timestamp for synced chat/diff files.
            end_timestamp: End timestamp for duration calculation.
            note: Custom note for the initial COMMITS entry. Defaults to 'Initial Commit'.
            message: Commit message to use directly (mutually exclusive with file_path).
        """
        self.cl_name = cl_name
        self._file_path = file_path
        self._bug = bug
        self._project = project
        self._chat_path = chat_path
        self._timestamp = timestamp
        self._end_timestamp = end_timestamp
        self._note = note
        self._message = message
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
        # Get bug and project first (needed for ChangeSpec lookup)
        bug = self._get_bug()
        project = self._get_project()

        # Determine the full CL name (with project prefix)
        full_name = self.cl_name
        if not self.cl_name.startswith(f"{project}_"):
            full_name = f"{project}_{self.cl_name}"

        # Check if ChangeSpec already exists (for restore workflow)
        existing_changespec = changespec_exists(project, full_name)
        existing_description = None
        if existing_changespec:
            existing_description = get_existing_changespec_description(
                project, full_name
            )

        # Get file path - either from argument, message, existing ChangeSpec, or editor
        file_path = self._file_path
        if file_path is None:
            if self._message:
                # Use message provided via -m flag
                fd, file_path = tempfile.mkstemp(suffix=".txt", prefix="gai_commit_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(self._message)
                self._temp_file_created = True
            elif existing_description:
                # Use description from existing ChangeSpec
                fd, file_path = tempfile.mkstemp(suffix=".txt", prefix="gai_commit_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(existing_description)
                self._temp_file_created = True
                print_status("Using description from existing ChangeSpec.", "info")
            else:
                file_path = open_editor_for_commit_message()
                if file_path is None:
                    return False
                self._temp_file_created = True
        elif not os.path.isfile(file_path):
            print_status(f"File does not exist: {file_path}", "error")
            return False

        # Read the original description content BEFORE formatting
        # (for use in ChangeSpec DESCRIPTION field)
        with open(file_path, encoding="utf-8") as f:
            original_description = f.read().strip()

        # Get parent branch name BEFORE creating the commit
        parent_branch = get_parent_branch_name()

        # Determine what to do with ChangeSpec after commit
        # - If ChangeSpec exists: update it
        # - If project file exists but no ChangeSpec: add new ChangeSpec
        # - If project file doesn't exist: create it and add new ChangeSpec
        should_update_changespec = existing_changespec
        should_add_changespec = not existing_changespec

        # Save the diff before committing (for COMMITS entry)
        print_status("Saving diff before commit...", "progress")
        diff_path = save_diff(full_name, timestamp=self._timestamp)

        # Format CL description
        print_status(
            "Formatting CL description with project tag and metadata.", "progress"
        )
        format_cl_description(file_path, project, bug)

        # Note: hg addremove is now handled by save_diff() above

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

        # Handle ChangeSpec updates
        cl_number = get_cl_number()
        if cl_number:
            cl_url = f"http://cl/{cl_number}"

            if should_update_changespec:
                # Update existing ChangeSpec's STATUS and CL fields
                print_status(
                    f"Updating existing ChangeSpec '{full_name}'...", "progress"
                )
                if update_existing_changespec(project, full_name, cl_url):
                    print_status(
                        f"ChangeSpec '{full_name}' updated successfully.", "success"
                    )
                    # Ensure required hooks are present (backward compatibility)
                    project_file = get_project_file_path(project)
                    ensure_required_hooks(
                        project_file, full_name, REQUIRED_CHANGESPEC_HOOKS
                    )
                else:
                    print_status("Failed to update existing ChangeSpec.", "warning")
            elif should_add_changespec:
                # Create project file if it doesn't exist
                if not project_file_exists(project):
                    create_project_file(project)

                # Get all initial hooks (required + test targets) in a single call
                print_status("Gathering hooks for new ChangeSpec...", "progress")
                initial_hooks = get_initial_hooks_for_changespec()

                # Add new ChangeSpec to project file (with all hooks atomically)
                print_status(
                    f"Adding ChangeSpec to project file for {project}...", "progress"
                )
                # Format bug as URL for ChangeSpec
                bug_url = f"http://b/{bug}" if bug else None
                if add_changespec_to_project_file(
                    project=project,
                    cl_name=full_name,
                    description=original_description,
                    parent=parent_branch,
                    cl_url=cl_url,
                    initial_hooks=initial_hooks,
                    bug=bug_url,
                ):
                    print_status(
                        f"ChangeSpec '{full_name}' added to project file.", "success"
                    )
                else:
                    print_status("Failed to add ChangeSpec to project file.", "warning")
        else:
            print_status("Could not get CL number for ChangeSpec update.", "warning")

        # Add initial COMMITS entry (only if no existing history entries)
        project_file = get_project_file_path(project)
        if os.path.isfile(project_file) and diff_path:
            # Check if this would be the first history entry
            with open(project_file, encoding="utf-8") as f:
                lines = f.readlines()
            next_num = get_next_commit_number(lines, full_name)
            if next_num == 1:
                print_status("Adding initial COMMITS entry...", "progress")
                history_note = self._note or "Initial Commit"
                if add_commit_entry(
                    project_file=project_file,
                    cl_name=full_name,
                    note=history_note,
                    diff_path=diff_path,
                    chat_path=self._chat_path,
                    end_timestamp=self._end_timestamp,
                ):
                    print_status("COMMITS entry added successfully.", "success")
                else:
                    print_status("Failed to add COMMITS entry.", "warning")

        # Clean up temp file on success
        self._cleanup_temp_file(file_path)

        print_status("Commit workflow completed successfully!", "success")
        return True

    def _cleanup_temp_file(self, file_path: str) -> None:
        """Clean up the temporary file if we created one."""
        if self._temp_file_created and os.path.exists(file_path):
            os.unlink(file_path)
