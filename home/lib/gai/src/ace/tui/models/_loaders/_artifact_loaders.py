"""Filesystem artifact loaders (project files, done/running markers)."""

import json
from pathlib import Path

from running_field import get_claimed_workspaces

from ....hooks.processes import is_process_running
from .._timestamps import (
    normalize_to_14_digit,
    parse_timestamp_14_digit,
    parse_timestamp_from_workflow_name,
)
from ..agent import Agent, AgentType


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
                    bug=bug_by_cl_name.get(cl_name),
                    cl_num=cl_by_cl_name.get(cl_name),
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
        List of Agent objects with status="DONE".
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

                cl_name = data.get("cl_name", "unknown")
                outcome = data.get("outcome", "completed")
                if outcome == "failed":
                    status = "FAILED"
                    error_message = data.get("error")
                else:
                    status = "DONE"
                    error_message = None
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
                        step_output=data.get("step_output"),
                        workspace_num=data.get("workspace_num"),
                        bug=bug_by_cl_name.get(cl_name),
                        cl_num=cl_by_cl_name.get(cl_name),
                        error_message=error_message,
                    )
                )
            except Exception:
                continue

    return agents


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
