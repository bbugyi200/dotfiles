"""Workflow nodes for the new-change workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rich_utils import print_status, print_workflow_failure, print_workflow_success
from shared_utils import (
    create_artifacts_directory,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
)

from .state import NewChangeState


def initialize_new_change_workflow(state: NewChangeState) -> NewChangeState:
    """
    Initialize the new-change workflow.

    Parses the ChangeSpec text and sets up artifacts directory.
    """
    changespec_text = state["changespec_text"]

    # Parse the ChangeSpec to extract NAME and DESCRIPTION
    try:
        lines = changespec_text.split("\n")
        cl_name = None
        cl_description_lines = []
        in_description = False

        for line in lines:
            if line.startswith("NAME:"):
                cl_name = line.split(":", 1)[1].strip()
            elif line.startswith("DESCRIPTION:"):
                in_description = True
            elif in_description:
                if line.startswith("  "):
                    # Part of description (2-space indented)
                    cl_description_lines.append(line[2:])  # Remove indent
                elif line and not line.startswith(" "):
                    # New field, end of description
                    in_description = False

        if not cl_name:
            return {
                **state,
                "failure_reason": "No NAME field found in ChangeSpec",
            }

        cl_description = "\n".join(cl_description_lines).strip()

        # Generate workflow tag and create artifacts directory
        workflow_tag = generate_workflow_tag()
        artifacts_dir = create_artifacts_directory()
        print_status(f"Created artifacts directory: {artifacts_dir}", "success")
        print_status(f"Generated workflow tag: {workflow_tag}", "info")

        # Initialize gai.md log
        initialize_gai_log(artifacts_dir, "new-change", workflow_tag)

        return {
            **state,
            "cl_name": cl_name,
            "cl_description": cl_description,
            "artifacts_dir": artifacts_dir,
            "workflow_tag": workflow_tag,
        }

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error parsing ChangeSpec: {e}",
        }


def handle_success(state: NewChangeState) -> NewChangeState:
    """Handle successful workflow completion."""
    artifacts_dir = state.get("artifacts_dir")
    workflow_tag = state.get("workflow_tag")

    if artifacts_dir and workflow_tag:
        finalize_gai_log(artifacts_dir, "new-change", workflow_tag, success=True)

    print_workflow_success("new-change", "New-change workflow completed successfully!")
    return state


def handle_failure(state: NewChangeState) -> NewChangeState:
    """Handle workflow failure."""
    artifacts_dir = state.get("artifacts_dir")
    workflow_tag = state.get("workflow_tag")

    if artifacts_dir and workflow_tag:
        finalize_gai_log(artifacts_dir, "new-change", workflow_tag, success=False)

    failure_reason = state.get("failure_reason", "Unknown error")
    print_workflow_failure("new-change", "New-change workflow failed", failure_reason)
    return state
