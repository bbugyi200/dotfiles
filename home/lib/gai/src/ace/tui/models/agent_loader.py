"""Functions for loading and aggregating agents from all sources."""

from datetime import datetime

from ...changespec import find_all_changespecs
from ...hooks.processes import is_process_running
from ._loaders import (
    get_all_project_files,
    load_agents_from_comments,
    load_agents_from_hooks,
    load_agents_from_mentors,
    load_agents_from_running_field,
    load_done_agents,
    load_running_home_agents,
    load_workflow_agent_steps,
    load_workflow_agents,
    load_workflow_states,
)
from ._timestamps import (
    extract_timestamp_from_workflow,
    extract_timestamp_str_from_suffix,
)
from .agent import Agent, AgentType
from .workflow import WorkflowEntry


def _get_status_priority(status: str) -> int:
    """Return sort priority for agent status (lower = appears first).

    Completed/failed steps appear before running/waiting steps.
    """
    if status in ("COMPLETED", "FAILED"):
        return 0
    # RUNNING, WAITING INPUT, and any other status
    return 1


def load_all_workflows() -> list[WorkflowEntry]:
    """Load all workflow entries from workflow_state.json files.

    Returns:
        List of WorkflowEntry objects sorted by start time (most recent first).
    """
    workflows = load_workflow_states()

    # Sort by start time (most recent first)
    workflows_with_time = [w for w in workflows if w.start_time is not None]
    workflows_without_time = [w for w in workflows if w.start_time is None]

    workflows_with_time.sort(key=lambda w: w.start_time, reverse=True)  # type: ignore

    return workflows_with_time + workflows_without_time


