"""Workflow completion handling logic for the loop command."""

import subprocess

from running_field import (
    get_claimed_workspaces,
    get_workspace_directory_for_num,
    release_workspace,
)

from ...changespec import (
    ChangeSpec,
    parse_project_file,
)
from ...comments import (
    set_comment_suffix,
)
from ...hooks import (
    clear_hook_suffix,
    set_hook_suffix,
)
from .monitor import (
    check_workflow_completion,
    get_running_crs_workflows,
    get_running_fix_hook_workflows,
    get_running_summarize_hook_workflows,
)
from .starter import (
    LogCallback,
    get_project_basename,
    get_workflow_output_path,
)


def _auto_accept_proposal(
    changespec: ChangeSpec,
    proposal_id: str,
    workspace_dir: str,
    log: LogCallback,
) -> bool:
    """Auto-accept a proposal without user interaction.

    Args:
        changespec: The ChangeSpec containing the proposal.
        proposal_id: The proposal ID (e.g., "2a").
        workspace_dir: The workspace directory to use.
        log: Logging callback.

    Returns:
        True if successful, False otherwise.
    """
    # Import here to avoid circular imports
    from accept_workflow import (
        _find_proposal_entry,
        _parse_proposal_id,
        _renumber_history_entries,
    )
    from history_utils import apply_diff_to_workspace

    # Parse proposal ID
    parsed = _parse_proposal_id(proposal_id)
    if not parsed:
        log(f"Invalid proposal ID: {proposal_id}", "yellow")
        return False
    base_num, letter = parsed

    # Find the proposal entry
    entry = _find_proposal_entry(changespec.history, base_num, letter)
    if not entry or not entry.diff:
        log(f"Proposal ({proposal_id}) not found or has no diff", "yellow")
        return False

    # Apply the diff
    success, error_msg = apply_diff_to_workspace(workspace_dir, entry.diff)
    if not success:
        log(f"Failed to apply proposal diff: {error_msg}", "yellow")
        return False

    # Amend the commit
    try:
        result = subprocess.run(
            ["bb_hg_amend", entry.note],
            capture_output=True,
            text=True,
            cwd=workspace_dir,
        )
        if result.returncode != 0:
            log(f"bb_hg_amend failed: {result.stderr.strip()}", "yellow")
            return False
    except FileNotFoundError:
        log("bb_hg_amend command not found", "yellow")
        return False

    # Renumber history entries
    success = _renumber_history_entries(
        changespec.file_path,
        changespec.name,
        [(base_num, letter)],
        None,
    )
    if not success:
        log("Failed to renumber HISTORY entries", "yellow")
        # Continue anyway since amend succeeded

    return True


