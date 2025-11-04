"""Workflow nodes for the create-cl workflow."""

import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rich_utils import print_status
from shared_utils import (
    create_artifacts_directory,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
    run_bam_command,
    run_shell_command,
)

from .state import CreateCLState


def _parse_changespec(changespec_text: str) -> dict[str, str | None]:
    """
    Parse a ChangeSpec from text format.

    Returns a dict with keys: name, description, parent, cl, status
    Raises ValueError if parsing fails.
    """
    lines = changespec_text.strip().split("\n")

    # Extract fields using regex
    name_match = None
    description_lines: list[str] = []
    parent_match = None
    cl_match = None
    status_match = None

    in_description = False

    for line in lines:
        # Check for NAME field
        if line.startswith("NAME: "):
            name_match = line[6:].strip()
            in_description = False

        # Check for DESCRIPTION field
        elif line.startswith("DESCRIPTION:"):
            in_description = True
            description_lines = []

        # Check for PARENT field
        elif line.startswith("PARENT: "):
            parent_match = line[8:].strip()
            in_description = False

        # Check for CL field
        elif line.startswith("CL: "):
            cl_match = line[4:].strip()
            in_description = False

        # Check for STATUS field
        elif line.startswith("STATUS: "):
            status_match = line[8:].strip()
            in_description = False

        # If we're in description, collect the line (must be 2-space indented)
        elif in_description:
            if line.startswith("  "):
                description_lines.append(line[2:])  # Remove 2-space indent
            elif line.strip():  # Non-empty line without indent ends description
                in_description = False

    # Validate required fields
    if not name_match:
        raise ValueError("ChangeSpec missing NAME field")
    if not description_lines:
        raise ValueError("ChangeSpec missing DESCRIPTION field")
    if parent_match is None:
        raise ValueError("ChangeSpec missing PARENT field")
    if cl_match is None:
        raise ValueError("ChangeSpec missing CL field")
    if not status_match:
        raise ValueError("ChangeSpec missing STATUS field")

    # Join description lines
    description = "\n".join(description_lines).strip()

    return {
        "name": name_match,
        "description": description,
        "parent": parent_match if parent_match != "None" else None,
        "cl": cl_match,
        "status": status_match,
    }


def _write_research_to_log(log_file: str, research_results: dict) -> None:
    """Write research findings to log.md file."""
    with open(log_file, "a") as f:
        f.write("# Researchers\n\n")

        for focus, result in research_results.items():
            f.write(f"## {result['title']}\n\n")
            f.write(f"{result['content']}\n\n")
            f.write("---\n\n")


def _write_coder_to_log(log_file: str, coder_response: str) -> None:
    """Write coder agent output to log.md file."""
    with open(log_file, "a") as f:
        f.write("# Coder\n\n")
        f.write(f"{coder_response}\n\n")


