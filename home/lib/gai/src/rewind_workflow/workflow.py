"""RewindWorkflow class for rewinding to a previous COMMITS entry."""

import os
import subprocess

from ace.changespec import ChangeSpec
from ace.hooks.processes import kill_and_persist_all_running_processes
from ace.operations import update_to_changespec
from commit_utils import run_bb_hg_clean
from rich_utils import print_status
from running_field import (
    claim_workspace,
    get_first_available_axe_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from workflow_utils import get_changespec_from_file

from .renumber import rewind_commit_entries


class RewindWorkflow:
    """A workflow for rewinding to a previous COMMITS entry."""

    def __init__(
        self,
        cl_name: str,
        project_file: str,
        selected_entry_num: int,
    ) -> None:
        """Initialize the rewind workflow.

        Args:
            cl_name: The CL name.
            project_file: Path to the project file.
            selected_entry_num: The entry number to rewind to.
        """
        self._cl_name = cl_name
        self._project_file = os.path.expanduser(project_file)
        self._selected_entry_num = selected_entry_num

    def run(self) -> tuple[bool, str]:
        """Run the rewind workflow.

        Returns:
            Tuple of (success, message).
        """
        project_file = self._project_file
        cl_name = self._cl_name
        selected_entry_num = self._selected_entry_num

        if not os.path.isfile(project_file):
            return (False, f"Project file not found: {project_file}")

        # Get the ChangeSpec upfront for validation
        changespec = get_changespec_from_file(project_file, cl_name)
        if not changespec:
            return (False, f"ChangeSpec not found: {cl_name}")

        # Extract project basename
        project = os.path.basename(os.path.dirname(project_file))

        # Validate entry exists and get all numeric entries
        numeric_entries = [e for e in (changespec.commits or []) if not e.is_proposed]
        entry_nums = {e.number for e in numeric_entries}

        if selected_entry_num not in entry_nums:
            return (False, f"Entry ({selected_entry_num}) not found")

        # Get entries after selected (need at least one)
        entries_after = [e for e in numeric_entries if e.number > selected_entry_num]
        if not entries_after:
            return (False, f"No entries after ({selected_entry_num})")

        # Validate selected entry has DIFF
        selected_entry = next(
            (e for e in numeric_entries if e.number == selected_entry_num), None
        )
        if not selected_entry or not selected_entry.diff:
            return (False, f"Entry ({selected_entry_num}) has no DIFF path")

        # Kill running processes before rewind
        self._kill_running_processes(changespec, project_file, cl_name)

        # Claim an available workspace
        workspace_num = get_first_available_axe_workspace(project_file)
        workspace_dir, workspace_suffix = get_workspace_directory_for_num(
            workspace_num, project
        )

        # Claim the workspace
        claim_success = claim_workspace(
            project_file,
            workspace_num,
            "rewind",
            os.getpid(),
            cl_name,
        )
        if not claim_success:
            return (False, "Failed to claim workspace")

        if workspace_suffix:
            print_status(f"Using workspace share: {workspace_suffix}", "progress")

        # Save original directory
        original_dir = os.getcwd()

        try:
            # Change to workspace directory
            os.chdir(workspace_dir)
            print_status(f"Changed to workspace: {workspace_dir}", "progress")

            # Clean workspace before switching branches
            clean_success, clean_error = run_bb_hg_clean(
                workspace_dir, f"{cl_name}-rewind"
            )
            if not clean_success:
                print_status(f"Warning: bb_hg_clean failed: {clean_error}", "warning")

            # Update to the changespec branch
            print_status(f"Updating to branch: {cl_name}", "progress")
            success, error_msg = update_to_changespec(
                changespec, revision=cl_name, workspace_dir=workspace_dir
            )
            if not success:
                return (False, f"Failed to update to branch: {error_msg}")

            # Collect diffs to rewind (entries after N where N = selected_entry_num)
            diff_files: list[str] = []
            for entry in sorted(numeric_entries, key=lambda e: e.number):
                if entry.number > selected_entry_num:
                    if entry.diff:
                        diff_files.append(os.path.expanduser(entry.diff))

            if not diff_files:
                return (False, "No diff files found to rewind")

            # Apply diffs in REVERSE order using gai_rewind
            diff_files_reversed = list(reversed(diff_files))
            print_status(f"Rewinding {len(diff_files_reversed)} diff(s)...", "progress")

            try:
                result = subprocess.run(
                    ["gai_rewind"] + diff_files_reversed,
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if result.returncode != 0:
                    error_output = (result.stderr or result.stdout).strip()
                    return (False, f"gai_rewind failed: {error_output}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                return (False, f"gai_rewind error: {e}")

            print_status("Diffs rewound successfully", "success")

            # CRITICAL: Run bb_hg_amend
            print_status("Amending commit...", "progress")
            amend_msg = f"[rewind] ({selected_entry_num})"
            try:
                result = subprocess.run(
                    ["bb_hg_amend", amend_msg],
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if result.returncode != 0:
                    error_output = (result.stderr or result.stdout).strip()
                    # CRITICAL FAILURE - halt and alert user
                    return (
                        False,
                        f"bb_hg_amend failed - requires manual intervention: {error_output}",
                    )
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                return (False, f"bb_hg_amend error: {e}")

            print_status("Commit amended", "success")

            # Update ChangeSpec with renumbering
            print_status("Updating ChangeSpec entries...", "progress")
            if rewind_commit_entries(
                project_file,
                cl_name,
                selected_entry_num,
            ):
                print_status("ChangeSpec entries updated", "success")
            else:
                return (False, "Failed to update ChangeSpec entries")

            return (True, f"Successfully rewound to entry ({selected_entry_num})")

        finally:
            # Always restore original directory and release workspace
            os.chdir(original_dir)
            release_workspace(project_file, workspace_num, "rewind", cl_name)

    def _kill_running_processes(
        self,
        changespec: ChangeSpec,
        project_file: str,
        cl_name: str,
    ) -> None:
        """Kill any running hook/agent/mentor processes before rewind.

        Args:
            changespec: The ChangeSpec object.
            project_file: Path to the project file.
            cl_name: The CL name.
        """
        kill_and_persist_all_running_processes(
            changespec,
            project_file,
            cl_name,
            "Killed for rewind operation",
            log_fn=lambda msg: print_status(msg, "progress"),
        )