def check_and_complete_workflows(
    changespec: ChangeSpec,
    log: LogCallback,
) -> list[str]:
    """Check completion of running workflows and auto-accept proposals.

    Args:
        changespec: The ChangeSpec to check.
        log: Logging callback.

    Returns:
        List of update messages.
    """
    updates: list[str] = []
    project_basename = get_project_basename(changespec)

    # Check CRS workflows
    for reviewer, timestamp in get_running_crs_workflows(changespec):
        output_path = get_workflow_output_path(changespec.name, "crs", timestamp)
        completed, proposal_id, exit_code = check_workflow_completion(output_path)

        if completed:
            workflow_name = f"loop(crs)-{reviewer}"

            if proposal_id and exit_code == 0:
                # Find and release the workspace
                for claim in get_claimed_workspaces(changespec.file_path):
                    if (
                        claim.cl_name == changespec.name
                        and claim.workflow == workflow_name
                    ):
                        workspace_dir, _ = get_workspace_directory_for_num(
                            claim.workspace_num, project_basename
                        )

                        # Re-read ChangeSpec to get current state
                        current_changespecs = parse_project_file(changespec.file_path)
                        current_cs = None
                        for cs in current_changespecs:
                            if cs.name == changespec.name:
                                current_cs = cs
                                break

                        if current_cs:
                            # Auto-accept the proposal
                            if _auto_accept_proposal(
                                current_cs, proposal_id, workspace_dir, log
                            ):
                                updates.append(
                                    f"CRS workflow [{reviewer}] -> COMPLETED, "
                                    f"auto-accepted ({proposal_id})"
                                )
                            else:
                                updates.append(
                                    f"CRS workflow [{reviewer}] -> FAILED to auto-accept"
                                )

                        # Release workspace
                        release_workspace(
                            changespec.file_path,
                            claim.workspace_num,
                            workflow_name,
                            changespec.name,
                        )
                        break
            else:
                # Workflow failed - set suffix and release workspace
                if changespec.comments:
                    set_comment_suffix(
                        changespec.file_path,
                        changespec.name,
                        reviewer,
                        "Unresolved Critique Comments",
                        changespec.comments,
                    )
                updates.append(
                    f"CRS workflow [{reviewer}] -> FAILED (exit {exit_code})"
                )

                # Release workspace
                for claim in get_claimed_workspaces(changespec.file_path):
                    if (
                        claim.cl_name == changespec.name
                        and claim.workflow == workflow_name
                    ):
                        release_workspace(
                            changespec.file_path,
                            claim.workspace_num,
                            workflow_name,
                            changespec.name,
                        )
                        break

    # Check fix-hook workflows
    for hook_command, timestamp in get_running_fix_hook_workflows(changespec):
        output_path = get_workflow_output_path(changespec.name, "fix-hook", timestamp)
        completed, proposal_id, exit_code = check_workflow_completion(output_path)

        if completed:
            workflow_name = f"loop(fix-hook)-{timestamp}"

            if proposal_id and exit_code == 0:
                # Find and release the workspace
                for claim in get_claimed_workspaces(changespec.file_path):
                    if (
                        claim.cl_name == changespec.name
                        and claim.workflow == workflow_name
                    ):
                        workspace_dir, _ = get_workspace_directory_for_num(
                            claim.workspace_num, project_basename
                        )

                        # Re-read ChangeSpec to get current state
                        current_changespecs = parse_project_file(changespec.file_path)
                        current_cs = None
                        for cs in current_changespecs:
                            if cs.name == changespec.name:
                                current_cs = cs
                                break

                        if current_cs:
                            # Auto-accept the proposal
                            if _auto_accept_proposal(
                                current_cs, proposal_id, workspace_dir, log
                            ):
                                updates.append(
                                    f"fix-hook workflow '{hook_command}' -> COMPLETED, "
                                    f"auto-accepted ({proposal_id})"
                                )
                                # Clear the hook suffix on success
                                if current_cs.hooks:
                                    clear_hook_suffix(
                                        changespec.file_path,
                                        changespec.name,
                                        hook_command,
                                        current_cs.hooks,
                                    )
                            else:
                                updates.append(
                                    f"fix-hook workflow '{hook_command}' -> FAILED to auto-accept"
                                )

                        # Release workspace
                        release_workspace(
                            changespec.file_path,
                            claim.workspace_num,
                            workflow_name,
                            changespec.name,
                        )
                        break
            else:
                # Workflow failed - set suffix and release workspace
                if changespec.hooks:
                    set_hook_suffix(
                        changespec.file_path,
                        changespec.name,
                        hook_command,
                        "Hook Command Failed",
                        changespec.hooks,
                        suffix_type="error",
                    )
                updates.append(
                    f"fix-hook workflow '{hook_command}' -> FAILED (exit {exit_code})"
                )

                # Release workspace
                for claim in get_claimed_workspaces(changespec.file_path):
                    if (
                        claim.cl_name == changespec.name
                        and claim.workflow == workflow_name
                    ):
                        release_workspace(
                            changespec.file_path,
                            claim.workspace_num,
                            workflow_name,
                            changespec.name,
                        )
                        break

    # Check summarize-hook workflows (no workspace to release)
    for hook_command, timestamp in get_running_summarize_hook_workflows(changespec):
        output_path = get_workflow_output_path(
            changespec.name, "summarize-hook", timestamp
        )
        completed, _, exit_code = check_workflow_completion(output_path)

        if completed:
            if exit_code == 0:
                updates.append(f"summarize-hook workflow '{hook_command}' -> COMPLETED")
            else:
                # Workflow failed - set fallback suffix
                if changespec.hooks:
                    set_hook_suffix(
                        changespec.file_path,
                        changespec.name,
                        hook_command,
                        "Hook Command Failed",
                        changespec.hooks,
                        suffix_type="error",
                    )
                updates.append(
                    f"summarize-hook workflow '{hook_command}' -> FAILED (exit {exit_code})"
                )

    return updates