def initialize_create_cl_workflow(state: CreateCLState) -> CreateCLState:
    """Initialize the create-cl workflow."""
    print_status("Initializing create-cl workflow...", "info")

    # Parse ChangeSpec from input
    try:
        changespec = _parse_changespec(state["changespec_text"])
    except ValueError as e:
        return {
            **state,
            "success": False,
            "failure_reason": f"Failed to parse ChangeSpec: {e}",
        }

    cl_name = changespec["name"]
    cl_description = changespec["description"]
    cl_parent = changespec["parent"]
    cl_status = changespec["status"]

    # Ensure required fields are not None (they are guaranteed by validation in _parse_changespec)
    assert cl_name is not None, "cl_name should not be None after parsing"
    assert cl_description is not None, "cl_description should not be None after parsing"
    assert cl_status is not None, "cl_status should not be None after parsing"

    print_status(f"Parsed ChangeSpec: {cl_name}", "success")
    print_status(f"Status: {cl_status}", "info")

    # Validate status is "Not Started"
    if cl_status != "Not Started":
        return {
            **state,
            "success": False,
            "failure_reason": f"ChangeSpec status must be 'Not Started', got '{cl_status}'",
        }

    # Validate design docs directory
    design_docs_dir = state["design_docs_dir"]
    if not os.path.isdir(design_docs_dir):
        return {
            **state,
            "success": False,
            "failure_reason": f"Design docs directory '{design_docs_dir}' does not exist",
        }

    # Find markdown files in design docs directory
    design_docs_dir_path = Path(design_docs_dir)
    md_files = list(design_docs_dir_path.glob("*.md"))

    if not md_files:
        return {
            **state,
            "success": False,
            "failure_reason": f"No markdown files found in design docs directory '{design_docs_dir}'",
        }

    print_status(
        f"Found {len(md_files)} design document(s) in {design_docs_dir}", "success"
    )

    # Generate workflow tag
    workflow_tag = generate_workflow_tag()
    print_status(f"Generated workflow tag: {workflow_tag}", "success")

    # Create artifacts directory
    artifacts_dir = create_artifacts_directory()
    print_status(f"Created artifacts directory: {artifacts_dir}", "success")

    # Initialize gai.md log
    initialize_gai_log(artifacts_dir, "create-cl", workflow_tag)

    # Create log.md file for research and coder output
    log_file = os.path.join(artifacts_dir, "log.md")
    with open(log_file, "w") as f:
        f.write(f"# Create-CL Workflow Log ({workflow_tag})\n\n")
        f.write(f"**CL Name:** {cl_name}\n\n")
        f.write(f"**CL Description:**\n```\n{cl_description}\n```\n\n")
        f.write("---\n\n")

    print_status(f"Created log file: {log_file}", "success")

    # Run clsurf command to get prior work
    project_name = state["project_name"]
    clsurf_output_file = os.path.join(artifacts_dir, "clsurf_output.txt")
    clsurf_cmd = f"clsurf 'a:me d:{project_name}'"

    print_status(f"Running clsurf command: {clsurf_cmd}", "progress")
    try:
        result = run_shell_command(clsurf_cmd, capture_output=True)
        with open(clsurf_output_file, "w") as f:
            f.write(f"# Command: {clsurf_cmd}\n")
            f.write(f"# Return code: {result.returncode}\n\n")
            f.write(result.stdout)
            if result.stderr:
                f.write(f"\n# STDERR:\n{result.stderr}")
        print_status(f"Created clsurf output file: {clsurf_output_file}", "success")
    except Exception as e:
        print_status(f"Warning: Failed to run clsurf command: {e}", "warning")
        # Create empty file
        with open(clsurf_output_file, "w") as f:
            f.write(f"# Command: {clsurf_cmd}\n")
            f.write(f"# Error running clsurf: {str(e)}\n")

    return {
        **state,
        "cl_name": cl_name,
        "cl_description": cl_description,
        "cl_parent": cl_parent,
        "cl_status": cl_status,
        "artifacts_dir": artifacts_dir,
        "workflow_tag": workflow_tag,
        "clsurf_output_file": clsurf_output_file,
        "log_file": log_file,
        "success": False,
        "failure_reason": None,
        "messages": [],
        "research_results": None,
        "coder_response": None,
        "coder_success": False,
    }


def write_research_to_log(state: CreateCLState) -> CreateCLState:
    """Write research findings to log.md file."""
    print_status("Writing research findings to log.md...", "progress")

    research_results = state.get("research_results")
    if not research_results:
        print_status("Warning: No research results to write", "warning")
        return state

    log_file = state["log_file"]
    _write_research_to_log(log_file, research_results)

    print_status(f"Research findings written to {log_file}", "success")
    return state


def write_coder_to_log(state: CreateCLState) -> CreateCLState:
    """Write coder agent output to log.md file."""
    print_status("Writing coder output to log.md...", "progress")

    coder_response = state.get("coder_response")
    if not coder_response:
        print_status("Warning: No coder response to write", "warning")
        return state

    log_file = state["log_file"]
    _write_coder_to_log(log_file, coder_response)

    print_status(f"Coder output written to {log_file}", "success")
    return state


