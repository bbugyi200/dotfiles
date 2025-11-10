"""Agent implementations for the create-project workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import print_status
from shared_utils import ensure_str_content

from .prompts import build_planner_prompt
from .state import CreateProjectState


def _validate_project_plan(plan_content: str, project_name: str) -> tuple[bool, str]:
    """
    Validate that the project plan follows the expected ChangeSpec format.

    Args:
        plan_content: The generated project plan content
        project_name: The expected project name for all ChangeSpecs

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not plan_content:
        return False, "Project plan is empty"

    # Check for at least one ChangeSpec (must have NAME: field)
    lines = plan_content.split("\n")
    has_name_field = any(line.strip().startswith("NAME: ") for line in lines)

    if not has_name_field:
        return (
            False,
            "Project plan must contain at least one ChangeSpec with a NAME: field",
        )

    # Check for required fields in each ChangeSpec
    required_fields = ["NAME:", "DESCRIPTION:", "PARENT:", "CL:", "STATUS:"]
    for field in required_fields:
        if not any(line.strip().startswith(field) for line in lines):
            return (
                False,
                f"Project plan must contain at least one ChangeSpec with a {field} field",
            )

    # Validate that all NAME fields start with project_name_
    name_lines = [line for line in lines if line.strip().startswith("NAME: ")]
    expected_prefix = f"{project_name}_"

    for name_line in name_lines:
        # Extract the name value (everything after "NAME: ")
        name_value = name_line.strip()[6:].strip()  # 6 is len("NAME: ")
        if not name_value.startswith(expected_prefix):
            return (
                False,
                f"All ChangeSpecs must have NAME starting with '{expected_prefix}'. Found NAME: {name_value}",
            )

        # Validate that there's a suffix after the prefix
        suffix = name_value[len(expected_prefix) :]
        if not suffix:
            return (
                False,
                f"NAME must have a descriptive suffix after '{expected_prefix}'. Found NAME: {name_value}",
            )

        # Validate suffix contains only words separated by underscores
        if not all(
            word.replace("_", "").replace("-", "").isalnum()
            for word in suffix.split("_")
        ):
            return (
                False,
                f"NAME suffix should contain only words separated by underscores. Found: {name_value}",
            )

    # Validate STATUS is set correctly based on PARENT and TEST TARGETS
    # Build a map of ChangeSpecs with their PARENT, TEST TARGETS, and STATUS
    changespecs: list[dict[str, str | None]] = []
    current_changespec: dict[str, str | None] = {}
    in_test_targets = False

    for line in lines:
        if line.strip().startswith("NAME: "):
            if current_changespec:
                changespecs.append(current_changespec)
            current_changespec = {
                "NAME": line.strip()[6:].strip(),
                "TEST_TARGETS": None,
            }
            in_test_targets = False
        elif line.strip().startswith("PARENT: "):
            current_changespec["PARENT"] = line.strip()[8:].strip()
            in_test_targets = False
        elif line.strip().startswith("STATUS: "):
            current_changespec["STATUS"] = line.strip()[8:].strip()
            in_test_targets = False
        elif line.strip().startswith("TEST TARGETS:"):
            # Check if there's a value on the same line
            rest = line.strip()[13:].strip()
            if rest:
                current_changespec["TEST_TARGETS"] = rest
            else:
                # Multi-line format or omitted
                current_changespec["TEST_TARGETS"] = "MULTILINE_OR_OMITTED"
            in_test_targets = True
        elif in_test_targets and line.startswith("  ") and line.strip():
            # Continuation line for TEST TARGETS
            current_changespec["TEST_TARGETS"] = "MULTILINE_OR_OMITTED"

    if current_changespec:
        changespecs.append(current_changespec)

    # Validate each ChangeSpec's STATUS
    for cs in changespecs:
        if "PARENT" not in cs or "STATUS" not in cs:
            continue

        parent = cs["PARENT"]
        status = cs["STATUS"]
        test_targets = cs.get("TEST_TARGETS")
        name = cs.get("NAME", "unknown")

        # Determine expected status based on PARENT and TEST TARGETS
        # TEST TARGETS = None means no tests (EZ workflow)
        # TEST TARGETS omitted or has values means TDD workflow
        is_ez = test_targets == "None"

        if parent == "None":
            expected_status = "Unstarted (EZ)" if is_ez else "Unstarted (TDD)"
            if status != expected_status:
                return (
                    False,
                    f"ChangeSpec '{name}' has PARENT: None and TEST TARGETS: {test_targets} "
                    f"but STATUS: {status}. Expected STATUS: {expected_status}",
                )
        else:
            expected_status = "Blocked (EZ)" if is_ez else "Blocked (TDD)"
            if status != expected_status:
                return (
                    False,
                    f"ChangeSpec '{name}' has PARENT: {parent} and TEST TARGETS: {test_targets} "
                    f"but STATUS: {status}. Expected STATUS: {expected_status}",
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
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print_status("Project planner agent response received", "success")

    # Save the planner agent's response
    artifacts_dir = state["artifacts_dir"]
    planner_response_path = os.path.join(artifacts_dir, "planner_response.txt")
    with open(planner_response_path, "w") as f:
        f.write(ensure_str_content(response.content))

    print(f"Saved planner response to: {planner_response_path}")

    # Validate the project plan
    project_name = state["project_name"]
    is_valid, error_message = _validate_project_plan(
        ensure_str_content(response.content), project_name
    )

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
    bug_id = state["bug_id"]
    try:
        with open(projects_file, "w") as f:
            # Write BUG field at the top
            f.write(f"BUG: {bug_id}\n\n\n")
            # Write the rest of the project plan
            f.write(ensure_str_content(response.content))
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
