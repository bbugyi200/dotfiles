"""Shared utilities for loop runner scripts."""

import subprocess
from collections.abc import Callable

from ace.changespec import ChangeSpec, parse_project_file
from chat_history import save_chat_history
from history_utils import add_proposed_history_entry, clean_workspace, save_diff
from running_field import release_workspace


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
    )

    # Save the diff
    diff_path = save_diff(cl_name, target_dir=workspace_dir)
    if not diff_path:
        print("Failed to save diff")
        return None, 1

    # Create proposed HISTORY entry
    success, entry_id = add_proposed_history_entry(
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


def finalize_loop_runner(
    project_file: str,
    changespec_name: str,
    workspace_num: int,
    workflow_name: str,
    proposal_id: str | None,
    exit_code: int,
    update_suffix_fn: Callable[[ChangeSpec, str, str | None, int], None],
) -> None:
    """Common finalization logic for loop runners.

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