def create_cl_commit(state: CreateCLState) -> CreateCLState:
    """Create the CL commit if coder succeeded."""
    if not state["coder_success"]:
        print_status("Coder did not succeed, skipping CL commit", "warning")
        return {**state, "success": False}

    print_status("Creating CL commit...", "progress")

    project_name = state["project_name"]
    cl_name = state["cl_name"]
    cl_description = state["cl_description"]

    # Create logfile with full CL description prepended with [PROJECT]
    logfile_path = os.path.join(state["artifacts_dir"], "cl_commit_message.txt")
    with open(logfile_path, "w") as f:
        f.write(f"[{project_name}] {cl_description}")

    print_status(f"Created commit message file: {logfile_path}", "success")

    # Run hg commit command
    commit_cmd = f"hg commit --logfile {logfile_path} --name {cl_name}"
    print_status(f"Running: {commit_cmd}", "progress")

    try:
        result = run_shell_command(commit_cmd, capture_output=True)
        if result.returncode == 0:
            print_status("CL commit created successfully", "success")

            # Upload the CL
            print_status("Uploading CL...", "progress")
            upload_cmd = "hg evolve --any; hg upload tree"
            upload_result = run_shell_command(upload_cmd, capture_output=True)
            if upload_result.returncode != 0:
                print_status(
                    f"Warning: CL upload failed: {upload_result.stderr}", "warning"
                )
                return {**state, "success": True}

            print_status("CL uploaded successfully", "success")

            # Get the CL number
            cl_number_cmd = "branch_number"
            cl_number_result = run_shell_command(cl_number_cmd, capture_output=True)
            if cl_number_result.returncode == 0:
                cl_number = cl_number_result.stdout.strip()
                print_status(f"CL number: {cl_number}", "success")
                # Print in a parseable format for work-project workflow
                print(f"##CL-ID:{cl_number}##")
                return {**state, "success": True, "cl_id": cl_number}
            else:
                print_status("Warning: Could not retrieve CL number", "warning")
                return {**state, "success": True}
        else:
            error_msg = f"hg commit failed: {result.stderr}"
            print_status(error_msg, "error")
            return {**state, "success": False, "failure_reason": error_msg}
    except Exception as e:
        error_msg = f"Error running hg commit: {e}"
        print_status(error_msg, "error")
        return {**state, "success": False, "failure_reason": error_msg}


def handle_success(state: CreateCLState) -> CreateCLState:
    """Handle successful CL creation."""
    success_message = f"""CL has been created successfully!

CL Name: {state["cl_name"]}
Project: {state["project_name"]}
Artifacts saved in: {state["artifacts_dir"]}
"""

    print_status("=" * 60, "info")
    print_status("SUCCESS! CL created!", "success")
    print_status("=" * 60, "info")
    print(success_message)

    # Finalize gai.md log
    artifacts_dir = state.get("artifacts_dir", "")
    workflow_tag = state.get("workflow_tag", "UNKNOWN")
    if artifacts_dir:
        finalize_gai_log(artifacts_dir, "create-cl", workflow_tag, True)

    run_bam_command("Create-CL Workflow Complete!")
    return state


def handle_failure(state: CreateCLState) -> CreateCLState:
    """Handle workflow failure."""
    reason = state.get("failure_reason", "Unknown error")

    failure_message = f"""Unable to create CL.

Reason: {reason}
Artifacts saved in: {state.get("artifacts_dir", "N/A")}
"""

    print_status("=" * 60, "info")
    print_status("FAILURE! Unable to create CL.", "error")
    print_status("=" * 60, "info")
    print(failure_message)

    # Finalize gai.md log
    artifacts_dir = state.get("artifacts_dir", "")
    workflow_tag = state.get("workflow_tag", "UNKNOWN")
    if artifacts_dir:
        finalize_gai_log(artifacts_dir, "create-cl", workflow_tag, False)

    run_bam_command("Create-CL Workflow Failed")
    return state
