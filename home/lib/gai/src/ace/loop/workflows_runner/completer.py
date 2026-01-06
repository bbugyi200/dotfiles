"""Workflow completion handling logic for the loop command."""

import subprocess

from gai_utils import shorten_path
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
    set_hook_suffix,
)
from ...hooks.history import is_proposal_entry
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
    start_fix_hook_workflow,
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
        find_proposal_entry,
        parse_proposal_id,
        renumber_commit_entries,
    )
    from commit_utils import apply_diff_to_workspace

    # Parse proposal ID
    parsed = parse_proposal_id(proposal_id)
    if not parsed:
        log(f"Invalid proposal ID: {proposal_id}", "yellow")
        return False
    base_num, letter = parsed

    # Find the proposal entry
    entry = find_proposal_entry(changespec.commits, base_num, letter)
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
    success = renumber_commit_entries(
        changespec.file_path,
        changespec.name,
        [(base_num, letter)],
        None,
    )
    if not success:
        log("Failed to renumber HISTORY entries", "yellow")
        # Continue anyway since amend succeeded

    # Add test target hooks from changed_test_targets
    from workflow_utils import add_test_hooks_if_available

    add_test_hooks_if_available(
        changespec.file_path,
        changespec.name,
        workspace_dir=workspace_dir,
        verbose=False,  # Loop runs silently
    )

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
    for hook_command, timestamp, entry_id, summary in get_running_fix_hook_workflows(
        changespec
    ):
        output_path = get_workflow_output_path(changespec.name, "fix-hook", timestamp)
        completed, proposal_id, exit_code = check_workflow_completion(output_path)

        if completed:
            workflow_name = f"loop(fix-hook)-{timestamp}"

            if proposal_id and exit_code == 0:
                # Re-read ChangeSpec to get current state
                current_changespecs = parse_project_file(changespec.file_path)
                current_cs = None
                for cs in current_changespecs:
                    if cs.name == changespec.name:
                        current_cs = cs
                        break

                # Always update hook suffix to reference proposal (preserving summary)
                if current_cs and current_cs.hooks:
                    current_summary = None
                    for h in current_cs.hooks:
                        if h.command == hook_command:
                            sl = h.get_status_line_for_commit_entry(entry_id)
                            if sl:
                                current_summary = sl.summary
                            break
                    set_hook_suffix(
                        changespec.file_path,
                        changespec.name,
                        hook_command,
                        proposal_id,
                        current_cs.hooks,
                        entry_id=entry_id,
                        suffix_type="plain",
                        summary=current_summary,
                    )

                # Find workspace and attempt auto-accept
                workspace_found = False
                for claim in get_claimed_workspaces(changespec.file_path):
                    if (
                        claim.cl_name == changespec.name
                        and claim.workflow == workflow_name
                    ):
                        workspace_found = True
                        workspace_dir, _ = get_workspace_directory_for_num(
                            claim.workspace_num, project_basename
                        )

                        if current_cs:
                            # Auto-accept the proposal
                            if _auto_accept_proposal(
                                current_cs, proposal_id, workspace_dir, log
                            ):
                                updates.append(
                                    f"fix-hook workflow '{hook_command}' -> COMPLETED, "
                                    f"auto-accepted ({proposal_id})"
                                )
                            else:
                                updates.append(
                                    f"fix-hook workflow '{hook_command}' -> proposal "
                                    f"({proposal_id}) created, auto-accept failed"
                                )

                        # Release workspace
                        release_workspace(
                            changespec.file_path,
                            claim.workspace_num,
                            workflow_name,
                            changespec.name,
                        )
                        break

                if not workspace_found:
                    # No workspace to auto-accept from, but suffix was still updated
                    updates.append(
                        f"fix-hook workflow '{hook_command}' -> proposal "
                        f"({proposal_id}) created (no workspace for auto-accept)"
                    )
            else:
                # Workflow failed - set error suffix with summary preserved
                # Re-read ChangeSpec to get current summary (in case fix-hook
                # started and failed in the same loop iteration)
                current_changespecs = parse_project_file(changespec.file_path)
                current_cs = None
                for cs in current_changespecs:
                    if cs.name == changespec.name:
                        current_cs = cs
                        break

                current_summary = None
                hooks_to_update = changespec.hooks
                if current_cs and current_cs.hooks:
                    hooks_to_update = current_cs.hooks
                    for h in current_cs.hooks:
                        if h.command == hook_command:
                            sl = h.get_status_line_for_commit_entry(entry_id)
                            if sl:
                                current_summary = sl.summary
                            break

                # Prepend output file path to summary for easy access to fix-hook logs
                shortened_output = shorten_path(output_path)
                if current_summary:
                    current_summary = f"{shortened_output} | {current_summary}"
                else:
                    current_summary = shortened_output

                if hooks_to_update:
                    set_hook_suffix(
                        changespec.file_path,
                        changespec.name,
                        hook_command,
                        "fix-hook Failed",
                        hooks_to_update,
                        entry_id=entry_id,
                        suffix_type="error",
                        summary=current_summary,
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
    for hook_command, timestamp, entry_id in get_running_summarize_hook_workflows(
        changespec
    ):
        output_path = get_workflow_output_path(
            changespec.name, "summarize-hook", timestamp
        )
        completed, _, exit_code = check_workflow_completion(output_path)

        if completed:
            if exit_code == 0:
                updates.append(f"summarize-hook workflow '{hook_command}' -> COMPLETED")
                # Immediately chain fix-hook for non-proposal entries
                if not is_proposal_entry(entry_id):
                    # Re-read ChangeSpec to get the summary that was just written
                    current_changespecs = parse_project_file(changespec.file_path)
                    for cs in current_changespecs:
                        if cs.name == changespec.name:
                            # Find the hook and start fix-hook workflow
                            if cs.hooks:
                                for h in cs.hooks:
                                    if h.command == hook_command:
                                        result = start_fix_hook_workflow(
                                            cs, h, entry_id, log
                                        )
                                        if result:
                                            updates.append(result)
                                        break
                            break
            else:
                # Workflow failed - set fallback suffix
                if changespec.hooks:
                    set_hook_suffix(
                        changespec.file_path,
                        changespec.name,
                        hook_command,
                        "Hook Command Failed",
                        changespec.hooks,
                        entry_id=entry_id,
                        suffix_type="error",
                    )
                updates.append(
                    f"summarize-hook workflow '{hook_command}' -> FAILED (exit {exit_code})"
                )

    return updates
