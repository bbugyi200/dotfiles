"""Workflow for amending Mercurial commits with HISTORY tracking."""

import os
import subprocess
import sys
from typing import NoReturn

from ace.hooks import add_test_target_hooks_to_changespec
from history_utils import (
    add_history_entry,
    add_proposed_history_entry,
    clean_workspace,
    save_diff,
)
from rich_utils import print_status
from workflow_base import BaseWorkflow
from workflow_utils import (
    get_changed_test_targets,
    get_changespec_from_file,
    get_cl_name_from_branch,
    get_project_file_path,
    get_project_from_workspace,
)


class AmendWorkflow(BaseWorkflow):
    """A workflow for amending Mercurial commits with HISTORY tracking."""

    def __init__(
        self,
        note: str,
        chat_path: str | None = None,
        timestamp: str | None = None,
        propose: bool = False,
        target_dir: str | None = None,
        project_file: str | None = None,
    ) -> None:
        """Initialize the amend workflow.

        Args:
            note: The note for the HISTORY entry.
            chat_path: Optional path to the chat file for this amend.
            timestamp: Optional shared timestamp for synced chat/diff files.
            propose: If True, create a proposed entry instead of amending.
            target_dir: Optional directory to run commands in (for propose mode).
            project_file: Optional path to project file. If not provided,
                will try to infer from workspace_name command.
        """
        self._note = note
        self._chat_path = chat_path
        self._timestamp = timestamp
        self._propose = propose
        self._target_dir = target_dir
        self._project_file = project_file

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
        cl_name = get_cl_name_from_branch()
        if not cl_name:
            print_status(
                "Not on a branch. Use 'gai commit' to create a new commit.", "error"
            )
            return False

        # Get project file - prefer explicit path over workspace inference
        if self._project_file:
            project_file = os.path.expanduser(self._project_file)
        else:
            project = get_project_from_workspace()
            if not project:
                print_status(
                    "Failed to get project name from 'workspace_name' command.",
                    "error",
                )
                return False
            project_file = get_project_file_path(project)

        # Save the diff before amending
        action = "propose" if self._propose else "amend"
        print_status(f"Saving diff before {action}...", "progress")
        diff_path = save_diff(
            cl_name, target_dir=self._target_dir, timestamp=self._timestamp
        )
        if not diff_path:
            print_status(f"No uncommitted changes to {action}.", "warning")
            return True  # Not an error, just nothing to do

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
            test_targets = get_changed_test_targets()
            if test_targets:
                print_status("Checking for new test target hooks...", "progress")
                # Parse test targets (space-separated)
                target_list = test_targets.split()
                # Get existing hooks from the ChangeSpec
                changespec = get_changespec_from_file(project_file, cl_name)
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
