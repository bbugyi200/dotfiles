"""Shared utilities for axe runner scripts."""

import signal
import subprocess
import sys
from collections.abc import Callable

from ace.changespec import ChangeSpec, parse_project_file
from chat_history import save_chat_history
from commit_utils import add_proposed_commit_entry, clean_workspace, save_diff
from running_field import release_workspace

# Global state for SIGTERM handler
_killed_state: dict[str, bool] = {"killed": False}


def was_killed() -> bool:
    """Check if the process received SIGTERM."""
    return _killed_state["killed"]


def install_sigterm_handler(description: str = "process") -> None:
    """Install a SIGTERM handler that sets killed flag and exits gracefully.

    The handler uses sys.exit() instead of re-raising SIGTERM so that
    finally blocks run, ensuring workspace cleanup happens before exit.

    Args:
        description: What was killed (e.g., "agent", "mentor", "workflow").
    """

    def _handler(_signum: int, _frame: object) -> None:
        _killed_state["killed"] = True
        print(f"\nReceived SIGTERM - {description} was killed", file=sys.stderr)
        sys.exit(128 + signal.SIGTERM)

    signal.signal(signal.SIGTERM, _handler)


def prepare_workspace(
    workspace_dir: str,
    cl_name: str,
    update_target: str,
    backup_suffix: str = "ace",
) -> bool:
    """Clean and update workspace before running agent or workflow.

    Args:
        workspace_dir: The workspace directory.
        cl_name: Display name for the CL/project (used for backup diff name).
        update_target: What to checkout (CL name or "p4head").
        backup_suffix: Suffix appended to cl_name for the backup diff name
            (e.g., "ace" produces "{cl_name}-ace").

    Returns:
        True if successful, False otherwise.
    """
    from commit_utils import run_bb_hg_clean

    # Clean workspace (saves any existing changes to a diff file)
    print("Cleaning workspace...")
    success, error = run_bb_hg_clean(workspace_dir, f"{cl_name}-{backup_suffix}")
    if not success:
        print(f"bb_hg_clean failed: {error}", file=sys.stderr)
        return False

    # Update workspace to target
    print(f"Updating workspace to {update_target}...")
    try:
        result = subprocess.run(
            ["bb_hg_update", update_target],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            print(f"bb_hg_update failed: {error_msg}", file=sys.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("bb_hg_update timed out", file=sys.stderr)
        return False
    except Exception as e:
        print(f"bb_hg_update error: {e}", file=sys.stderr)
        return False

    print("Workspace ready")
    return True


def _check_for_local_changes() -> bool:
    """Check if there are uncommitted local changes.

    Returns:
        True if there are changes, False otherwise.
    """
    result = subprocess.run(
        ["branch_local_changes"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def create_proposal_from_changes(
    project_file: str,
    cl_name: str,
    workspace_dir: str,
    workflow_note: str,
    prompt: str,
    response: str,
    workflow: str,
    timestamp: str | None = None,
) -> tuple[str | None, int]:
    """Create a proposal from uncommitted changes.

    Args:
        project_file: Path to the project file.
        cl_name: The ChangeSpec name.
        workspace_dir: The workspace directory.
        workflow_note: Note for the history entry.
        prompt: The prompt used (for chat history).
        response: The response content (for chat history).
        workflow: The workflow name (for chat history).
        timestamp: Optional start timestamp for accurate duration calculation.

    Returns:
        Tuple of (proposal_id, exit_code). proposal_id is None on failure.
    """
    if not _check_for_local_changes():
        print("No changes detected")
        return None, 1

    print("Changes detected, creating proposal...")

    # Save chat history
    chat_path = save_chat_history(
        prompt=prompt,
        response=response,
        workflow=workflow,
        timestamp=timestamp,
    )

    # Save the diff
    diff_path = save_diff(cl_name, target_dir=workspace_dir)
    if not diff_path:
        print("Failed to save diff")
        return None, 1

    # Create proposed HISTORY entry
    success, entry_id = add_proposed_commit_entry(
        project_file=project_file,
        cl_name=cl_name,
        note=workflow_note,
        diff_path=diff_path,
        chat_path=chat_path,
    )

    if success and entry_id:
        print(f"Created proposal ({entry_id}): {workflow_note}")
        clean_workspace(workspace_dir)
        return entry_id, 0

    print("Failed to create proposal entry")
    return None, 1


def finalize_axe_runner(
    project_file: str,
    changespec_name: str,
    workspace_num: int,
    workflow_name: str,
    proposal_id: str | None,
    exit_code: int,
    update_suffix_fn: Callable[[ChangeSpec, str, str | None, int], None],
) -> None:
    """Common finalization logic for axe runners.

    Args:
        project_file: Path to the project file.
        changespec_name: Name of the ChangeSpec.
        workspace_num: Workspace number to release.
        workflow_name: Name of the workflow.
        proposal_id: Proposal ID if successful, None otherwise.
        exit_code: Exit code (0 for success).
        update_suffix_fn: Callback to update the suffix (hook or comment).
            Receives (changespec, project_file, proposal_id, exit_code).
    """
    # Update suffix based on result
    try:
        changespecs = parse_project_file(project_file)
        for cs in changespecs:
            if cs.name == changespec_name:
                update_suffix_fn(cs, project_file, proposal_id, exit_code)
                break
    except Exception as e:
        print(f"Warning: Failed to update suffix: {e}")

    # Release workspace
    try:
        release_workspace(
            project_file,
            workspace_num,
            workflow_name,
            changespec_name,
        )
        print(f"Released workspace #{workspace_num}")
    except Exception as e:
        print(f"Warning: Failed to release workspace: {e}")

    # Write completion marker
    print()
    print(f"===WORKFLOW_COMPLETE=== PROPOSAL_ID: {proposal_id} EXIT_CODE: {exit_code}")
