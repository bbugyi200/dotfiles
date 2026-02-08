"""ChangeSpec field agent loaders (HOOKS, MENTORS, COMMENTS)."""

from ....changespec import ChangeSpec, extract_pid_from_agent_suffix
from .._timestamps import parse_timestamp_from_suffix
from ..agent import Agent, AgentType


def load_agents_from_hooks(
    cs: ChangeSpec, bug: str | None, cl_num: str | None
) -> list[Agent]:
    """Load running agents from HOOKS field.

    Args:
        cs: The ChangeSpec to extract agents from.
        bug: Bug URL from the ChangeSpec, or None.
        cl_num: CL number from the ChangeSpec, or None.

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
            # Capture running agents AND failed agents with error suffix
            if sl.suffix_type not in ("running_agent", "error"):
                continue

            # Extract error message for failed agents (include summary if available)
            error_message = None
            if sl.suffix_type == "error":
                if sl.summary:
                    error_message = f"{sl.suffix}\n\nOutput: {sl.summary}"
                else:
                    error_message = sl.suffix

            # Determine agent type from suffix
            # - Running summarize agents: suffix contains "summarize_hook-<PID>-<timestamp>"
            # - Failed summarize agents: suffix is "summarize-hook Failed"
            agent_type = AgentType.FIX_HOOK
            if sl.suffix:
                suffix_lower = sl.suffix.lower()
                if "summarize" in suffix_lower:
                    agent_type = AgentType.SUMMARIZE

            agents.append(
                Agent(
                    agent_type=agent_type,
                    cl_name=cs.name,
                    project_file=cs.file_path,
                    # Fix-hook agents that are running should have RUNNING status,
                    # not inherit the hook's FAILED status
                    status=(
                        "RUNNING" if sl.suffix_type == "running_agent" else sl.status
                    ),
                    start_time=parse_timestamp_from_suffix(sl.suffix),
                    hook_command=hook.display_command,
                    commit_entry_id=sl.commit_entry_num,
                    pid=extract_pid_from_agent_suffix(sl.suffix),
                    raw_suffix=sl.suffix,
                    bug=bug,
                    cl_num=cl_num,
                    error_message=error_message,
                )
            )

    return agents


def load_agents_from_mentors(
    cs: ChangeSpec, bug: str | None, cl_num: str | None
) -> list[Agent]:
    """Load running agents from MENTORS field.

    Args:
        cs: The ChangeSpec to extract agents from.
        bug: Bug URL from the ChangeSpec, or None.
        cl_num: CL number from the ChangeSpec, or None.

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
                    start_time=parse_timestamp_from_suffix(msl.suffix),
                    mentor_profile=msl.profile_name,
                    mentor_name=msl.mentor_name,
                    commit_entry_id=mentor_entry.entry_id,
                    pid=extract_pid_from_agent_suffix(msl.suffix),
                    raw_suffix=msl.suffix,
                    bug=bug,
                    cl_num=cl_num,
                )
            )

    return agents


def load_agents_from_comments(
    cs: ChangeSpec, bug: str | None, cl_num: str | None
) -> list[Agent]:
    """Load running agents from COMMENTS field.

    Args:
        cs: The ChangeSpec to extract agents from.
        bug: Bug URL from the ChangeSpec, or None.
        cl_num: CL number from the ChangeSpec, or None.

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
                start_time=parse_timestamp_from_suffix(comment.suffix),
                reviewer=comment.reviewer,
                pid=extract_pid_from_agent_suffix(comment.suffix),
                raw_suffix=comment.suffix,
                bug=bug,
                cl_num=cl_num,
            )
        )

    return agents
