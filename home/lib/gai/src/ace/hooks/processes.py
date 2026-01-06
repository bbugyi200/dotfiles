"""Process management utilities for hooks."""

import os
import signal

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
) -> list[tuple[HookEntry, HookStatusLine, int]]:
    """Kill all running hook processes for a ChangeSpec.

    Finds all hooks with suffix_type="running_process", extracts the PID,
    and sends SIGTERM to terminate the process group.

    Args:
        changespec: The ChangeSpec to kill running hooks for.

    Returns:
        List of (hook, status_line, pid) tuples for processes that were killed
        (or attempted to kill). Used to update suffix to killed_process.
    """
    killed: list[tuple[HookEntry, HookStatusLine, int]] = []

    if not changespec.hooks:
        return killed

    for hook in changespec.hooks:
        if not hook.status_lines:
            continue
        for sl in hook.status_lines:
            if sl.suffix_type == "running_process" and sl.suffix:
                try:
                    pid = int(sl.suffix)
                except ValueError:
                    continue

                try:
                    # Send SIGTERM to process group
                    os.killpg(pid, signal.SIGTERM)
                    killed.append((hook, sl, pid))
                except ProcessLookupError:
                    # Process already dead - still mark as killed
                    killed.append((hook, sl, pid))
                except PermissionError:
                    # Can't kill - may be owned by different user
                    # Still mark as killed to clean up the state
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

                    try:
                        # Send SIGTERM to process group
                        os.killpg(pid, signal.SIGTERM)
                        killed_hooks.append((hook, sl, pid))
                    except ProcessLookupError:
                        # Process already dead - still mark as killed
                        killed_hooks.append((hook, sl, pid))
                    except PermissionError:
                        # Can't kill - may be owned by different user
                        # Still mark as killed to clean up the state
                        killed_hooks.append((hook, sl, pid))

    # Kill agent processes on comments (crs workflow)
    if changespec.comments:
        for comment in changespec.comments:
            if comment.suffix_type == "running_agent" and comment.suffix:
                pid = extract_pid_from_agent_suffix(comment.suffix)
                if pid is None:
                    continue

                try:
                    # Send SIGTERM to process group
                    os.killpg(pid, signal.SIGTERM)
                    killed_comments.append((comment, pid))
                except ProcessLookupError:
                    # Process already dead - still mark as killed
                    killed_comments.append((comment, pid))
                except PermissionError:
                    # Can't kill - may be owned by different user
                    # Still mark as killed to clean up the state
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
                try:
                    os.killpg(pid, signal.SIGTERM)
                    killed_count += 1
                except ProcessLookupError:
                    # Process already dead - still count it as handled
                    killed_count += 1
                except PermissionError:
                    # Can't kill - may be owned by different user
                    # Still count as handled to clean up the state
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

                try:
                    # Send SIGTERM to process group
                    os.killpg(pid, signal.SIGTERM)
                    killed.append((entry, sl, pid))
                except ProcessLookupError:
                    # Process already dead - still mark as killed
                    killed.append((entry, sl, pid))
                except PermissionError:
                    # Can't kill - may be owned by different user
                    # Still mark as killed to clean up the state
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
