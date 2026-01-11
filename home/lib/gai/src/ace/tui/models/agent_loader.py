"""Functions for loading and aggregating agents from all sources."""

from datetime import datetime
from pathlib import Path

from running_field import get_claimed_workspaces

from ...changespec import (
    ChangeSpec,
    extract_pid_from_agent_suffix,
    find_all_changespecs,
)
from ...hooks.processes import is_process_running
from .agent import Agent, AgentType


def _parse_timestamp_from_suffix(suffix: str | None) -> datetime | None:
    """Parse start time from agent suffix format.

    Formats supported:
    - <agent>-<PID>-YYmmdd_HHMMSS (new format with PID)
    - <agent>-YYmmdd_HHMMSS (legacy format)
    - YYmmdd_HHMMSS (bare timestamp)
    - crs-YYmmdd_HHMMSS (CRS format)

    Args:
        suffix: The suffix value to parse.

    Returns:
        Parsed datetime, or None if parsing fails.
    """
    if suffix is None:
        return None

    # Try to extract timestamp from the end
    ts: str | None = None

    if "-" in suffix:
        parts = suffix.split("-")
        # New format: <agent>-<PID>-YYmmdd_HHMMSS
        if len(parts) >= 3:
            ts = parts[-1]
        # Legacy format: <agent>-YYmmdd_HHMMSS or crs-YYmmdd_HHMMSS
        elif len(parts) == 2:
            ts = parts[-1]
    else:
        # Bare timestamp: YYmmdd_HHMMSS
        ts = suffix

    if ts and len(ts) == 13 and ts[6] == "_":
        try:
            return datetime.strptime(ts, "%y%m%d_%H%M%S")
        except ValueError:
            pass

    return None


def _get_all_project_files() -> list[str]:
    """Get all project file paths.

    Returns:
        List of paths to .gp files.
    """
    projects_dir = Path.home() / ".gai" / "projects"

    if not projects_dir.exists():
        return []

    project_files: list[str] = []

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        project_name = project_dir.name
        gp_file = project_dir / f"{project_name}.gp"

        if gp_file.exists():
            project_files.append(str(gp_file))

    return project_files


def _load_agents_from_running_field(
    project_files: list[str],
) -> list[Agent]:
    """Load agents from RUNNING field in all project files.

    Args:
        project_files: List of project file paths.

    Returns:
        List of Agent objects from RUNNING field claims.
    """
    agents: list[Agent] = []

    for project_file in project_files:
        claims = get_claimed_workspaces(project_file)
        for claim in claims:
            # Include both regular workspaces (1-99) and loop workspaces (100-199)
            # Loop workspaces are used by fix-hook, summarize-hook, etc.
            agents.append(
                Agent(
                    agent_type=AgentType.RUNNING,
                    cl_name=claim.cl_name or "unknown",
                    project_file=project_file,
                    status="RUNNING",
                    start_time=None,  # RUNNING field doesn't have timestamps
                    workspace_num=claim.workspace_num,
                    workflow=claim.workflow,
                    pid=claim.pid,
                    # Use artifacts_timestamp as raw_suffix for prompt lookup
                    raw_suffix=claim.artifacts_timestamp,
                )
            )

    return agents


def _load_agents_from_hooks(cs: ChangeSpec) -> list[Agent]:
    """Load running agents from HOOKS field.

    Args:
        cs: The ChangeSpec to extract agents from.

    Returns:
        List of Agent objects from running hook agents.
    """
    agents: list[Agent] = []

    if not cs.hooks:
        return agents

    for hook in cs.hooks:
        if not hook.status_lines:
            continue

        for sl in hook.status_lines:
            if sl.suffix_type != "running_agent":
                continue

            # Determine agent type from suffix
            agent_type = AgentType.FIX_HOOK
            if sl.suffix and "summarize" in sl.suffix.lower():
                agent_type = AgentType.SUMMARIZE

            agents.append(
                Agent(
                    agent_type=agent_type,
                    cl_name=cs.name,
                    project_file=cs.file_path,
                    status=sl.status,
                    start_time=_parse_timestamp_from_suffix(sl.suffix),
                    hook_command=hook.display_command,
                    commit_entry_id=sl.commit_entry_num,
                    pid=extract_pid_from_agent_suffix(sl.suffix),
                    raw_suffix=sl.suffix,
                )
            )

    return agents


