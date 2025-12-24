"""Workflow for amending Mercurial commits with HISTORY tracking."""

import os
import subprocess
import sys
from typing import NoReturn

from history_utils import (
    add_history_entry,
    add_proposed_history_entry,
    clean_workspace,
    save_diff,
)
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
        propose: bool = False,
        target_dir: str | None = None,
    ) -> None:
        """Initialize the amend workflow.

        Args:
            note: The note for the HISTORY entry.
            chat_path: Optional path to the chat file for this amend.
            timestamp: Optional shared timestamp for synced chat/diff files.
            propose: If True, create a proposed entry instead of amending.
            target_dir: Optional directory to run commands in (for propose mode).
        """
        self._note = note
        self._chat_path = chat_path
        self._timestamp = timestamp
        self._propose = propose
        self._target_dir = target_dir

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
        action = "propose" if self._propose else "amend"
        print_status(f"Saving diff before {action}...", "progress")
        diff_path = save_diff(
            cl_name, target_dir=self._target_dir, timestamp=self._timestamp
        )
        if not diff_path:
            print_status(f"No uncommitted changes to {action}.", "warning")
            return True  # Not an error, just nothing to do

        project_file = _get_project_file_path(project)

        if self._propose:
            # Propose mode: add proposed entry, clean workspace, skip amend
            return self._run_propose_mode(cl_name, project_file, diff_path)
        else:
            # Regular mode: amend commit
            return self._run_amend_mode(cl_name, project_file, diff_path)

    def _run_propose_mode(
        self, cl_name: str, project_file: str, diff_path: str
    ) -> bool:
        """Run the workflow in propose mode.

        Args:
            cl_name: The CL name.
            project_file: Path to the project file.
            diff_path: Path to the saved diff.

        Returns:
            True if successful, False otherwise.
        """
        if os.path.isfile(project_file):
            print_status("Adding proposed HISTORY entry...", "progress")
            success, entry_id = add_proposed_history_entry(
                project_file=project_file,
                cl_name=cl_name,
                note=self._note,
                diff_path=diff_path,
                chat_path=self._chat_path,
            )
            if success:
                print_status(
                    f"Proposed HISTORY entry ({entry_id}) added successfully.",
                    "success",
                )
            else:
                print_status("Failed to add proposed HISTORY entry.", "error")
                return False
        else:
            print_status(
                f"Project file not found: {project_file}. Cannot create proposal.",
                "error",
            )
            return False

        # Clean the workspace
        print_status("Cleaning workspace...", "progress")
        target_dir = self._target_dir or os.getcwd()
        if clean_workspace(target_dir):
            print_status("Workspace cleaned successfully.", "success")
        else:
            print_status("Failed to clean workspace.", "warning")

        print_status("Proposal created successfully!", "success")
        return True

    def _run_amend_mode(self, cl_name: str, project_file: str, diff_path: str) -> bool:
        """Run the workflow in regular amend mode.

        Args:
            cl_name: The CL name.
            project_file: Path to the project file.
            diff_path: Path to the saved diff.

        Returns:
            True if successful, False otherwise.
        """
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
    parser.add_argument(
        "--propose",
        action="store_true",
        help="Create a proposed HISTORY entry instead of amending. "
        "Saves the diff, adds a proposed entry (e.g., 2a), and cleans workspace.",
    )
    parser.add_argument(
        "--target-dir",
        dest="target_dir",
        help="Directory to run commands in (default: current directory).",
    )

    args = parser.parse_args()

    workflow = AmendWorkflow(
        note=args.note,
        chat_path=args.chat_path,
        propose=args.propose,
        target_dir=args.target_dir,
    )
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
