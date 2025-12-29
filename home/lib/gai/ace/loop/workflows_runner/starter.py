"""Workflow starting/launching logic for the loop command."""

import os
import subprocess
import time
from collections.abc import Callable

from gai_utils import ensure_gai_directory, make_safe_filename
from history_utils import run_bb_hg_clean
from running_field import (
    claim_workspace,
    get_first_available_loop_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)

from ...changespec import (
    ChangeSpec,
    CommentEntry,
    HookEntry,
)
from ...comments import (
    set_comment_suffix,
)
from ...hooks import (
    generate_timestamp,
    get_failing_hooks_for_fix,
    get_failing_hooks_for_summarize,
    get_hook_output_path,
    get_last_history_entry_id,
    set_hook_suffix,
)

# Type alias for logging callback
LogCallback = Callable[[str, str | None], None]


def get_workflow_output_path(name: str, workflow_type: str, timestamp: str) -> str:
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


def get_project_basename(changespec: ChangeSpec) -> str:
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
            if entry.reviewer in ("critique", "critique:me") and entry.suffix is None:
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
    project_basename = get_project_basename(changespec)
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

        # Clean workspace before switching branches
        clean_success, clean_error = run_bb_hg_clean(
            workspace_dir, f"{changespec.name}-crs"
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
        output_path = get_workflow_output_path(changespec.name, "crs", timestamp)

        # Build the runner script path
        runner_script = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
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
    project_basename = get_project_basename(changespec)
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

        # Clean workspace before switching branches
        clean_success, clean_error = run_bb_hg_clean(
            workspace_dir, f"{changespec.name}-fix-hook"
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
        output_path = get_workflow_output_path(changespec.name, "fix-hook", timestamp)

        # Build the runner script path
        runner_script = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
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
    output_path = get_workflow_output_path(changespec.name, "summarize-hook", timestamp)

    # Build the runner script path
    runner_script = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
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
