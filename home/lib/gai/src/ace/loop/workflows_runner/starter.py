"""Workflow starting/launching logic for the loop command."""

import os
import subprocess
import time
from collections.abc import Callable

from commit_utils import run_bb_hg_clean
from gai_utils import ensure_gai_directory, make_safe_filename
from running_field import (
    claim_workspace,
    get_first_available_loop_workspace,
    get_workspace_directory_for_num,
)

from ...changespec import (
    ChangeSpec,
    CommentEntry,
    HookEntry,
    count_all_runners_global,
    get_current_and_proposal_entry_ids,
)
from ...comments import (
    set_comment_suffix,
)
from ...hooks import (
    generate_timestamp,
    get_failing_hook_entries_for_fix,
    get_failing_hook_entries_for_summarize,
    get_hook_output_path,
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
    return changespec.project_basename


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


def _fix_hook_workflow_eligible(
    changespec: ChangeSpec,
) -> list[tuple[HookEntry, str]]:
    """Get fix-hook-eligible hooks (FAILED status, no suffix) for all non-historical entries.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of (HookEntry, entry_id) tuples eligible for fix-hook workflow.
    """
    if not changespec.hooks:
        return []
    entry_ids = get_current_and_proposal_entry_ids(changespec)
    return get_failing_hook_entries_for_fix(changespec.hooks, entry_ids)


def _summarize_hook_workflow_eligible(
    changespec: ChangeSpec,
) -> list[tuple[HookEntry, str]]:
    """Get summarize-hook-eligible hooks (FAILED status, proposal entry, no suffix).

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        List of (HookEntry, entry_id) tuples eligible for summarize-hook workflow.
    """
    if not changespec.hooks:
        return []
    entry_ids = get_current_and_proposal_entry_ids(changespec)
    return get_failing_hook_entries_for_summarize(changespec.hooks, entry_ids)


def _start_crs_workflow(
    changespec: ChangeSpec,
    comment_entry: CommentEntry,
    log: LogCallback,
) -> str | None:
    """Start CRS workflow as a background process.

    Spawns the subprocess first, then claims the workspace with the actual PID.
    If the claim fails, the subprocess is terminated.

    Args:
        changespec: The ChangeSpec to run CRS for.
        comment_entry: The comment entry to process.
        log: Logging callback.

    Returns:
        Update message if started, None if failed.
    """
    project_basename = get_project_basename(changespec)
    timestamp = generate_timestamp()

    # Get workspace info (don't claim yet - need subprocess PID first)
    workspace_num = get_first_available_loop_workspace(changespec.file_path)
    workflow_name = f"loop(crs)-{comment_entry.reviewer}"

    try:
        workspace_dir, _ = get_workspace_directory_for_num(
            workspace_num, project_basename
        )
    except RuntimeError as e:
        log(f"Warning: Failed to get workspace directory: {e}", "yellow")
        return None

    if not os.path.isdir(workspace_dir):
        log(f"Warning: Workspace directory not found: {workspace_dir}", "yellow")
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
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log(
            f"Warning: bb_hg_update error for {changespec.name} "
            f"(cwd: {workspace_dir}): {e}",
            "yellow",
        )
        return None

    # Expand the comments file path (replace ~ with home directory)
    comments_file = comment_entry.file_path
    if comments_file and comments_file.startswith("~"):
        comments_file = os.path.expanduser(comments_file)

    # Get output file path
    output_path = get_workflow_output_path(changespec.name, "crs", timestamp)

    # Build the runner script path (use abspath to handle relative __file__)
    runner_script = os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ),
        "loop_crs_runner.py",
    )

    # Start the background process first to get actual PID
    try:
        with open(output_path, "w") as output_file:
            proc = subprocess.Popen(
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
                    timestamp,  # Pass timestamp for artifacts directory sync
                ],
                cwd=workspace_dir,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=os.environ,
            )
            pid = proc.pid
    except Exception as e:
        log(f"Warning: Failed to start CRS subprocess: {e}", "yellow")
        return None

    # Now claim workspace with actual subprocess PID
    if not claim_workspace(
        changespec.file_path,
        workspace_num,
        workflow_name,
        pid,
        changespec.name,
    ):
        log(
            f"Warning: Failed to claim workspace for CRS on {changespec.name}, "
            "terminating subprocess",
            "yellow",
        )
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return None

    # Set timestamp suffix on comment entry to indicate workflow is running
    # Include PID in suffix for process management
    if changespec.comments:
        set_comment_suffix(
            changespec.file_path,
            changespec.name,
            comment_entry.reviewer,
            f"crs-{pid}-{timestamp}",
            changespec.comments,
            suffix_type="running_agent",
        )

    return f"CRS workflow -> RUNNING for [{comment_entry.reviewer}]"


