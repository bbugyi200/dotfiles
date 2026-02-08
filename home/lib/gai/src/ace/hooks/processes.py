"""Process management utilities for hooks."""

import os
import re
import signal
from collections.abc import Callable

from ..changespec import (
    ChangeSpec,
    CommentEntry,
    HookEntry,
    HookStatusLine,
    MentorEntry,
    MentorStatusLine,
    extract_pid_from_agent_suffix,
)
from .timestamps import get_current_timestamp


def _try_kill_process_group(pid: int) -> bool:
    """Try to kill a process group via SIGTERM.

    Args:
        pid: The process group ID to kill.

    Returns:
        True always (process was killed, already dead, or inaccessible).
    """
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    return True


def is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is still running.

    Args:
        pid: The process ID to check.

    Returns:
        True if the process is running, False otherwise.
    """
    try:
        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it
        return True


def kill_running_hook_processes(
    changespec: ChangeSpec,
    skip_dollar: bool = False,
) -> list[tuple[HookEntry, HookStatusLine, int]]:
    """Kill all running hook processes for a ChangeSpec.

    Finds all hooks with suffix_type="running_process", extracts the PID,
    and sends SIGTERM to terminate the process group.

    Args:
        changespec: The ChangeSpec to kill running hooks for.
        skip_dollar: If True, skip $-prefixed hooks (skip_proposal_runs).

    Returns:
        List of (hook, status_line, pid) tuples for processes that were killed
        (or attempted to kill). Used to update suffix to killed_process.
    """
    killed: list[tuple[HookEntry, HookStatusLine, int]] = []

    if not changespec.hooks:
        return killed

    for hook in changespec.hooks:
        if skip_dollar and hook.skip_proposal_runs:
            continue
        if not hook.status_lines:
            continue
        for sl in hook.status_lines:
            if sl.suffix_type == "running_process" and sl.suffix:
                try:
                    pid = int(sl.suffix)
                except ValueError:
                    continue

                _try_kill_process_group(pid)
                killed.append((hook, sl, pid))

    return killed


def mark_hooks_as_killed(
    hooks: list[HookEntry],
    killed_processes: list[tuple[HookEntry, HookStatusLine, int]],
    description: str,
) -> list[HookEntry]:
    """Update hook status lines to mark killed processes as DEAD.

    Changes suffix_type from "running_process" to "killed_process" and
    updates the suffix to include a timestamped description.

    Args:
        hooks: List of all HookEntry objects.
        killed_processes: List of (hook, status_line, pid) from kill operation.
        description: Description of why the hook was killed
            (e.g., "Killed hook running on reverted CL.").

    Returns:
        Updated list of HookEntry objects with modified suffix_type.
    """
    timestamp = get_current_timestamp()
    formatted_description = f"[{timestamp}] {description}"

    # Build lookup set of (command, commit_entry_num, pid) for killed processes
    killed_lookup: set[tuple[str, str, str]] = {
        (hook.command, sl.commit_entry_num, str(pid))
        for hook, sl, pid in killed_processes
    }

    updated_hooks: list[HookEntry] = []
    for hook in hooks:
        if not hook.status_lines:
            updated_hooks.append(hook)
            continue

        updated_status_lines: list[HookStatusLine] = []
        for sl in hook.status_lines:
            if (hook.command, sl.commit_entry_num, sl.suffix) in killed_lookup:
                # Create new status line with DEAD status and description
                new_suffix = f"{sl.suffix} | {formatted_description}"
                updated_sl = HookStatusLine(
                    commit_entry_num=sl.commit_entry_num,
                    timestamp=sl.timestamp,
                    status="DEAD",
                    duration=sl.duration,
                    suffix=new_suffix,
                    suffix_type="killed_process",
                )
                updated_status_lines.append(updated_sl)
            else:
                updated_status_lines.append(sl)

        updated_hook = HookEntry(
            command=hook.command,
            status_lines=updated_status_lines,
        )
        updated_hooks.append(updated_hook)

    return updated_hooks


def kill_running_agent_processes(
    changespec: ChangeSpec,
) -> tuple[
    list[tuple[HookEntry, HookStatusLine, int]],
    list[tuple[CommentEntry, int]],
]:
    """Kill all running agent processes for a ChangeSpec.

    Finds all hooks and comment entries with suffix_type="running_agent",
    extracts the PID from the suffix (format: <agent>-<PID>-<timestamp>),
    and sends SIGTERM to terminate the process group.

    Args:
        changespec: The ChangeSpec to kill running agents for.

    Returns:
        Tuple of:
        - List of (hook, status_line, pid) tuples for killed hook agents
        - List of (commit_entry, pid) tuples for killed comment agents
    """
    killed_hooks: list[tuple[HookEntry, HookStatusLine, int]] = []
    killed_comments: list[tuple[CommentEntry, int]] = []

    # Kill agent processes on hooks (fix_hook, summarize_hook workflows)
    if changespec.hooks:
        for hook in changespec.hooks:
            if not hook.status_lines:
                continue
            for sl in hook.status_lines:
                if sl.suffix_type == "running_agent" and sl.suffix:
                    pid = extract_pid_from_agent_suffix(sl.suffix)
                    if pid is None:
                        continue

                    _try_kill_process_group(pid)
                    killed_hooks.append((hook, sl, pid))

    # Kill agent processes on comments (crs workflow)
    if changespec.comments:
        for comment in changespec.comments:
            if comment.suffix_type == "running_agent" and comment.suffix:
                pid = extract_pid_from_agent_suffix(comment.suffix)
                if pid is None:
                    continue

                _try_kill_process_group(pid)
                killed_comments.append((comment, pid))

    return killed_hooks, killed_comments


def mark_hook_agents_as_killed(
    hooks: list[HookEntry],
    killed_agents: list[tuple[HookEntry, HookStatusLine, int]],
) -> list[HookEntry]:
    """Update hook status lines to mark killed agent processes.

    Changes suffix_type from "running_agent" to "killed_agent" for
    the specified status lines.

    Args:
        hooks: List of all HookEntry objects.
        killed_agents: List of (hook, status_line, pid) from kill operation.

    Returns:
        Updated list of HookEntry objects with modified suffix_type.
    """
    # Build lookup set of (command, commit_entry_num, suffix) for killed agents
    killed_lookup: set[tuple[str, str, str]] = {
        (hook.command, sl.commit_entry_num, sl.suffix or "")
        for hook, sl, pid in killed_agents
    }

    updated_hooks: list[HookEntry] = []
    for hook in hooks:
        if not hook.status_lines:
            updated_hooks.append(hook)
            continue

        updated_status_lines: list[HookStatusLine] = []
        for sl in hook.status_lines:
            if (hook.command, sl.commit_entry_num, sl.suffix or "") in killed_lookup:
                # Create new status line with killed_agent type
                updated_sl = HookStatusLine(
                    commit_entry_num=sl.commit_entry_num,
                    timestamp=sl.timestamp,
                    status=sl.status,
                    duration=sl.duration,
                    suffix=sl.suffix,
                    suffix_type="killed_agent",
                )
                updated_status_lines.append(updated_sl)
            else:
                updated_status_lines.append(sl)

        updated_hook = HookEntry(
            command=hook.command,
            status_lines=updated_status_lines,
        )
        updated_hooks.append(updated_hook)

    return updated_hooks


def kill_running_processes_for_hooks(
    hooks: list[HookEntry] | None,
    hook_indices: set[int],
) -> int:
    """Kill running processes/agents for specific hooks by index.

    This function is used when removing hook status lines via the "h" option
    (rerun or delete). It kills any processes/agents associated with the
    hooks being modified.

    Unlike kill_running_hook_processes() and kill_running_agent_processes()
    which operate on ALL hooks in a ChangeSpec, this function targets only
    specific hooks by index.

    Args:
        hooks: List of all HookEntry objects.
        hook_indices: Set of hook indices to check and kill.

    Returns:
        Count of processes/agents killed.
    """
    if not hooks:
        return 0

    killed_count = 0

    for idx in hook_indices:
        if idx < 0 or idx >= len(hooks):
            continue

        hook = hooks[idx]
        if not hook.status_lines:
            continue

        for sl in hook.status_lines:
            pid: int | None = None

            if sl.suffix_type == "running_process" and sl.suffix:
                try:
                    pid = int(sl.suffix)
                except ValueError:
                    continue
            elif sl.suffix_type == "running_agent" and sl.suffix:
                pid = extract_pid_from_agent_suffix(sl.suffix)

            if pid is not None:
                _try_kill_process_group(pid)
                killed_count += 1

    return killed_count


def kill_running_mentor_processes(
    changespec: ChangeSpec,
) -> list[tuple[MentorEntry, MentorStatusLine, int]]:
    """Kill all running mentor processes for a ChangeSpec.

    Finds all mentors with suffix_type="running_agent", extracts the PID
    from the suffix (format: mentor_<name>-<PID>-<timestamp>),
    and sends SIGTERM to terminate the process group.

    Args:
        changespec: The ChangeSpec to kill running mentors for.

    Returns:
        List of (mentor_entry, status_line, pid) tuples for processes that
        were killed (or attempted to kill).
    """
    killed: list[tuple[MentorEntry, MentorStatusLine, int]] = []

    if not changespec.mentors:
        return killed

    for entry in changespec.mentors:
        if not entry.status_lines:
            continue
        for sl in entry.status_lines:
            if sl.suffix_type == "running_agent" and sl.suffix:
                pid = extract_pid_from_agent_suffix(sl.suffix)
                if pid is None:
                    continue

                _try_kill_process_group(pid)
                killed.append((entry, sl, pid))

    return killed


def mark_mentor_agents_as_killed(
    mentors: list[MentorEntry],
    killed_agents: list[tuple[MentorEntry, MentorStatusLine, int]],
) -> list[MentorEntry]:
    """Update mentor status lines to mark killed agent processes.

    Changes suffix_type from "running_agent" to "killed_agent" for
    the specified status lines.

    Args:
        mentors: List of all MentorEntry objects.
        killed_agents: List of (mentor_entry, status_line, pid) from kill operation.

    Returns:
        Updated list of MentorEntry objects with modified suffix_type.
    """
    # Build lookup set of (entry_id, profile_name, mentor_name, suffix) for killed agents
    killed_lookup: set[tuple[str, str, str, str]] = {
        (entry.entry_id, sl.profile_name, sl.mentor_name, sl.suffix or "")
        for entry, sl, pid in killed_agents
    }

    updated_mentors: list[MentorEntry] = []
    for entry in mentors:
        if not entry.status_lines:
            updated_mentors.append(entry)
            continue

        updated_status_lines: list[MentorStatusLine] = []
        for sl in entry.status_lines:
            key = (entry.entry_id, sl.profile_name, sl.mentor_name, sl.suffix or "")
            if key in killed_lookup:
                # Create new status line with killed_agent type
                updated_sl = MentorStatusLine(
                    profile_name=sl.profile_name,
                    mentor_name=sl.mentor_name,
                    status=sl.status,
                    timestamp=sl.timestamp,
                    duration=sl.duration,
                    suffix=sl.suffix,
                    suffix_type="killed_agent",
                )
                updated_status_lines.append(updated_sl)
            else:
                updated_status_lines.append(sl)

        updated_entry = MentorEntry(
            entry_id=entry.entry_id,
            profiles=entry.profiles,
            status_lines=updated_status_lines,
        )
        updated_mentors.append(updated_entry)

    return updated_mentors


def _extract_mentor_workflow_from_suffix(suffix: str) -> str | None:
    """Extract workflow name from mentor suffix.

    Args:
        suffix: Mentor suffix in format "mentor_{name}-{PID}-{timestamp}"

    Returns:
        Workflow name in format "axe(mentor)-{name}-{timestamp}" or None
    """
    match = re.match(r"^mentor_(.+)-\d+-(\d{6}_\d{6})$", suffix)
    if match:
        mentor_name = match.group(1)
        timestamp = match.group(2)
        return f"axe(mentor)-{mentor_name}-{timestamp}"
    return None


def kill_and_persist_all_running_processes(
    changespec: ChangeSpec,
    project_file: str,
    cl_name: str,
    kill_reason: str,
    log_fn: Callable[[str], None] | None = None,
) -> None:
    """Kill all running hook/agent/mentor processes and persist updates.

    This is a convenience function that orchestrates killing all running
    processes (hooks, agents, mentors) for a ChangeSpec, marking them as
    killed, persisting updates to the project file, and releasing any
    workspaces claimed by killed mentor processes.

    Args:
        changespec: The ChangeSpec to kill processes for.
        project_file: Path to the project file.
        cl_name: The CL name.
        kill_reason: Description of why processes are being killed
            (e.g., "Killed hook running on reverted CL.").
        log_fn: Optional callback for logging messages.
    """
    # Lazy imports to avoid circular dependencies
    from ..comments.operations import (
        mark_comment_agents_as_killed,
        update_changespec_comments_field,
    )
    from ..mentors import update_changespec_mentors_field
    from .execution import update_changespec_hooks_field

    # Kill running hook processes
    killed_processes = kill_running_hook_processes(changespec)
    if killed_processes:
        if log_fn:
            log_fn(f"Killed {len(killed_processes)} running hook process(es)")
        if changespec.hooks:
            updated_hooks = mark_hooks_as_killed(
                changespec.hooks, killed_processes, kill_reason
            )
            update_changespec_hooks_field(project_file, cl_name, updated_hooks)

    # Kill running agent processes
    killed_hook_agents, killed_comment_agents = kill_running_agent_processes(changespec)
    total_killed_agents = len(killed_hook_agents) + len(killed_comment_agents)
    if total_killed_agents:
        if log_fn:
            log_fn(f"Killed {total_killed_agents} running agent process(es)")
        if killed_hook_agents and changespec.hooks:
            updated_hooks = mark_hook_agents_as_killed(
                changespec.hooks, killed_hook_agents
            )
            update_changespec_hooks_field(project_file, cl_name, updated_hooks)
        if killed_comment_agents and changespec.comments:
            updated_comments = mark_comment_agents_as_killed(
                changespec.comments, killed_comment_agents
            )
            update_changespec_comments_field(project_file, cl_name, updated_comments)

    # Kill running mentor processes
    killed_mentors = kill_running_mentor_processes(changespec)
    if killed_mentors:
        if log_fn:
            log_fn(f"Killed {len(killed_mentors)} running mentor process(es)")
        if changespec.mentors:
            updated_mentors = mark_mentor_agents_as_killed(
                changespec.mentors, killed_mentors
            )
            update_changespec_mentors_field(project_file, cl_name, updated_mentors)

        # Release workspaces claimed by killed mentor processes
        from running_field import get_claimed_workspaces, release_workspace

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
                    if log_fn:
                        log_fn(
                            f"Released workspace #{claim.workspace_num} "
                            f"for killed mentor"
                        )
                    break