def load_all_agents() -> list[Agent]:
    """Load all running agents from all sources.

    Sources:
    1. RUNNING field in project files (workspace claims)
    2. HOOKS field with suffix_type="running_agent" (fix-hook, summarize-hook)
    3. MENTORS field with suffix_type="running_agent"
    4. COMMENTS field with suffix_type="running_agent" (CRS)
    5. done.json marker files (DONE agents)

    Returns:
        List of Agent objects sorted by start time (most recent first),
        with agents that have no start time at the end.
    """
    agents: list[Agent] = []

    # Get all project files
    project_files = get_all_project_files()

    # Load all ChangeSpecs early to build bug lookup
    all_changespecs = find_all_changespecs()

    # Build bug URL lookup by CL name
    bug_by_cl_name: dict[str, str | None] = {}
    for cs in all_changespecs:
        if cs.bug:
            bug_id = cs.bug.removeprefix("http://b/")
            bug_by_cl_name[cs.name] = f"http://b/{bug_id}"

    # Build CL number lookup by CL name
    cl_by_cl_name: dict[str, str | None] = {}
    for cs in all_changespecs:
        if cs.cl:
            cl_by_cl_name[cs.name] = cs.cl

    # 1. Load from RUNNING field
    agents.extend(
        load_agents_from_running_field(project_files, bug_by_cl_name, cl_by_cl_name)
    )

    # 1a. Load completed (DONE) agents
    agents.extend(load_done_agents(bug_by_cl_name, cl_by_cl_name))

    # 1b. Load running home mode agents (from running.json markers)
    agents.extend(load_running_home_agents())

    # 1c. Load workflow entries as agents
    agents.extend(load_workflow_agents())

    # 1d. Load workflow agent steps (individual agent steps within workflows)
    workflow_agent_steps = load_workflow_agent_steps()

    # 2. Load from each ChangeSpec's fields
    for cs in all_changespecs:
        stripped_bug_id = cs.bug.removeprefix("http://b/") if cs.bug else None
        bug = f"http://b/{stripped_bug_id}" if stripped_bug_id else None
        cl_num = cs.cl

        # HOOKS - fix-hook and summarize agents
        agents.extend(load_agents_from_hooks(cs, bug, cl_num))

        # MENTORS - mentor agents
        agents.extend(load_agents_from_mentors(cs, bug, cl_num))

        # COMMENTS - CRS agents
        agents.extend(load_agents_from_comments(cs, bug, cl_num))

    # Filter out agents with dead PIDs (but keep completed agents)
    verified_agents: list[Agent] = []
    # Statuses that indicate completed work (don't filter these by PID)
    completed_statuses = (
        "DONE",
        "FAILED",
        "COMPLETED",
        "NO CHANGES",
        "NEW CL",
        "NEW PROPOSAL",
    )
    for agent in agents:
        # Completed agents represent finished work - always include them
        if agent.status in completed_statuses:
            verified_agents.append(agent)
        elif agent.pid is not None:
            if is_process_running(agent.pid):
                verified_agents.append(agent)
            # Skip agents with dead PIDs
        else:
            # Agents without PIDs (legacy entries) - still include them
            verified_agents.append(agent)

    agents = verified_agents

    # Deduplicate loop-spawned agents by timestamp
    # Loop agents have different PIDs in RUNNING (loop process) vs ChangeSpec (subprocess),
    # but share the same timestamp. Match by (cl_name, timestamp) to deduplicate.

    # Build index of ChangeSpec agents (non-RUNNING) by (cl_name, timestamp)
    changespec_agents_by_key: dict[tuple[str, str], Agent] = {}
    for agent in agents:
        if agent.agent_type != AgentType.RUNNING:
            ts = extract_timestamp_str_from_suffix(agent.raw_suffix)
            if ts:
                key = (agent.cl_name, ts)
                changespec_agents_by_key[key] = agent

    # Match RUNNING entries with ChangeSpec entries
    # Keep RUNNING entries only if they don't match a ChangeSpec entry
    final_agents: list[Agent] = []
    for agent in agents:
        if agent.agent_type == AgentType.RUNNING:
            workflow = agent.workflow or ""
            # Check if this is an axe agent workflow
            is_axe_agent = any(
                workflow.startswith(prefix)
                for prefix in ["axe(mentor)", "axe(fix-hook)", "axe(crs)"]
            )
            if is_axe_agent:
                ts = extract_timestamp_from_workflow(workflow)
                if ts:
                    key = (agent.cl_name, ts)
                    if key in changespec_agents_by_key:
                        # Match found! Copy workspace_num and workflow, skip RUNNING entry
                        matched = changespec_agents_by_key[key]
                        if matched.workspace_num is None:
                            matched.workspace_num = agent.workspace_num
                        if matched.workflow is None:
                            matched.workflow = agent.workflow
                        continue  # Don't add RUNNING entry (deduplicated)
            # Non-loop workflow or no match found - keep RUNNING entry
            final_agents.append(agent)
        else:
            final_agents.append(agent)

    agents = final_agents

    # Deduplicate workflow entries: match by raw_suffix (timestamp)
    # Prefer workflow_state.json entries (accurate status), but copy
    # workspace_num and cl_name from RUNNING field entries
    seen_suffixes: dict[str, Agent] = {}
    for agent in agents:
        if agent.agent_type == AgentType.WORKFLOW and agent.raw_suffix:
            if agent.raw_suffix in seen_suffixes:
                existing = seen_suffixes[agent.raw_suffix]
                # Copy workspace_num from RUNNING field entry
                if existing.workspace_num is None and agent.workspace_num is not None:
                    existing.workspace_num = agent.workspace_num
                # Copy cl_name if existing has "unknown"
                if existing.cl_name == "unknown" and agent.cl_name != "unknown":
                    existing.cl_name = agent.cl_name
                # Prefer non-RUNNING status from workflow_state.json (accurate status)
                if existing.status == "RUNNING" and agent.status != "RUNNING":
                    existing.status = agent.status
                # Copy PID from workflow_state.json if existing has none
                if existing.pid is None and agent.pid is not None:
                    existing.pid = agent.pid
            else:
                seen_suffixes[agent.raw_suffix] = agent

    # Filter out duplicates
    agents = [
        a
        for a in agents
        if a.agent_type != AgentType.WORKFLOW
        or a.raw_suffix not in seen_suffixes
        or seen_suffixes.get(a.raw_suffix) is a
    ]

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

    sorted_agents = agents_with_time + agents_without_time

    # Insert workflow agent steps immediately after their parent workflows
    if workflow_agent_steps:
        result: list[Agent] = []
        for agent in sorted_agents:
            result.append(agent)
            # Check if any agent steps belong to this agent (matching workflow+timestamp)
            if agent.agent_type == AgentType.WORKFLOW or (
                agent.workflow and agent.workflow.startswith("workflow-")
            ):
                # Find matching agent steps by timestamp
                matching_steps = [
                    step
                    for step in workflow_agent_steps
                    if step.parent_timestamp == agent.raw_suffix
                ]
                # Sort by workflow position: main steps first, then substeps
                matching_steps.sort(
                    key=lambda s: (
                        # Primary: completed/failed steps (0) before running/waiting steps (1)
                        _get_status_priority(s.status),
                        # Secondary: position in workflow (parent_step_index for
                        # substeps, step_index for main steps)
                        (
                            s.parent_step_index
                            if s.parent_step_index is not None
                            else (s.step_index or 0)
                        ),
                        # Tertiary: substeps (1) come after main steps (0)
                        1 if s.parent_step_index is not None else 0,
                        # Quaternary: order within substeps
                        s.step_index or 0,
                    )
                )
                result.extend(matching_steps)
        return result

    return sorted_agents