def start_fix_hook_workflow(
    changespec: ChangeSpec,
    hook: HookEntry,
    entry_id: str,
    log: LogCallback,
) -> str | None:
    """Start fix-hook workflow as a background process.

    Spawns the subprocess first, then claims the workspace with the actual PID.
    If the claim fails, the subprocess is terminated.

    Args:
        changespec: The ChangeSpec to run fix-hook for.
        hook: The hook to fix.
        entry_id: The history entry ID for the failing status line.
        log: Logging callback.

    Returns:
        Update message if started, None if failed.
    """
    project_basename = get_project_basename(changespec)
    timestamp = generate_timestamp()

    # Get workspace info (don't claim yet - need subprocess PID first)
    workspace_num = get_first_available_loop_workspace(changespec.file_path)
    workflow_name = f"loop(fix-hook)-{timestamp}"

    try:
        workspace_dir, _ = get_workspace_directory_for_num(
            workspace_num, project_basename
        )
    except RuntimeError as e:
        log(f"Warning: Failed to get workspace directory: {e}", "yellow")
        return None

    if not os.path.isdir(workspace_dir):
        log(f"Warning: Workspace directory not found: {workspace_dir}", "yellow")
        return None

    # Get the summary from the existing status line BEFORE starting the process
    # (has suffix_type="summarize_complete" after summarize-hook workflow completed)
    existing_summary: str | None = None
    sl = hook.get_status_line_for_commit_entry(entry_id)
    if sl and sl.suffix_type == "summarize_complete":
        existing_summary = sl.suffix  # The summary is stored as the suffix value

    # Refuse to start fix-hook without a summary - this ensures the requirement
    # that fix-hooks always have summaries from the summarize-hook workflow
    if not existing_summary:
        log(
            f"Warning: No summary found for fix-hook on "
            f"{hook.display_command} ({entry_id}), skipping",
            "yellow",
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
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log(
            f"Warning: bb_hg_update error for {changespec.name} "
            f"(cwd: {workspace_dir}): {e}",
            "yellow",
        )
        return None

    # Get hook output path for the failing hook's specific entry
    hook_output_path = ""
    sl = hook.get_status_line_for_commit_entry(entry_id)
    if sl and sl.timestamp:
        hook_output_path = get_hook_output_path(changespec.name, sl.timestamp)

    # Get output file path for workflow
    output_path = get_workflow_output_path(changespec.name, "fix-hook", timestamp)

    # Build the runner script path (use abspath to handle relative __file__)
    runner_script = os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ),
        "loop_fix_hook_runner.py",
    )

    # Start the background process first to get actual PID
    try:
        with open(output_path, "w") as output_file:
            proc = subprocess.Popen(
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
                    entry_id,
                    timestamp,  # Pass timestamp for artifacts directory sync
                ],
                cwd=workspace_dir,
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=os.environ,
            )
            pid = proc.pid
    except Exception as e:
        log(f"Warning: Failed to start fix-hook subprocess: {e}", "yellow")
        return None

    # Now claim workspace with actual subprocess PID
    if not claim_workspace(
        changespec.file_path,
        workspace_num,
        workflow_name,
        pid,
        changespec.name,
    ):
        log(
            f"Warning: Failed to claim workspace for fix-hook on {changespec.name}, "
            "terminating subprocess",
            "yellow",
        )
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return None

    # Set timestamp suffix on hook status line to indicate workflow is running
    # Include PID in suffix for process management, preserve summary in compound suffix
    # Pass hooks=None to force re-read with lock, avoiding stale data race condition
    # when multiple fix-hooks are started in the same loop cycle
    set_hook_suffix(
        changespec.file_path,
        changespec.name,
        hook.command,
        f"fix_hook-{pid}-{timestamp}",
        hooks=None,  # Re-read fresh data under lock
        entry_id=entry_id,
        suffix_type="running_agent",
        summary=existing_summary,
    )

    return f"fix-hook workflow -> RUNNING for '{hook.display_command}' ({entry_id})"


