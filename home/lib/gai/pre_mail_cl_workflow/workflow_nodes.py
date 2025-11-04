"""Workflow nodes for the pre-mail-cl workflow."""

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
    safe_hg_amend,
)

from .state import PreMailCLState


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


def _write_feature_coder_to_log(log_file: str, feature_coder_response: str) -> None:
    """Write feature coder agent output to log.md file."""
    with open(log_file, "a") as f:
        f.write("# Feature Coder\n\n")
        f.write(f"{feature_coder_response}\n\n")


def initialize_pre_mail_cl_workflow(state: PreMailCLState) -> PreMailCLState:
    """Initialize the pre-mail-cl workflow."""
    print_status("Initializing pre-mail-cl workflow...", "info")

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

    # Ensure required fields are not None
    assert cl_name is not None, "cl_name should not be None after parsing"
    assert cl_description is not None, "cl_description should not be None after parsing"
    assert cl_status is not None, "cl_status should not be None after parsing"

    # Display the ChangeSpec in a nice panel
    from rich.panel import Panel
    from rich_utils import console

    changespec_display = f"""[bold]NAME:[/bold] {cl_name}

[bold]DESCRIPTION:[/bold]
{cl_description}

[bold]PARENT:[/bold] {cl_parent if cl_parent else "None"}
[bold]CL:[/bold] {state["cl_number"]}
[bold]STATUS:[/bold] {cl_status}"""

    console.print(
        Panel(
            changespec_display,
            title="📋 ChangeSpec",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    print_status(f"Parsed ChangeSpec: {cl_name}", "success")
    print_status(f"CL Number: {state['cl_number']}", "info")
    print_status(f"Status: {cl_status}", "info")

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

    # Read test output file
    test_output_file = state["test_output_file"]
    if not os.path.isfile(test_output_file):
        return {
            **state,
            "success": False,
            "failure_reason": f"Test output file '{test_output_file}' does not exist",
        }

    try:
        with open(test_output_file) as f:
            test_output_content = f.read()
    except Exception as e:
        return {
            **state,
            "success": False,
            "failure_reason": f"Failed to read test output file: {e}",
        }

    print_status(f"Read test output file: {test_output_file}", "success")

    # Generate workflow tag
    workflow_tag = generate_workflow_tag()
    print_status(f"Generated workflow tag: {workflow_tag}", "success")

    # Create artifacts directory
    artifacts_dir = create_artifacts_directory()
    print_status(f"Created artifacts directory: {artifacts_dir}", "success")

    # Initialize gai.md log
    initialize_gai_log(artifacts_dir, "pre-mail-cl", workflow_tag)

    # Create log.md file for research and feature coder output
    log_file = os.path.join(artifacts_dir, "log.md")
    with open(log_file, "w") as f:
        f.write(f"# Pre-Mail-CL Workflow Log ({workflow_tag})\n\n")
        f.write(f"**CL Name:** {cl_name}\n\n")
        f.write(f"**CL Number:** {state['cl_number']}\n\n")
        f.write(f"**CL Description:**\n```\n{cl_description}\n```\n\n")
        f.write(f"**Test Output:**\n```\n{test_output_content}\n```\n\n")
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
        "test_output_content": test_output_content,
        "artifacts_dir": artifacts_dir,
        "workflow_tag": workflow_tag,
        "clsurf_output_file": clsurf_output_file,
        "log_file": log_file,
        "success": False,
        "failure_reason": None,
        "messages": [],
        "research_results": None,
        "feature_coder_response": None,
        "feature_coder_success": False,
        "tests_passed": False,
    }


def write_research_to_log(state: PreMailCLState) -> PreMailCLState:
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


def write_feature_coder_to_log(state: PreMailCLState) -> PreMailCLState:
    """Write feature coder agent output to log.md file."""
    print_status("Writing feature coder output to log.md...", "progress")

    feature_coder_response = state.get("feature_coder_response")
    if not feature_coder_response:
        print_status("Warning: No feature coder response to write", "warning")
        return state

    log_file = state["log_file"]
    _write_feature_coder_to_log(log_file, feature_coder_response)

    print_status(f"Feature coder output written to {log_file}", "success")
    return state


def verify_tests_pass(state: PreMailCLState) -> PreMailCLState:
    """Verify that the tests pass after feature implementation."""
    if not state["feature_coder_success"]:
        print_status(
            "Feature coder did not succeed, skipping test verification", "warning"
        )
        return {**state, "tests_passed": False}

    print_status(
        "Verifying that tests pass after feature implementation...", "progress"
    )

    # TODO: Implement test verification logic
    # For now, we'll assume tests passed if the feature coder succeeded
    # In a real implementation, we would run the tests and verify they pass

    print_status(
        "Test verification not yet implemented - assuming tests pass if coder succeeded",
        "warning",
    )

    return {
        **state,
        "tests_passed": state["feature_coder_success"],
    }


def amend_cl(state: PreMailCLState) -> PreMailCLState:
    """Amend the CL if tests passed."""
    if not state["feature_coder_success"]:
        print_status("Feature coder did not succeed, skipping CL amend", "warning")
        return {**state, "success": False}

    if not state["tests_passed"]:
        print_status("Tests did not pass, skipping CL amend", "warning")
        return {**state, "success": False}

    print_status("Amending CL with feature implementation...", "progress")

    project_name = state["project_name"]
    cl_description = state["cl_description"]

    # Create commit message for amend
    commit_message = f"[{project_name}] {cl_description}"

    # Use safe_hg_amend to amend the CL
    success = safe_hg_amend(commit_message, use_unamend_first=False)

    if success:
        print_status("CL amended successfully", "success")

        # Upload the CL
        print_status("Uploading amended CL...", "progress")
        upload_cmd = "hg evolve --any; hg upload tree"
        upload_result = run_shell_command(upload_cmd, capture_output=True)
        if upload_result.returncode != 0:
            print_status(
                f"Warning: CL upload failed: {upload_result.stderr}", "warning"
            )
            return {**state, "success": True}

        print_status("Amended CL uploaded successfully", "success")
        return {**state, "success": True}
    else:
        error_msg = "Failed to amend CL"
        print_status(error_msg, "error")
        return {**state, "success": False, "failure_reason": error_msg}


def handle_success(state: PreMailCLState) -> PreMailCLState:
    """Handle successful feature implementation and CL amendment."""
    success_message = f"""Feature implemented and CL amended successfully!

CL Name: {state["cl_name"]}
CL Number: {state["cl_number"]}
Project: {state["project_name"]}
Artifacts saved in: {state["artifacts_dir"]}
"""

    print_status("=" * 60, "info")
    print_status("SUCCESS! Feature implemented and CL amended!", "success")
    print_status("=" * 60, "info")
    print(success_message)

    # Finalize gai.md log
    artifacts_dir = state.get("artifacts_dir", "")
    workflow_tag = state.get("workflow_tag", "UNKNOWN")
    if artifacts_dir:
        finalize_gai_log(artifacts_dir, "pre-mail-cl", workflow_tag, True)

    run_bam_command("Pre-Mail-CL Workflow Complete!")
    return state


def handle_failure(state: PreMailCLState) -> PreMailCLState:
    """Handle workflow failure."""
    reason = state.get("failure_reason", "Unknown error")

    failure_message = f"""Unable to implement feature and amend CL.

Reason: {reason}
Artifacts saved in: {state.get("artifacts_dir", "N/A")}
"""

    print_status("=" * 60, "info")
    print_status("FAILURE! Unable to implement feature.", "error")
    print_status("=" * 60, "info")
    print(failure_message)

    # Finalize gai.md log
    artifacts_dir = state.get("artifacts_dir", "")
    workflow_tag = state.get("workflow_tag", "UNKNOWN")
    if artifacts_dir:
        finalize_gai_log(artifacts_dir, "pre-mail-cl", workflow_tag, False)

    run_bam_command("Pre-Mail-CL Workflow Failed")
    return state
