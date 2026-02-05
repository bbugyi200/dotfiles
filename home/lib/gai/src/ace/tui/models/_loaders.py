"""Agent and workflow loading functions from various sources."""

import json
from datetime import datetime
from pathlib import Path

from running_field import get_claimed_workspaces

from ...changespec import ChangeSpec, extract_pid_from_agent_suffix
from ...hooks.processes import is_process_running
from ._timestamps import (
    normalize_to_14_digit,
    parse_timestamp_14_digit,
    parse_timestamp_from_suffix,
    parse_timestamp_from_workflow_name,
)
from .agent import Agent, AgentType
from .workflow import WorkflowEntry


def get_all_project_files() -> list[str]:
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


def load_agents_from_running_field(
    project_files: list[str],
    bug_by_cl_name: dict[str, str | None],
    cl_by_cl_name: dict[str, str | None],
) -> list[Agent]:
    """Load agents from RUNNING field in all project files.

    Args:
        project_files: List of project file paths.
        bug_by_cl_name: Mapping of CL names to bug URLs.
        cl_by_cl_name: Mapping of CL names to CL numbers.

    Returns:
        List of Agent objects from RUNNING field claims.
    """
    agents: list[Agent] = []

    for project_file in project_files:
        claims = get_claimed_workspaces(project_file)
        for claim in claims:
            # Skip hook processes - they're not agents
            # Hook processes have workflow like "axe(hooks)-1" or "axe(hooks)-1a"
            if claim.workflow and claim.workflow.startswith("axe(hooks)"):
                continue

            # Detect workflow claims: workflow field starts with "workflow("
            is_workflow_claim = (
                claim.workflow
                and claim.workflow.startswith("workflow(")
                and claim.workflow.endswith(")")
            )

            if is_workflow_claim:
                # Extract workflow name from "workflow(name)"
                workflow_name = claim.workflow[9:-1]
                agent_type = AgentType.WORKFLOW
            else:
                workflow_name = claim.workflow
                agent_type = AgentType.RUNNING

            # Normalize timestamp (handles both 13-char and 14-digit formats)
            normalized_ts = normalize_to_14_digit(claim.artifacts_timestamp)
            start_time = (
                parse_timestamp_14_digit(normalized_ts)
                if normalized_ts
                else parse_timestamp_from_workflow_name(claim.workflow)
            )

            cl_name = claim.cl_name or "unknown"
            agents.append(
                Agent(
                    agent_type=agent_type,
                    cl_name=cl_name,
                    project_file=project_file,
                    status="RUNNING",
                    start_time=start_time,
                    workspace_num=claim.workspace_num,
                    workflow=workflow_name,
                    pid=claim.pid,
                    # Use normalized timestamp as raw_suffix for prompt lookup
                    raw_suffix=normalized_ts,
                    new_cl_name=claim.new_cl_name,
                    new_cl_url=(
                        cl_by_cl_name.get(claim.new_cl_name)
                        if claim.new_cl_name
                        else None
                    ),
                    bug=bug_by_cl_name.get(cl_name),
                    cl_num=cl_by_cl_name.get(cl_name),
                )
            )

    return agents


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
                    status=sl.status,
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