def _start_summarize_hook_workflow(
    changespec: ChangeSpec,
    hook: HookEntry,
    entry_id: str,
    log: LogCallback,
) -> str | None:
    """Start summarize-hook workflow as a background process.

    This workflow does NOT require a workspace - it only reads the hook output
    file and calls the summarize agent.

    Args:
        changespec: The ChangeSpec to run summarize-hook for.
        hook: The hook to summarize.
        entry_id: The history entry ID for the failing status line.
        log: Logging callback.

    Returns:
        Update message if started, None if failed.
    """
    timestamp = generate_timestamp()

    # Get hook output path for the failing hook's specific entry
    hook_output_path = ""
    sl = hook.get_status_line_for_commit_entry(entry_id)
    if sl and sl.timestamp:
        hook_output_path = get_hook_output_path(changespec.name, sl.timestamp)

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
                entry_id=entry_id,
                suffix_type="error",
            )
        return f"summarize-hook workflow '{hook.display_command}' ({entry_id}) -> no output to summarize"

    # Get output file path for workflow
    output_path = get_workflow_output_path(changespec.name, "summarize-hook", timestamp)

    # Build the runner script path (use abspath to handle relative __file__)
    runner_script = os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ),
        "loop_summarize_hook_runner.py",
    )

    try:
        # Start the background process and capture PID
        with open(output_path, "w") as output_file:
            proc = subprocess.Popen(
                [
                    "python3",
                    runner_script,
                    changespec.name,
                    changespec.file_path,
                    hook.command,
                    hook_output_path,
                    output_path,
                    entry_id,
                    timestamp,  # Pass timestamp for artifacts directory sync
                ],
                stdout=output_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=os.environ,
            )
            pid = proc.pid

        # Set timestamp suffix on hook status line to indicate workflow is running
        # Include PID in suffix for process management
        if changespec.hooks:
            set_hook_suffix(
                changespec.file_path,
                changespec.name,
                hook.command,
                f"summarize_hook-{pid}-{timestamp}",
                changespec.hooks,
                entry_id=entry_id,
                suffix_type="running_agent",
            )

        return f"summarize-hook workflow -> RUNNING for '{hook.display_command}' ({entry_id})"

    except Exception as e:
        log(f"Warning: Error starting summarize-hook workflow: {e}", "yellow")
        return None


def start_stale_workflows(
    changespec: ChangeSpec,
    log: LogCallback,
    max_runners: int = 5,
    runners_started_this_cycle: int = 0,
) -> tuple[list[str], int, list[str]]:
    """Start all stale CRS, fix-hook, and summarize-hook workflows for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to check.
        log: Logging callback.
        max_runners: Maximum concurrent runners (hooks, agents, mentors) globally (default: 5).
        runners_started_this_cycle: Number of runners already started this cycle (across
            all ChangeSpecs). Added to the global count to avoid exceeding the limit.

    Returns:
        Tuple of (update_messages, agents_started_count, started_workflow_identifiers).
    """
    updates: list[str] = []
    started: list[str] = []

    # Don't start workflows for terminal statuses
    if changespec.status in ("Reverted", "Submitted"):
        return updates, 0, started

    # Check global concurrency limit before starting any workflows
    # Include runners started this cycle (across all ChangeSpecs) that aren't
    # yet written to disk
    current_running = count_all_runners_global() + runners_started_this_cycle
    if current_running >= max_runners:
        log(
            f"Skipping workflow start: {current_running} runners running "
            f"(limit: {max_runners})",
            "dim",
        )
        return updates, 0, started

    available_slots = max_runners - current_running
    agents_started = 0

    # Start CRS workflows for eligible comment entries
    for entry in _crs_workflow_eligible(changespec):
        if agents_started >= available_slots:
            log(
                f"Reached runner limit ({max_runners}), deferring remaining workflows",
                "dim",
            )
            break
        result = _start_crs_workflow(changespec, entry, log)
        if result:
            updates.append(result)
            started.append(f"crs:{entry.reviewer}")
            agents_started += 1
        # Small delay between workflow starts to ensure unique timestamps
        if result:
            time.sleep(1)

    # Start fix-hook workflows for all eligible failing hooks (non-proposal entries)
    for hook, entry_id in _fix_hook_workflow_eligible(changespec):
        if agents_started >= available_slots:
            log(
                f"Reached runner limit ({max_runners}), deferring remaining workflows",
                "dim",
            )
            break
        result = start_fix_hook_workflow(changespec, hook, entry_id, log)
        if result:
            updates.append(result)
            started.append(f"fix-hook:{hook.command}:{entry_id}")
            agents_started += 1
        # Small delay between workflow starts to ensure unique timestamps
        if result:
            time.sleep(1)

    # Start summarize-hook workflows for proposal entry failures
    for hook, entry_id in _summarize_hook_workflow_eligible(changespec):
        if agents_started >= available_slots:
            log(
                f"Reached runner limit ({max_runners}), deferring remaining workflows",
                "dim",
            )
            break
        result = _start_summarize_hook_workflow(changespec, hook, entry_id, log)
        if result:
            updates.append(result)
            started.append(f"summarize-hook:{hook.command}:{entry_id}")
            agents_started += 1
        # Small delay between workflow starts to ensure unique timestamps
        if result:
            time.sleep(1)

    return updates, agents_started, started
