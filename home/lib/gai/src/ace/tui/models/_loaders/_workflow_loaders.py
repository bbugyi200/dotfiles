"""Workflow state and step loaders."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ....hooks.processes import is_process_running
from .._timestamps import parse_timestamp_14_digit
from ..agent import Agent, AgentType
from ..workflow import WorkflowEntry


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
                        display_status = "DONE"
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

                    # Check PID liveness for active workflows
                    if (
                        display_status in ("RUNNING", "WAITING INPUT")
                        and pid is not None
                        and not is_process_running(pid)
                    ):
                        display_status = "FAILED"

                    # Read appears_as_agent and is_anonymous flags
                    appears_as_agent = data.get("appears_as_agent", False)
                    is_anonymous = data.get("is_anonymous", False)

                    # Extract diff_path from the last step's first path-typed output
                    diff_path = None
                    steps_list = data.get("steps", [])
                    if steps_list:
                        last_step = steps_list[-1]
                        output_types = last_step.get("output_types") or {}
                        step_output = last_step.get("output")
                        if output_types and isinstance(step_output, dict):
                            for field_name, field_type in output_types.items():
                                if field_type == "path":
                                    path_value = step_output.get(field_name)
                                    if path_value:
                                        diff_path = str(path_value)
                                        break

                    # Fallback: check for any path-looking key in last step output
                    if not diff_path and steps_list:
                        last_output = steps_list[-1].get("output")
                        if isinstance(last_output, dict) and last_output.get(
                            "diff_path"
                        ):
                            diff_path = str(last_output["diff_path"])

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
                            is_anonymous=is_anonymous,
                            diff_path=diff_path,
                            error_message=data.get("error"),
                        )
                    )
                except Exception:
                    continue

    return entries


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

        # Extract step_output from last completed step so that
        # appears_as_agent workflows expose meta_* fields in the TUI.
        step_output: dict[str, Any] | None = None
        if entry.steps:
            for step in reversed(entry.steps):
                if step.output and isinstance(step.output, dict):
                    step_output = step.output
                    break

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
                is_anonymous=entry.is_anonymous,
                artifacts_dir=entry.artifacts_dir,
                diff_path=entry.diff_path,
                error_message=entry.error_message,
                step_output=step_output,
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
            if not (
                workflow_dir.name.startswith("workflow-")
                or workflow_dir.name == "ace-run"
            ):
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
                            display_status = "DONE"
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

                        # Skip pre-prompt steps from embedded workflows
                        if is_pre_prompt_step:
                            continue

                        # Read artifacts_dir, diff_path, and error from marker
                        artifacts_dir_from_marker = data.get("artifacts_dir")
                        diff_path = data.get("diff_path")
                        error_message = data.get("error")

                        # Also extract diff_path from output_types if not already set
                        if not diff_path:
                            output_types = data.get("output_types") or {}
                            if output_types and isinstance(step_output, dict):
                                for field_name, field_type in output_types.items():
                                    if field_type == "path":
                                        path_value = step_output.get(field_name)
                                        if path_value:
                                            diff_path = str(path_value)
                                            break

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
                                error_message=error_message,
                            )
                        )
                    except Exception:
                        continue

    return agents
