"""Mentor starting and workspace management for the loop workflow."""

import os
import subprocess
import time
from collections.abc import Callable

from commit_utils import run_bb_hg_clean
from gai_utils import ensure_gai_directory, get_gai_directory, make_safe_filename
from mentor_config import MentorProfileConfig
from running_field import (
    claim_workspace,
    get_first_available_loop_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from status_state_machine import remove_workspace_suffix

from ..changespec import ChangeSpec
from ..hooks import generate_timestamp
from ..mentors import set_mentor_status

# Type alias for logging callback
LogCallback = Callable[[str, str | None], None]


def _get_mentor_output_path(name: str, mentor_name: str, timestamp: str) -> str:
    """Get the output file path for a mentor run.

    Args:
        name: The ChangeSpec name.
        mentor_name: The mentor name.
        timestamp: The timestamp in YYmmdd_HHMMSS format.

    Returns:
        Full path to the mentor output file.
    """
    mentors_dir = ensure_gai_directory("mentors")
    safe_name = make_safe_filename(name)
    filename = f"{safe_name}-{mentor_name}-{timestamp}.txt"
    return os.path.join(mentors_dir, filename)


def get_mentor_chat_path(cl_name: str, mentor_name: str, timestamp: str) -> str:
    """Get the chat file path for a mentor run.

    The chat file is created by invoke_agent() when the mentor runs.

    Args:
        cl_name: The ChangeSpec name (used as branch_or_workspace).
        mentor_name: The mentor name.
        timestamp: The timestamp in YYmmdd_HHMMSS format.

    Returns:
        Full path to the chat file (e.g., ~/.gai/chats/{cl_name}-mentor_{mentor_name}-{timestamp}.md)
    """
    chats_dir = get_gai_directory("chats")
    # Format matches chat_history._generate_chat_filename() with:
    # - branch_or_workspace = cl_name
    # - workflow = "mentor-{mentor_name}" (normalized to "mentor_{mentor_name}")
    filename = f"{cl_name}-mentor_{mentor_name}-{timestamp}.md"
    return os.path.join(chats_dir, filename)


def _start_single_mentor(
    changespec: ChangeSpec,
    entry_id: str,
    profile: MentorProfileConfig,
    mentor_name: str,
    log: LogCallback,
) -> str | None:
    """Start a single mentor workflow as a background process.

    Args:
        changespec: The ChangeSpec to run mentor for.
        entry_id: The commit entry ID.
        profile: The mentor profile configuration.
        mentor_name: The specific mentor to run.
        log: Logging callback.

    Returns:
        Update message if started, None if failed.
    """
    project_basename = changespec.project_basename
    timestamp = generate_timestamp()

    # Claim a workspace
    workspace_num = get_first_available_loop_workspace(changespec.file_path)
    workflow_name = f"loop(mentor)-{mentor_name}-{timestamp}"

    if not claim_workspace(
        changespec.file_path,
        workspace_num,
        workflow_name,
        changespec.name,
    ):
        log(
            f"Warning: Failed to claim workspace for mentor {mentor_name} "
            f"on {changespec.name}",
            "yellow",
        )
        return None

    try:
        workspace_dir, _ = get_workspace_directory_for_num(
            workspace_num, project_basename
        )

        if not os.path.isdir(workspace_dir):
            log(f"Warning: Workspace directory not found: {workspace_dir}", "yellow")
            release_workspace(
                changespec.file_path,
                workspace_num,
                workflow_name,
                changespec.name,
            )
            return None

        # Clean workspace before switching branches
        clean_success, clean_error = run_bb_hg_clean(
            workspace_dir, f"{changespec.name}-mentor"
        )
        if not clean_success:
            log(f"Warning: bb_hg_clean failed: {clean_error}", "yellow")

        # Run bb_hg_update to switch to the ChangeSpec's branch
        try:
            result = subprocess.run(
                ["bb_hg_update", changespec.name],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                error_output = (
                    result.stderr.strip() or result.stdout.strip() or "no error output"
                )
                log(
                    f"Warning: bb_hg_update failed for {changespec.name} "
                    f"(cwd: {workspace_dir}): {error_output}",
                    "yellow",
                )
                release_workspace(
                    changespec.file_path,
                    workspace_num,
                    workflow_name,
                    changespec.name,
                )
                return None
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            log(
                f"Warning: bb_hg_update error for {changespec.name} "
                f"(cwd: {workspace_dir}): {e}",
                "yellow",
            )
            release_workspace(
                changespec.file_path,
                workspace_num,
                workflow_name,
                changespec.name,
            )
            return None

        # Get output file path
        output_path = _get_mentor_output_path(changespec.name, mentor_name, timestamp)

        # Build the runner script path (use abspath to handle relative __file__)
        runner_script = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
            "loop_mentor_runner.py",
        )

        # Start the background process and capture PID
        with open(output_path, "w") as output_file:
            proc = subprocess.Popen(
                [
                    "python3",
                    runner_script,
                    changespec.name,
                    changespec.file_path,
                    mentor_name,
                    workspace_dir,
                    output_path,
                    str(workspace_num),
                    workflow_name,
                    entry_id,
                    profile.name,
                    timestamp,  # Pass timestamp for chat file naming
                ],
                cwd=workspace_dir,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=os.environ,
            )
            pid = proc.pid

        # Set mentor status to RUNNING with timestamp
        set_mentor_status(
            changespec.file_path,
            changespec.name,
            entry_id,
            profile.name,
            mentor_name,
            status="RUNNING",
            timestamp=timestamp,
            suffix=f"mentor_{mentor_name}-{pid}-{timestamp}",
            suffix_type="running_agent",
        )

        return f"mentor {profile.name}:{mentor_name} -> RUNNING for ({entry_id})"

    except Exception as e:
        log(f"Warning: Error starting mentor {mentor_name}: {e}", "yellow")
        release_workspace(
            changespec.file_path,
            workspace_num,
            workflow_name,
            changespec.name,
        )
        return None


def start_mentors_for_profile(
    changespec: ChangeSpec,
    entry_id: str,
    profile: MentorProfileConfig,
    log: LogCallback,
    max_to_start: int,
    started_mentors: set[tuple[str, str]] | None = None,
) -> tuple[int, list[str]]:
    """Start mentor workflows for a profile.

    During WIP status, only mentors with run_on_wip=True will be started.

    Args:
        changespec: The ChangeSpec to run mentors for.
        entry_id: The commit entry ID.
        profile: The mentor profile configuration.
        log: Logging callback.
        max_to_start: Maximum number of mentors to start.
        started_mentors: Set of (profile_name, mentor_name) tuples that have
            already been started. If None, no mentors are skipped.

    Returns:
        Tuple of (number_started, update_messages).
    """
    updates: list[str] = []
    started = 0

    # Check if we're in WIP status (only run mentors with run_on_wip=True)
    is_wip_status = remove_workspace_suffix(changespec.status) == "WIP"

    # Start each mentor in the profile
    # Note: Profile entry is already added upfront by _add_matching_profiles_upfront()
    for mentor in profile.mentors:
        if started >= max_to_start:
            break

        # Skip mentors that have already been started
        if started_mentors and (profile.name, mentor.name) in started_mentors:
            continue

        # During WIP status, skip mentors without run_on_wip=True
        if is_wip_status and not mentor.run_on_wip:
            continue

        result = _start_single_mentor(changespec, entry_id, profile, mentor.name, log)
        if result:
            updates.append(result)
            started += 1

            # Small delay between mentor starts to ensure unique timestamps
            time.sleep(1)

    return started, updates
