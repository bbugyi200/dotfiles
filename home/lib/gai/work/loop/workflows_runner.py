"""Workflow background execution for the loop command (crs and fix-hook)."""

import os
import re
import subprocess
import time
from collections.abc import Callable

from gai_utils import ensure_gai_directory, make_safe_filename
from running_field import (
    claim_workspace,
    get_claimed_workspaces,
    get_first_available_loop_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)

from ..changespec import (
    ChangeSpec,
    CommentEntry,
    HookEntry,
    parse_project_file,
)
from ..comments import (
    set_comment_suffix,
)
from ..hooks import (
    generate_timestamp,
    get_failing_hooks_for_fix,
    get_failing_hooks_for_summarize,
    get_hook_output_path,
    get_last_history_entry_id,
    set_hook_suffix,
)
from ..hooks.core import is_proposal_entry

# Type alias for logging callback
LogCallback = Callable[[str, str | None], None]

# Workflow completion marker (same pattern as hooks)
WORKFLOW_COMPLETE_MARKER = "===WORKFLOW_COMPLETE=== PROPOSAL_ID: "


def _get_workflow_output_path(name: str, workflow_type: str, timestamp: str) -> str:
    """Get the output file path for a workflow run.

    Args:
        name: The ChangeSpec name.
        workflow_type: The workflow type ("crs" or "fix-hook").
        timestamp: The timestamp in YYmmdd_HHMMSS format.

    Returns:
        Full path to the workflow output file.
    """
    workflows_dir = ensure_gai_directory("workflows")
    safe_name = make_safe_filename(name)
    filename = f"{safe_name}_{workflow_type}-{timestamp}.txt"
    return os.path.join(workflows_dir, filename)


def _get_project_basename(changespec: ChangeSpec) -> str:
    """Extract project basename from ChangeSpec file path."""
    return os.path.splitext(os.path.basename(changespec.file_path))[0]


def _crs_workflow_eligible(changespec: ChangeSpec) -> list[CommentEntry]:
    """Get CRS-eligible comment entries (no suffix).

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of CommentEntry objects eligible for CRS workflow.
    """
    eligible: list[CommentEntry] = []
    if changespec.comments:
        for entry in changespec.comments:
            if entry.reviewer in ("reviewer", "author") and entry.suffix is None:
                eligible.append(entry)
    return eligible


def _fix_hook_workflow_eligible(changespec: ChangeSpec) -> list[HookEntry]:
    """Get fix-hook-eligible hooks (FAILED status, no suffix).

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of HookEntry objects eligible for fix-hook workflow.
    """
    if not changespec.hooks:
        return []
    return get_failing_hooks_for_fix(changespec.hooks)


def _summarize_hook_workflow_eligible(changespec: ChangeSpec) -> list[HookEntry]:
    """Get summarize-hook-eligible hooks (FAILED status, proposal entry, no suffix).

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of HookEntry objects eligible for summarize-hook workflow.
    """
    if not changespec.hooks:
        return []
    return get_failing_hooks_for_summarize(changespec.hooks)


