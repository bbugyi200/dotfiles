"""RewindWorkflow class for rewinding to a previous COMMITS entry."""

import os
import subprocess

from ace.changespec import ChangeSpec
from ace.comments.operations import (
    mark_comment_agents_as_killed,
    update_changespec_comments_field,
)
from ace.hooks.execution import update_changespec_hooks_field
from ace.hooks.processes import (
    kill_running_agent_processes,
    kill_running_hook_processes,
    kill_running_mentor_processes,
    mark_hook_agents_as_killed,
    mark_hooks_as_killed,
    mark_mentor_agents_as_killed,
)
from ace.mentors import update_changespec_mentors_field
from ace.operations import update_to_changespec
from commit_utils import run_bb_hg_clean
from rich_utils import print_status
from running_field import (
    claim_workspace,
    get_claimed_workspaces,
    get_first_available_axe_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from workflow_utils import get_changespec_from_file

from .renumber import rewind_commit_entries


def _extract_mentor_workflow_from_suffix(suffix: str) -> str | None:
    """Extract workflow name from mentor suffix.

    Args:
        suffix: Mentor suffix in format "mentor_{name}-{PID}-{timestamp}"

    Returns:
        Workflow name in format "axe(mentor)-{name}-{timestamp}" or None
    """
    import re

    match = re.match(r"^mentor_(.+)-\d+-(\d{6}_\d{6})$", suffix)
    if match:
        mentor_name = match.group(1)
        timestamp = match.group(2)
        return f"axe(mentor)-{mentor_name}-{timestamp}"
    return None


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

        # Kill any running hook processes
        killed_processes = kill_running_hook_processes(changespec)
        if killed_processes:
            print_status(
                f"Killed {len(killed_processes)} running hook process(es)",
                "progress",
            )
            if changespec.hooks:
                updated_hooks = mark_hooks_as_killed(
                    changespec.hooks,
                    killed_processes,
                    "Killed for rewind operation",
                )
                update_changespec_hooks_field(project_file, cl_name, updated_hooks)

        # Kill any running agent processes
        killed_hook_agents, killed_comment_agents = kill_running_agent_processes(
            changespec
        )
        total_killed_agents = len(killed_hook_agents) + len(killed_comment_agents)
        if total_killed_agents:
            print_status(
                f"Killed {total_killed_agents} running agent process(es)",
                "progress",
            )
            if killed_hook_agents and changespec.hooks:
                updated_hooks = mark_hook_agents_as_killed(
                    changespec.hooks, killed_hook_agents
                )
                update_changespec_hooks_field(project_file, cl_name, updated_hooks)
            if killed_comment_agents and changespec.comments:
                updated_comments = mark_comment_agents_as_killed(
                    changespec.comments, killed_comment_agents
                )
                update_changespec_comments_field(
                    project_file, cl_name, updated_comments
                )

        # Kill any running mentor processes
        killed_mentors = kill_running_mentor_processes(changespec)
        if killed_mentors:
            print_status(
                f"Killed {len(killed_mentors)} running mentor process(es)",
                "progress",
            )
            if changespec.mentors:
                updated_mentors = mark_mentor_agents_as_killed(
                    changespec.mentors, killed_mentors
                )
                update_changespec_mentors_field(project_file, cl_name, updated_mentors)

            # Release workspaces claimed by killed mentor processes
            for _entry, status_line, _pid in killed_mentors:
                if not status_line.suffix:
                    continue

                workflow = _extract_mentor_workflow_from_suffix(status_line.suffix)
                if not workflow:
                    continue

                for claim in get_claimed_workspaces(project_file):
                    if claim.workflow == workflow and claim.cl_name == cl_name:
                        release_workspace(
                            project_file, claim.workspace_num, workflow, cl_name
                        )
                        print_status(
                            f"Released workspace #{claim.workspace_num} for killed mentor",
                            "progress",
                        )
                        break