def load_done_agents(
    bug_by_cl_name: dict[str, str | None],
    cl_by_cl_name: dict[str, str | None],
) -> list[Agent]:
    """Load completed agents from done.json marker files.

    Scans ~/.gai/projects/*/artifacts/ace-run/*/done.json for completed agents.

    Args:
        bug_by_cl_name: Mapping of CL names to bug URLs.
        cl_by_cl_name: Mapping of CL names to CL numbers.

    Returns:
        List of Agent objects with status="NO CHANGES", "NEW CL", or "NEW PROPOSAL".
    """
    agents: list[Agent] = []
    projects_dir = Path.home() / ".gai" / "projects"

    if not projects_dir.exists():
        return agents

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        ace_run_dir = project_dir / "artifacts" / "ace-run"
        if not ace_run_dir.exists():
            continue

        for artifact_dir in ace_run_dir.iterdir():
            if not artifact_dir.is_dir():
                continue

            done_file = artifact_dir / "done.json"
            if not done_file.exists():
                continue

            try:
                with open(done_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Parse timestamp from artifact dir name (YYYYmmddHHMMSS)
                timestamp_str = artifact_dir.name
                start_time = parse_timestamp_14_digit(timestamp_str)

                # Map outcome to status string (backward compat: default to no_changes)
                outcome = data.get("outcome", "no_changes")
                if outcome == "new_cl":
                    status = "NEW CL"
                elif outcome == "new_proposal":
                    status = "NEW PROPOSAL"
                else:
                    status = "NO CHANGES"

                cl_name = data.get("cl_name", "unknown")
                agents.append(
                    Agent(
                        agent_type=AgentType.RUNNING,
                        cl_name=cl_name,
                        project_file=data.get("project_file", ""),
                        status=status,
                        start_time=start_time,
                        workflow="ace(run)",
                        raw_suffix=timestamp_str,
                        response_path=data.get("response_path"),
                        diff_path=data.get("diff_path"),
                        new_cl_name=data.get("new_cl_name"),
                        new_cl_url=(
                            cl_by_cl_name.get(data.get("new_cl_name"))
                            if data.get("new_cl_name")
                            else None
                        ),
                        proposal_id=data.get("proposal_id"),
                        workspace_num=data.get("workspace_num"),
                        bug=bug_by_cl_name.get(cl_name),
                        cl_num=cl_by_cl_name.get(cl_name),
                    )
                )
            except Exception:
                continue

    return agents


def load_workflow_states() -> list[WorkflowEntry]:
    """Load running/completed workflows from workflow_state.json marker files.

    Scans ~/.gai/projects/*/artifacts/workflow-*/*/workflow_state.json for workflows.

    Returns:
        List of WorkflowEntry objects.
    """
    from xprompt import StepState, StepStatus

    entries: list[WorkflowEntry] = []
    projects_dir = Path.home() / ".gai" / "projects"

    if not projects_dir.exists():
        return entries

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        artifacts_dir = project_dir / "artifacts"
        if not artifacts_dir.exists():
            continue

        # Look for workflow-* directories
        for workflow_dir in artifacts_dir.iterdir():
            if not workflow_dir.is_dir():
                continue
            if not workflow_dir.name.startswith("workflow-"):
                continue

            # Look for timestamp directories with workflow_state.json
            for timestamp_dir in workflow_dir.iterdir():
                if not timestamp_dir.is_dir():
                    continue

                state_file = timestamp_dir / "workflow_state.json"
                if not state_file.exists():
                    continue

                try:
                    with open(state_file, encoding="utf-8") as f:
                        data = json.load(f)

                    # Parse timestamp from directory name
                    start_time = parse_timestamp_14_digit(timestamp_dir.name)
                    if start_time is None:
                        # Try ISO format from state file
                        iso_time = data.get("start_time")
                        if iso_time:
                            try:
                                start_time = datetime.fromisoformat(iso_time)
                            except ValueError:
                                pass

                    # Map status string to display status
                    status = data.get("status", "running")
                    if status == "waiting_hitl":
                        display_status = "WAITING INPUT"
                    elif status == "completed":
                        display_status = "COMPLETED"
                    elif status == "failed":
                        display_status = "FAILED"
                    else:
                        display_status = "RUNNING"

                    # Parse step states
                    steps: list[StepState] = []
                    for step_data in data.get("steps", []):
                        step_status = StepStatus(step_data.get("status", "pending"))
                        steps.append(
                            StepState(
                                name=step_data.get("name", ""),
                                status=step_status,
                                output=step_data.get("output"),
                                error=step_data.get("error"),
                            )
                        )

                    # Build project file path
                    project_name = project_dir.name
                    project_file = str(project_dir / f"{project_name}.gp")

                    # Extract PID if available
                    pid = data.get("pid")

                    # Read appears_as_agent flag
                    appears_as_agent = data.get("appears_as_agent", False)

                    entries.append(
                        WorkflowEntry(
                            workflow_name=data.get("workflow_name", "unknown"),
                            cl_name=data.get("context", {}).get("cl_name", "unknown"),
                            project_file=project_file,
                            status=display_status,
                            current_step=data.get("current_step_index", 0),
                            total_steps=len(steps),
                            steps=steps,
                            start_time=start_time,
                            artifacts_dir=str(timestamp_dir),
                            pid=pid,
                            appears_as_agent=appears_as_agent,
                        )
                    )
                except Exception:
                    continue

    return entries


def load_running_home_agents() -> list[Agent]:
    """Load running home mode agents from running.json marker files.

    Scans ~/.gai/projects/home/artifacts/ace-run/*/running.json for running agents.
    Only includes agents with PIDs that are still running.

    Returns:
        List of Agent objects with status="RUNNING".
    """
    agents: list[Agent] = []
    home_ace_run_dir = (
        Path.home() / ".gai" / "projects" / "home" / "artifacts" / "ace-run"
    )

    if not home_ace_run_dir.exists():
        return agents

    for artifact_dir in home_ace_run_dir.iterdir():
        if not artifact_dir.is_dir():
            continue

        running_file = artifact_dir / "running.json"
        if not running_file.exists():
            continue

        try:
            with open(running_file, encoding="utf-8") as f:
                data = json.load(f)

            # Verify PID is still running
            pid = data.get("pid")
            if pid is None or not is_process_running(pid):
                # Process died - clean up the stale marker
                try:
                    running_file.unlink()
                except OSError:
                    pass
                continue

            # Parse timestamp from artifact dir name (YYYYmmddHHMMSS)
            timestamp_str = artifact_dir.name
            start_time = parse_timestamp_14_digit(timestamp_str)

            cl_name = data.get("cl_name", "~")
            agents.append(
                Agent(
                    agent_type=AgentType.RUNNING,
                    cl_name=cl_name,
                    project_file=str(
                        Path.home() / ".gai" / "projects" / "home" / "home.gp"
                    ),
                    status="RUNNING",
                    start_time=start_time,
                    workflow="ace(run)",
                    pid=pid,
                    raw_suffix=timestamp_str,
                )
            )
        except Exception:
            continue

    return agents


def load_workflow_agents() -> list[Agent]:
    """Load workflow entries as Agent objects for display in Agents tab.

    Converts WorkflowEntry objects from load_workflow_states() to Agent objects
    so they can be displayed alongside other agents.

    Returns:
        List of Agent objects with agent_type=AgentType.WORKFLOW.
    """
    entries = load_workflow_states()
    agents: list[Agent] = []

    for entry in entries:
        # Extract timestamp from artifacts_dir path for raw_suffix
        # artifacts_dir format: ~/.gai/projects/<project>/artifacts/workflow-<name>/<timestamp>
        raw_suffix = None
        if entry.artifacts_dir:
            raw_suffix = Path(entry.artifacts_dir).name

        agents.append(
            Agent(
                agent_type=AgentType.WORKFLOW,
                cl_name=entry.cl_name,
                project_file=entry.project_file,
                status=entry.status,
                start_time=entry.start_time,
                workflow=entry.workflow_name,
                raw_suffix=raw_suffix,
                pid=entry.pid,
                appears_as_agent=entry.appears_as_agent,
                artifacts_dir=entry.artifacts_dir,
            )
        )

    return agents


def load_workflow_agent_steps() -> list[Agent]:
    """Load agent step entries from workflow agent_step_*.json marker files.

    Scans ~/.gai/projects/*/artifacts/workflow-*/*/agent_step_*.json for agent steps.

    Returns:
        List of Agent objects with agent_type=AgentType.WORKFLOW representing
        individual agent steps within workflows.
    """
    agents: list[Agent] = []
    projects_dir = Path.home() / ".gai" / "projects"

    if not projects_dir.exists():
        return agents

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        artifacts_dir = project_dir / "artifacts"
        if not artifacts_dir.exists():
            continue

        # Look for workflow-* directories
        for workflow_dir in artifacts_dir.iterdir():
            if not workflow_dir.is_dir():
                continue
            if not workflow_dir.name.startswith("workflow-"):
                continue

            # Look for timestamp directories with agent_step_*.json files
            for timestamp_dir in workflow_dir.iterdir():
                if not timestamp_dir.is_dir():
                    continue

                # Find all prompt step marker files
                for marker_file in timestamp_dir.glob("prompt_step_*.json"):
                    try:
                        with open(marker_file, encoding="utf-8") as f:
                            data = json.load(f)

                        # Parse timestamp from directory name
                        start_time = parse_timestamp_14_digit(timestamp_dir.name)

                        # Build project file path
                        project_name = project_dir.name
                        project_file = str(project_dir / f"{project_name}.gp")

                        # Map status to display string
                        status = data.get("status", "completed")
                        if status == "waiting_hitl":
                            display_status = "WAITING INPUT"
                        elif status == "completed":
                            display_status = "COMPLETED"
                        elif status == "in_progress":
                            display_status = "RUNNING"
                        elif status == "failed":
                            display_status = "FAILED"
                        else:
                            display_status = status.upper()

                        workflow_name = data.get("workflow_name", "unknown")
                        step_name = data.get("step_name", "unknown")

                        # Read new fields from marker (with backward compat defaults)
                        step_type = data.get("step_type", "agent")
                        step_source = data.get("step_source")
                        step_output = data.get("output")
                        step_index = data.get("step_index")
                        total_steps = data.get("total_steps")
                        parent_step_index = data.get("parent_step_index")
                        parent_total_steps = data.get("parent_total_steps")
                        is_hidden = data.get("hidden", False)
                        is_pre_prompt_step = data.get("is_pre_prompt_step", False)

                        # Skip hidden workflow steps - they should never appear
                        # in the Agents tab
                        if is_hidden:
                            continue

                        # Skip pre-prompt steps from embedded workflows
                        if is_pre_prompt_step:
                            continue

                        # Read artifacts_dir and diff_path from marker
                        artifacts_dir_from_marker = data.get("artifacts_dir")
                        diff_path = data.get("diff_path")

                        agents.append(
                            Agent(
                                agent_type=AgentType.WORKFLOW,
                                cl_name=step_name,
                                project_file=project_file,
                                status=display_status,
                                start_time=start_time,
                                workflow=workflow_name,
                                raw_suffix=timestamp_dir.name,
                                parent_workflow=workflow_name,
                                parent_timestamp=timestamp_dir.name,
                                step_name=step_name,
                                step_type=step_type,
                                step_source=step_source,
                                step_output=step_output,
                                step_index=step_index,
                                total_steps=total_steps,
                                parent_step_index=parent_step_index,
                                parent_total_steps=parent_total_steps,
                                is_hidden_step=is_hidden,
                                artifacts_dir=artifacts_dir_from_marker,
                                diff_path=diff_path,
                            )
                        )
                    except Exception:
                        continue

    return agents
