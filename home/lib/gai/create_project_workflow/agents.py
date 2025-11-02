"""Agent implementations for the create-project workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import HumanMessage
from rich_utils import print_status

from .prompts import build_planner_prompt
from .state import CreateProjectState


def _validate_project_plan(plan_content: str) -> tuple[bool, str]:
    """
    Validate that the project plan follows the expected format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not plan_content:
        return False, "Project plan is empty"

    # Check for at least one first-level bullet (*)
    lines = plan_content.split("\n")
    has_first_level_bullet = any(line.strip().startswith("* ") for line in lines)

    if not has_first_level_bullet:
        return (
            False,
            "Project plan must contain at least one first-level bullet (*) representing a CL",
        )

    return True, ""


def run_planner_agent(state: CreateProjectState) -> CreateProjectState:
    """Run the project planner agent to generate the project plan."""
    print_status("Running project planner agent...", "progress")

    # Build prompt for planner
    prompt = build_planner_prompt(state)

    # Send prompt to Gemini with big model (as requested)
    model = GeminiCommandWrapper(model_size="big")
    model.set_logging_context(
        agent_type="project_planner",
        iteration=1,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print_status("Project planner agent response received", "success")

    # Save the planner agent's response
    artifacts_dir = state["artifacts_dir"]
    planner_response_path = os.path.join(artifacts_dir, "planner_response.txt")
    with open(planner_response_path, "w") as f:
        f.write(response.content)

    print(f"Saved planner response to: {planner_response_path}")

    # Validate the project plan
    is_valid, error_message = _validate_project_plan(response.content)

    if not is_valid:
        print_status(f"Project plan validation failed: {error_message}", "error")
        return {
            **state,
            "success": False,
            "failure_reason": f"Project plan validation failed: {error_message}",
            "messages": state["messages"] + messages + [response],
        }

    # Write the project plan to the projects file
    projects_file = state["projects_file"]
    try:
        with open(projects_file, "w") as f:
            f.write(response.content)
        print_status(f"Project plan written to: {projects_file}", "success")
    except Exception as e:
        print_status(f"Failed to write project plan: {e}", "error")
        return {
            **state,
            "success": False,
            "failure_reason": f"Failed to write project plan to {projects_file}: {str(e)}",
            "messages": state["messages"] + messages + [response],
        }

    # Workflow succeeded
    return {
        **state,
        "success": True,
        "failure_reason": None,
        "messages": state["messages"] + messages + [response],
    }
