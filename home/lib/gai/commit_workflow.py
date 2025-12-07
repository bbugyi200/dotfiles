"""Workflow for creating Mercurial commits with formatted CL descriptions."""

import os
import sys
from typing import NoReturn

from rich_utils import print_status
from shared_utils import run_shell_command
from workflow_base import BaseWorkflow


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
        file_path: str,
        cl_name: str,
        bug: str | None = None,
        project: str | None = None,
    ) -> None:
        """Initialize the commit workflow.

        Args:
            file_path: Path to the file containing the CL description.
            cl_name: CL name to use for the commit (e.g., "baz_feature").
            bug: Bug number to include in metadata. Defaults to output of 'branch_bug'.
            project: Project name to prepend. Defaults to output of 'workspace_name'.
        """
        self.file_path = file_path
        self.cl_name = cl_name
        self._bug = bug
        self._project = project

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
        # Validate file exists
        if not os.path.isfile(self.file_path):
            print_status(f"File does not exist: {self.file_path}", "error")
            return False

        # Get bug and project
        bug = self._get_bug()
        project = self._get_project()

        # Format CL description
        print_status(
            "Formatting CL description with project tag and metadata.", "progress"
        )
        _format_cl_description(self.file_path, project, bug)

        # Run hg addremove (necessary when adding new / deleting old files)
        print_status("Running hg addremove...", "progress")
        addremove_result = run_shell_command("hg addremove", capture_output=True)
        if addremove_result.returncode != 0:
            print_status(f"hg addremove failed: {addremove_result.stderr}", "warning")
            # Continue anyway, as this is not always required

        # Prepend project name if not already present
        full_name = self.cl_name
        if not self.cl_name.startswith(f"{project}_"):
            full_name = f"{project}_{self.cl_name}"

        # Create the commit
        print_status(f"Creating Mercurial commit with name: {full_name}", "progress")
        commit_cmd = f'hg commit --name "{full_name}" --logfile "{self.file_path}"'
        commit_result = run_shell_command(commit_cmd, capture_output=True)

        if commit_result.returncode != 0:
            print_status(
                f"Failed to create Mercurial commit: {commit_result.stderr}", "error"
            )
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

        # Retrieve CL number
        print_status("Retrieving CL number...", "progress")
        branch_number_result = run_shell_command("branch_number", capture_output=False)
        if branch_number_result.returncode != 0:
            print_status("Failed to retrieve CL number.", "error")
            return False

        print_status("Commit workflow completed successfully!", "success")
        return True


def main() -> NoReturn:
    """Main entry point for the commit workflow (standalone execution)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Create a Mercurial commit with formatted CL description and metadata tags."
    )
    parser.add_argument(
        "file_path",
        help="Path to the file containing the CL description.",
    )
    parser.add_argument(
        "name",
        help='CL name to use for the commit (e.g., "baz_feature"). The project name '
        'will be automatically prepended if not already present (e.g., "foobar_baz_feature").',
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
        file_path=args.file_path,
        cl_name=args.name,
        bug=args.bug,
        project=args.project,
    )
    success = workflow.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
