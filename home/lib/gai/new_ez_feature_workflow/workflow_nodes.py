"""Workflow nodes for the new-ez-feature workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rich_utils import print_status, print_workflow_failure, print_workflow_success
from shared_utils import (
    copy_design_docs_locally,
    create_artifacts_directory,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
)

from .state import NewEzFeatureState


def initialize_new_ez_feature_workflow(state: NewEzFeatureState) -> NewEzFeatureState:
    """
    Initialize the new-ez-feature workflow.

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
                # Check if this is a new field (non-empty, non-whitespace, doesn't start with space)
                if line and line.strip() and not line.startswith(" "):
                    # New field, end of description
                    in_description = False
                else:
                    # Part of description - could be indented line or blank line
                    if line.startswith("  "):
                        # Indented line - remove 2-space indent
                        cl_description_lines.append(line[2:])
                    elif not line or not line.strip():
                        # Blank line - preserve as empty string
                        cl_description_lines.append("")
                    # Else: line with 1 space or other whitespace - skip it

        if not cl_name:
            return {
                **state,
                "failure_reason": "No NAME field found in ChangeSpec",
            }

        # Join and strip only trailing whitespace to preserve internal blank lines
        cl_description = "\n".join(cl_description_lines).rstrip()

        # Generate workflow tag and create artifacts directory
        workflow_tag = generate_workflow_tag()
        artifacts_dir = create_artifacts_directory()
        print_status(f"Created artifacts directory: {artifacts_dir}", "success")
        print_status(f"Generated workflow tag: {workflow_tag}", "info")

        # Initialize gai.md log
        initialize_gai_log(artifacts_dir, "new-ez-feature", workflow_tag)

        # Copy design documents and context files to local .gai/context/ directory
        design_docs_dir = state.get("design_docs_dir")
        context_file_directory = state.get("context_file_directory")

        # Prepare list of source directories to copy from
        source_dirs = [design_docs_dir, context_file_directory]

        # Copy all design docs to local directory
        local_designs_dir = copy_design_docs_locally(source_dirs)

        return {
            **state,
            "cl_name": cl_name,
            "cl_description": cl_description,
            "artifacts_dir": artifacts_dir,
            "workflow_tag": workflow_tag,
            "context_file_directory": local_designs_dir,
        }

    except Exception as e:
        return {
            **state,
            "failure_reason": f"Error initializing workflow: {e}",
        }


def handle_success(state: NewEzFeatureState) -> NewEzFeatureState:
    """Handle successful workflow completion."""
    artifacts_dir = state.get("artifacts_dir")
    workflow_tag = state.get("workflow_tag")

    if artifacts_dir and workflow_tag:
        finalize_gai_log(artifacts_dir, "new-ez-feature", workflow_tag, success=True)

    print_workflow_success(
        "new-ez-feature", "New-ez-feature workflow completed successfully!"
    )
    return {**state, "success": True}


def handle_failure(state: NewEzFeatureState) -> NewEzFeatureState:
    """Handle workflow failure."""
    artifacts_dir = state.get("artifacts_dir")
    workflow_tag = state.get("workflow_tag")

    if artifacts_dir and workflow_tag:
        finalize_gai_log(artifacts_dir, "new-ez-feature", workflow_tag, success=False)

    failure_reason = state.get("failure_reason", "Unknown error")
    print_workflow_failure(
        "new-ez-feature", "New-ez-feature workflow failed", failure_reason
    )
    return {**state, "success": False}