def _start_crs_workflow(
    changespec: ChangeSpec,
    comment_entry: CommentEntry,
    log: LogCallback,
) -> str | None:
    """Start CRS workflow as a background process.

    Args:
        changespec: The ChangeSpec to run CRS for.
        comment_entry: The comment entry to process.
        log: Logging callback.

    Returns:
        Update message if started, None if failed.
    """
    project_basename = _get_project_basename(changespec)
    timestamp = generate_timestamp()

    # Claim a workspace
    workspace_num = get_first_available_loop_workspace(changespec.file_path)
    workflow_name = f"loop(crs)-{comment_entry.reviewer}"

    if not claim_workspace(
        changespec.file_path,
        workspace_num,
        workflow_name,
        changespec.name,
    ):
        log(
            f"Warning: Failed to claim workspace for CRS on {changespec.name}",
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
                    f"Warning: bb_hg_update failed for {changespec.name}: {error_output}",
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
            log(f"Warning: bb_hg_update error for {changespec.name}: {e}", "yellow")
            release_workspace(
                changespec.file_path,
                workspace_num,
                workflow_name,
                changespec.name,
            )
            return None

        # Set timestamp suffix on comment entry to indicate workflow is running
        if changespec.comments:
            set_comment_suffix(
                changespec.file_path,
                changespec.name,
                comment_entry.reviewer,
                timestamp,
                changespec.comments,
            )

        # Expand the comments file path (replace ~ with home directory)
        comments_file = comment_entry.file_path
        if comments_file and comments_file.startswith("~"):
            comments_file = os.path.expanduser(comments_file)

        # Get output file path
        output_path = _get_workflow_output_path(changespec.name, "crs", timestamp)

        # Build the runner script path
        runner_script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "loop_crs_runner.py",
        )

        # Start the background process
        with open(output_path, "w") as output_file:
            subprocess.Popen(
                [
                    "python3",
                    runner_script,
                    changespec.name,
                    changespec.file_path,
                    comments_file or "",
                    comment_entry.reviewer,
                    workspace_dir,
                    output_path,
                    str(workspace_num),
                    workflow_name,
                ],
                cwd=workspace_dir,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        return f"CRS workflow -> RUNNING for [{comment_entry.reviewer}]"

    except Exception as e:
        log(f"Warning: Error starting CRS workflow: {e}", "yellow")
        release_workspace(
            changespec.file_path,
            workspace_num,
            workflow_name,
            changespec.name,
        )
        return None


def _start_fix_hook_workflow(
    changespec: ChangeSpec,
    hook: HookEntry,
    log: LogCallback,
) -> str | None:
    """Start fix-hook workflow as a background process.

    Args:
        changespec: The ChangeSpec to run fix-hook for.
        hook: The hook to fix.
        log: Logging callback.

    Returns:
        Update message if started, None if failed.
    """
    project_basename = _get_project_basename(changespec)
    timestamp = generate_timestamp()

    # Claim a workspace
    workspace_num = get_first_available_loop_workspace(changespec.file_path)
    workflow_name = f"loop(fix-hook)-{timestamp}"

    if not claim_workspace(
        changespec.file_path,
        workspace_num,
        workflow_name,
        changespec.name,
    ):
        log(
            f"Warning: Failed to claim workspace for fix-hook on {changespec.name}",
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
                    f"Warning: bb_hg_update failed for {changespec.name}: {error_output}",
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
            log(f"Warning: bb_hg_update error for {changespec.name}: {e}", "yellow")
            release_workspace(
                changespec.file_path,
                workspace_num,
                workflow_name,
                changespec.name,
            )
            return None

        # Set timestamp suffix on hook status line to indicate workflow is running
        if changespec.hooks:
            set_hook_suffix(
                changespec.file_path,
                changespec.name,
                hook.command,
                timestamp,
                changespec.hooks,
            )

        # Get hook output path for the failing hook
        hook_output_path = ""
        if hook.timestamp:
            hook_output_path = get_hook_output_path(changespec.name, hook.timestamp)

        # Get the last HISTORY entry ID
        last_history_id = get_last_history_entry_id(changespec) or "0"

        # Get output file path for workflow
        output_path = _get_workflow_output_path(changespec.name, "fix-hook", timestamp)

        # Build the runner script path
        runner_script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "loop_fix_hook_runner.py",
        )

        # Start the background process
        with open(output_path, "w") as output_file:
            subprocess.Popen(
                [
                    "python3",
                    runner_script,
                    changespec.name,
                    changespec.file_path,
                    hook.command,
                    hook_output_path,
                    workspace_dir,
                    output_path,
                    str(workspace_num),
                    workflow_name,
                    last_history_id,
                ],
                cwd=workspace_dir,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        return f"fix-hook workflow -> RUNNING for '{hook.display_command}'"

    except Exception as e:
        log(f"Warning: Error starting fix-hook workflow: {e}", "yellow")
        release_workspace(
            changespec.file_path,
            workspace_num,
            workflow_name,
            changespec.name,
        )
        return None


def _start_summarize_hook_workflow(
    changespec: ChangeSpec,
    hook: HookEntry,
    log: LogCallback,
) -> str | None:
    """Start summarize-hook workflow as a background process.

    This workflow does NOT require a workspace - it only reads the hook output
    file and calls the summarize agent.

    Args:
        changespec: The ChangeSpec to run summarize-hook for.
        hook: The hook to summarize.
        log: Logging callback.

    Returns:
        Update message if started, None if failed.
    """
    timestamp = generate_timestamp()

    # Set timestamp suffix on hook status line to indicate workflow is running
    if changespec.hooks:
        set_hook_suffix(
            changespec.file_path,
            changespec.name,
            hook.command,
            timestamp,
            changespec.hooks,
        )

    # Get hook output path for the failing hook
    hook_output_path = ""
    if hook.timestamp:
        hook_output_path = get_hook_output_path(changespec.name, hook.timestamp)

    if not hook_output_path or not os.path.exists(hook_output_path):
        # No output file to summarize - set a default suffix
        log(
            f"Warning: No hook output file for summarize-hook on {changespec.name}",
            "yellow",
        )
        if changespec.hooks:
            set_hook_suffix(
                changespec.file_path,
                changespec.name,
                hook.command,
                "Hook Command Failed",
                changespec.hooks,
            )
        return f"summarize-hook workflow '{hook.display_command}' -> no output to summarize"

    # Get output file path for workflow
    output_path = _get_workflow_output_path(
        changespec.name, "summarize-hook", timestamp
    )

    # Build the runner script path
    runner_script = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "loop_summarize_hook_runner.py",
    )

    try:
        # Start the background process
        with open(output_path, "w") as output_file:
            subprocess.Popen(
                [
                    "python3",
                    runner_script,
                    changespec.name,
                    changespec.file_path,
                    hook.command,
                    hook_output_path,
                    output_path,
                ],
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        return f"summarize-hook workflow -> RUNNING for '{hook.display_command}'"

    except Exception as e:
        log(f"Warning: Error starting summarize-hook workflow: {e}", "yellow")
        return None


def start_stale_workflows(
    changespec: ChangeSpec,
    log: LogCallback,
) -> tuple[list[str], list[str]]:
    """Start all stale CRS, fix-hook, and summarize-hook workflows for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to check.
        log: Logging callback.

    Returns:
        Tuple of (update_messages, started_workflow_identifiers).
    """
    updates: list[str] = []
    started: list[str] = []

    # Don't start workflows for terminal statuses
    if changespec.status in ("Reverted", "Submitted"):
        return updates, started

    # Start CRS workflows for eligible comment entries
    for entry in _crs_workflow_eligible(changespec):
        result = _start_crs_workflow(changespec, entry, log)
        if result:
            updates.append(result)
            started.append(f"crs:{entry.reviewer}")
        # Small delay between workflow starts to ensure unique timestamps
        if result:
            time.sleep(1)

    # Start fix-hook workflows for all eligible failing hooks (non-proposal entries)
    for hook in _fix_hook_workflow_eligible(changespec):
        result = _start_fix_hook_workflow(changespec, hook, log)
        if result:
            updates.append(result)
            started.append(f"fix-hook:{hook.command}")
        # Small delay between workflow starts to ensure unique timestamps
        if result:
            time.sleep(1)

    # Start summarize-hook workflows for proposal entry failures
    for hook in _summarize_hook_workflow_eligible(changespec):
        result = _start_summarize_hook_workflow(changespec, hook, log)
        if result:
            updates.append(result)
            started.append(f"summarize-hook:{hook.command}")
        # Small delay between workflow starts to ensure unique timestamps
        if result:
            time.sleep(1)

    return updates, started


def _check_workflow_completion(output_path: str) -> tuple[bool, str | None, int | None]:
    """Check if a workflow has completed by reading its output file.

    Args:
        output_path: Path to the workflow output file.

    Returns:
        Tuple of (completed, proposal_id, exit_code).
    """
    if not os.path.exists(output_path):
        return (False, None, None)

    try:
        with open(output_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return (False, None, None)

    marker_pos = content.rfind(WORKFLOW_COMPLETE_MARKER)
    if marker_pos == -1:
        return (False, None, None)

    # Parse: PROPOSAL_ID: <id> EXIT_CODE: <code>
    try:
        after_marker = content[marker_pos + len(WORKFLOW_COMPLETE_MARKER) :].strip()
        parts = after_marker.split()
        proposal_id = parts[0] if parts and parts[0] != "None" else None
        exit_code = int(parts[2]) if len(parts) > 2 else 1
    except (ValueError, IndexError):
        return (True, None, 1)

    return (True, proposal_id, exit_code)


def _get_running_crs_workflows(changespec: ChangeSpec) -> list[tuple[str, str]]:
    """Get running CRS workflows for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of (reviewer_type, timestamp) tuples for running CRS workflows.
    """
    running: list[tuple[str, str]] = []
    if changespec.comments:
        for entry in changespec.comments:
            if entry.reviewer in ("reviewer", "author") and entry.suffix:
                # Check if suffix is a timestamp (YYmmdd_HHMMSS = 13 chars with underscore)
                if re.match(r"^\d{6}_\d{6}$", entry.suffix):
                    running.append((entry.reviewer, entry.suffix))
    return running


def _get_running_fix_hook_workflows(changespec: ChangeSpec) -> list[tuple[str, str]]:
    """Get running fix-hook workflows for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of (hook_command, timestamp) tuples for running fix-hook workflows.
    """
    running: list[tuple[str, str]] = []
    if changespec.hooks:
        for hook in changespec.hooks:
            sl = hook.latest_status_line
            # Only non-proposal entries are fix-hook workflows
            if sl and sl.suffix and re.match(r"^\d{6}_\d{6}$", sl.suffix):
                if not is_proposal_entry(sl.history_entry_num):
                    running.append((hook.command, sl.suffix))
    return running


def _get_running_summarize_hook_workflows(
    changespec: ChangeSpec,
) -> list[tuple[str, str]]:
    """Get running summarize-hook workflows for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of (hook_command, timestamp) tuples for running summarize-hook workflows.
    """
    running: list[tuple[str, str]] = []
    if changespec.hooks:
        for hook in changespec.hooks:
            sl = hook.latest_status_line
            # Only proposal entries are summarize-hook workflows
            if sl and sl.suffix and re.match(r"^\d{6}_\d{6}$", sl.suffix):
                if is_proposal_entry(sl.history_entry_num):
                    running.append((hook.command, sl.suffix))
    return running


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
    project_basename = _get_project_basename(changespec)

    # Check CRS workflows
    for reviewer, timestamp in _get_running_crs_workflows(changespec):
        output_path = _get_workflow_output_path(changespec.name, "crs", timestamp)
        completed, proposal_id, exit_code = _check_workflow_completion(output_path)

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
    for hook_command, timestamp in _get_running_fix_hook_workflows(changespec):
        output_path = _get_workflow_output_path(changespec.name, "fix-hook", timestamp)
        completed, proposal_id, exit_code = _check_workflow_completion(output_path)

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
                                    from ..hooks import clear_hook_suffix

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
    for hook_command, timestamp in _get_running_summarize_hook_workflows(changespec):
        output_path = _get_workflow_output_path(
            changespec.name, "summarize-hook", timestamp
        )
        completed, _, exit_code = _check_workflow_completion(output_path)

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
                    )
                updates.append(
                    f"summarize-hook workflow '{hook_command}' -> FAILED (exit {exit_code})"
                )

    return updates