def _load_agents_from_mentors(cs: ChangeSpec) -> list[Agent]:
    """Load running agents from MENTORS field.

    Args:
        cs: The ChangeSpec to extract agents from.

    Returns:
        List of Agent objects from running mentor agents.
    """
    agents: list[Agent] = []

    if not cs.mentors:
        return agents

    for mentor_entry in cs.mentors:
        if not mentor_entry.status_lines:
            continue

        for msl in mentor_entry.status_lines:
            if msl.suffix_type != "running_agent":
                continue

            agents.append(
                Agent(
                    agent_type=AgentType.MENTOR,
                    cl_name=cs.name,
                    project_file=cs.file_path,
                    status=msl.status,
                    start_time=_parse_timestamp_from_suffix(msl.suffix),
                    mentor_profile=msl.profile_name,
                    mentor_name=msl.mentor_name,
                    commit_entry_id=mentor_entry.entry_id,
                    pid=extract_pid_from_agent_suffix(msl.suffix),
                    raw_suffix=msl.suffix,
                )
            )

    return agents


def _load_agents_from_comments(cs: ChangeSpec) -> list[Agent]:
    """Load running agents from COMMENTS field.

    Args:
        cs: The ChangeSpec to extract agents from.

    Returns:
        List of Agent objects from running CRS agents.
    """
    agents: list[Agent] = []

    if not cs.comments:
        return agents

    for comment in cs.comments:
        if comment.suffix_type != "running_agent":
            continue

        agents.append(
            Agent(
                agent_type=AgentType.CRS,
                cl_name=cs.name,
                project_file=cs.file_path,
                status="RUNNING",
                start_time=_parse_timestamp_from_suffix(comment.suffix),
                reviewer=comment.reviewer,
                pid=extract_pid_from_agent_suffix(comment.suffix),
                raw_suffix=comment.suffix,
            )
        )

    return agents


def load_all_agents() -> list[Agent]:
    """Load all running agents from all sources.

    Sources:
    1. RUNNING field in project files (workspace claims)
    2. HOOKS field with suffix_type="running_agent" (fix-hook, summarize-hook)
    3. MENTORS field with suffix_type="running_agent"
    4. COMMENTS field with suffix_type="running_agent" (CRS)

    Returns:
        List of Agent objects sorted by start time (most recent first),
        with agents that have no start time at the end.
    """
    agents: list[Agent] = []

    # Get all project files
    project_files = _get_all_project_files()

    # 1. Load from RUNNING field
    agents.extend(_load_agents_from_running_field(project_files))

    # 2. Load from each ChangeSpec's fields
    all_changespecs = find_all_changespecs()

    for cs in all_changespecs:
        # HOOKS - fix-hook and summarize agents
        agents.extend(_load_agents_from_hooks(cs))

        # MENTORS - mentor agents
        agents.extend(_load_agents_from_mentors(cs))

        # COMMENTS - CRS agents
        agents.extend(_load_agents_from_comments(cs))

    # Filter out agents with dead PIDs
    verified_agents: list[Agent] = []
    for agent in agents:
        if agent.pid is not None:
            if is_process_running(agent.pid):
                verified_agents.append(agent)
            # Skip agents with dead PIDs
        else:
            # Agents without PIDs (legacy entries) - still include them
            verified_agents.append(agent)

    agents = verified_agents

    # Sort by start time (most recent first), with None times at end
    def sort_key(a: Agent) -> tuple[bool, datetime]:
        if a.start_time is None:
            # Put None times at the end, sorted by a far-future date
            return (True, datetime.max)
        # Put non-None times first, sorted newest to oldest (reverse)
        return (False, a.start_time)

    agents.sort(key=sort_key, reverse=True)

    # Since we sorted reverse=True, we need to flip the None/non-None order
    # Actually, let's redo this more simply
    agents_with_time = [a for a in agents if a.start_time is not None]
    agents_without_time = [a for a in agents if a.start_time is None]

    # Sort with-time by start_time descending (most recent first)
    agents_with_time.sort(key=lambda a: a.start_time, reverse=True)  # type: ignore

    return agents_with_time + agents_without_time
