"""Workflow for amending Mercurial commits with HISTORY tracking."""

import os
import subprocess
import sys
from typing import NoReturn

from history_utils import add_history_entry, save_diff
from rich_utils import print_status
from shared_utils import run_shell_command
from work.changespec import ChangeSpec, parse_project_file
from work.hooks import add_test_target_hooks_to_changespec
from workflow_base import BaseWorkflow


def _get_project_file_path(project: str) -> str:
    """Get the path to the project file for a given project.

    Args:
        project: Project name.

    Returns:
        Path to the project file (~/.gai/projects/<project>/<project>.gp).
    """
    return os.path.expanduser(f"~/.gai/projects/{project}/{project}.gp")


def _get_cl_name_from_branch() -> str | None:
    """Get the current CL name from branch_name command.

    Returns:
        The CL name, or None if not on a branch.
    """
    result = run_shell_command("branch_name", capture_output=True)
    if result.returncode != 0:
        return None
    branch_name = result.stdout.strip()
    return branch_name if branch_name else None


def _get_project_from_workspace() -> str | None:
    """Get the current project name from workspace_name command.

    Returns:
        The project name, or None if command fails.
    """
    result = run_shell_command("workspace_name", capture_output=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _get_changed_test_targets() -> str | None:
    """Get test targets from changed files in the current branch.

    Calls the `changed_test_targets` script to get Blaze test targets
    for files that have changed in the current branch.

    Returns:
        Space-separated test targets string, or None if no targets found
        or the command fails.
    """
    try:
        result = subprocess.run(
            ["changed_test_targets"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            targets = result.stdout.strip()
            if targets:
                return targets
    except Exception:
        pass
    return None


def _get_changespec_from_file(project_file: str, cl_name: str) -> ChangeSpec | None:
    """Get a ChangeSpec from a project file by name.

    Args:
        project_file: Path to the project file.
        cl_name: The CL name to look for.

    Returns:
        The ChangeSpec if found, None otherwise.
    """
    changespecs = parse_project_file(project_file)
    for cs in changespecs:
        if cs.name == cl_name:
            return cs
    return None


class AmendWorkflow(BaseWorkflow):
    """A workflow for amending Mercurial commits with HISTORY tracking."""

    def __init__(
        self,
        note: str,
        chat_path: str | None = None,
        timestamp: str | None = None,
    ) -> None:
        """Initialize the amend workflow.

        Args:
            note: The note for the HISTORY entry.
            chat_path: Optional path to the chat file for this amend.
            timestamp: Optional shared timestamp for synced chat/diff files.
        """
        self._note = note
        self._chat_path = chat_path
        self._timestamp = timestamp

    @property
    def name(self) -> str:
        return "amend"

    @property
    def description(self) -> str:
        return "Amend the current commit with HISTORY tracking"

    def run(self) -> bool:
        """Run the amend workflow.

        Returns:
            True if the workflow completed successfully, False otherwise.
        """
        # Get current branch/CL name
        cl_name = _get_cl_name_from_branch()
        if not cl_name:
            print_status(
                "Not on a branch. Use 'gai commit' to create a new commit.", "error"
            )
            return False

        # Get project name
        project = _get_project_from_workspace()
        if not project:
            print_status(
                "Failed to get project name from 'workspace_name' command.", "error"
            )
            return False

        # Save the diff before amending
        print_status("Saving diff before amend...", "progress")
        diff_path = save_diff(cl_name, timestamp=self._timestamp)
        if not diff_path:
            print_status("No uncommitted changes to amend.", "warning")
            return True  # Not an error, just nothing to do

        # Run bb_hg_amend
        print_status(f"Amending commit with note: {self._note}", "progress")
        try:
            result = subprocess.run(
                ["bb_hg_amend", self._note],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print_status(f"bb_hg_amend failed: {result.stderr}", "error")
                return False
        except FileNotFoundError:
            print_status("bb_hg_amend command not found", "error")
            return False

        # Add HISTORY entry
        project_file = _get_project_file_path(project)
        if os.path.isfile(project_file):
            print_status("Adding HISTORY entry...", "progress")
            success = add_history_entry(
                project_file=project_file,
                cl_name=cl_name,
                note=self._note,
                diff_path=diff_path,
                chat_path=self._chat_path,
            )
            if success:
                print_status("HISTORY entry added successfully.", "success")
            else:
                print_status("Failed to add HISTORY entry.", "warning")

            # Add any new test target hooks from changed_test_targets
            test_targets = _get_changed_test_targets()
            if test_targets:
                print_status("Checking for new test target hooks...", "progress")
                # Parse test targets (space-separated)
                target_list = test_targets.split()
                # Get existing hooks from the ChangeSpec
                changespec = _get_changespec_from_file(project_file, cl_name)
                existing_hooks = changespec.hooks if changespec else None
                if add_test_target_hooks_to_changespec(
                    project_file, cl_name, target_list, existing_hooks
                ):
                    print_status("Test target hooks updated.", "success")
                else:
                    print_status("Failed to update test target hooks.", "warning")
        else:
            print_status(
                f"Project file not found: {project_file}. Skipping HISTORY entry.",
                "warning",
            )

        print_status("Amend completed successfully!", "success")
        return True


def main() -> NoReturn:
    """Main entry point for the amend workflow (standalone execution)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Amend the current Mercurial commit with HISTORY tracking."
    )
    parser.add_argument(
        "note",
        help='The note for this amend (e.g., "Fixed typo in README").',
    )
    parser.add_argument(
        "--chat",
        dest="chat_path",
        help="Path to the chat file associated with this amend.",
    )

    args = parser.parse_args()

    workflow = AmendWorkflow(
        note=args.note,
        chat_path=args.chat_path,
    )
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
