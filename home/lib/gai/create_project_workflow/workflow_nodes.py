"""Workflow nodes for the create-project workflow."""

import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from shared_utils import (
    copy_design_docs_locally,
    create_artifacts_directory,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
    run_bam_command,
    run_shell_command,
)

from .state import CreateProjectState


def initialize_create_project_workflow(
    state: CreateProjectState,
) -> CreateProjectState:
    """Initialize the create-project workflow by creating artifacts and running clsurf."""
    print("Initializing create-project workflow...")
    print(f"Critique query: {state['clquery']}")
    print(f"Design docs directory: {state['design_docs_dir']}")

    # Validate filename does not end with .md
    filename = state["filename"]
    if filename.endswith(".md"):
        return {
            **state,
            "success": False,
            "failure_reason": f"Filename must not include .md extension. Got: '{filename}'. Use just the basename (e.g., 'my-project' instead of 'my-project.md')",
        }

    # Verify design docs directory exists
    if not os.path.isdir(state["design_docs_dir"]):
        return {
            **state,
            "success": False,
            "failure_reason": f"Design docs directory '{state['design_docs_dir']}' does not exist or is not a directory",
        }

    # Find markdown files in design docs directory
    design_docs_dir = Path(state["design_docs_dir"])
    md_files = list(design_docs_dir.glob("*.md"))

    if not md_files:
        return {
            **state,
            "success": False,
            "failure_reason": f"No markdown files found in design docs directory '{state['design_docs_dir']}'",
        }

    print(f"Found {len(md_files)} markdown file(s) in design docs directory:")
    for md_file in md_files:
        print(f"  - {md_file}")

    # Generate unique workflow tag
    workflow_tag = generate_workflow_tag()
    print(f"Generated workflow tag: {workflow_tag}")

    # Create artifacts directory
    artifacts_dir = create_artifacts_directory()
    print(f"Created artifacts directory: {artifacts_dir}")

    # Initialize the gai.md log
    initialize_gai_log(artifacts_dir, "create-project", workflow_tag)

    # Copy design documents to local .gai/designs/ directory
    design_docs_dir_str = state["design_docs_dir"]
    local_designs_dir = copy_design_docs_locally([design_docs_dir_str])

    if not local_designs_dir:
        return {
            **state,
            "success": False,
            "failure_reason": "No design documents were copied to local directory",
        }

    # Create ~/.gai/projects directory if it doesn't exist
    projects_dir = Path.home() / ".gai" / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    print(f"Ensured projects directory exists: {projects_dir}")

    # Use the filename provided by the user (already validated to not end with .md)
    # Add .md extension for the actual file
    project_name = state["filename"]
    projects_file = str(projects_dir / f"{project_name}.md")
    print(f"Project file will be written to: {projects_file}")
    print(f"Project NAME: {project_name}")

    # Run clsurf command
    print(f"Running clsurf command with query: {state['clquery']}")
    clsurf_output_file = os.path.join(artifacts_dir, "clsurf_output.txt")
    clsurf_cmd = f"clsurf 'a:me -tag:archive {state['clquery']}'"

    try:
        result = run_shell_command(clsurf_cmd, capture_output=True)
        with open(clsurf_output_file, "w") as f:
            f.write(f"# Command: {clsurf_cmd}\n")
            f.write(f"# Return code: {result.returncode}\n\n")
            f.write(result.stdout)
            if result.stderr:
                f.write(f"\n# STDERR:\n{result.stderr}")
        print(f"Created clsurf output file: {clsurf_output_file}")
    except Exception as e:
        print(f"⚠️ Warning: Failed to run clsurf command: {e}")
        # Create an empty file to avoid issues later
        with open(clsurf_output_file, "w") as f:
            f.write(f"# Command: {clsurf_cmd}\n")
            f.write(f"# Error running clsurf: {str(e)}\n")

    return {
        **state,
        "artifacts_dir": artifacts_dir,
        "workflow_tag": workflow_tag,
        "clsurf_output_file": clsurf_output_file,
        "projects_file": projects_file,
        "project_name": project_name,
        "design_docs_dir": local_designs_dir,  # Use local copy instead
        "success": False,  # Will be set to True after agent completes
        "failure_reason": None,
        "messages": [],
    }


def handle_success(state: CreateProjectState) -> CreateProjectState:
    """Handle successful project plan generation."""
    print(
        f"""
🎉 SUCCESS! Project plan has been generated!

Projects file: {state["projects_file"]}
Artifacts saved in: {state["artifacts_dir"]}
"""
    )

    # Finalize the gai.md log
    artifacts_dir = state.get("artifacts_dir", "")
    workflow_tag = state.get("workflow_tag", "UNKNOWN")
    if artifacts_dir:
        finalize_gai_log(artifacts_dir, "create-project", workflow_tag, True)

    run_bam_command("Create-Project Workflow Complete!")
    return state


def handle_failure(state: CreateProjectState) -> CreateProjectState:
    """Handle workflow failure."""
    reason = state.get("failure_reason", "Unknown error")

    print(
        f"""
❌ FAILURE! Unable to generate project plan.

Reason: {reason}
Artifacts saved in: {state["artifacts_dir"]}
"""
    )

    # Finalize the gai.md log
    artifacts_dir = state.get("artifacts_dir", "")
    workflow_tag = state.get("workflow_tag", "UNKNOWN")
    if artifacts_dir:
        finalize_gai_log(artifacts_dir, "create-project", workflow_tag, False)

    run_bam_command("Create-Project Workflow Failed")
    return state
