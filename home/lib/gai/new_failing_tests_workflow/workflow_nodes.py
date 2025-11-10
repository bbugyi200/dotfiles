"""Workflow nodes for the new-failing-tests workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rich_utils import print_status
from shared_utils import (
    copy_design_docs_locally,
    create_artifacts_directory,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
    run_bam_command,
    run_shell_command,
)

from .state import NewFailingTestState


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


def _write_test_coder_to_log(log_file: str, test_coder_response: str) -> None:
    """Write test coder agent output to log.md file."""
    with open(log_file, "a") as f:
        f.write("# Test Coder\n\n")
        f.write(f"{test_coder_response}\n\n")


def initialize_new_failing_test_workflow(
    state: NewFailingTestState,
) -> NewFailingTestState:
    """Initialize the new-failing-tests workflow."""
    print_status("Initializing new-failing-tests workflow...", "info")

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
    print_status(f"Status: {cl_status}", "info")

    # Validate status is "Unstarted (TDD)"
    if cl_status != "Unstarted (TDD)":
        return {
            **state,
            "success": False,
            "failure_reason": f"ChangeSpec status must be 'Unstarted (TDD)', got '{cl_status}'",
        }

    # Generate workflow tag
    workflow_tag = generate_workflow_tag()
    print_status(f"Generated workflow tag: {workflow_tag}", "success")

    # Create artifacts directory
    artifacts_dir = create_artifacts_directory()
    print_status(f"Created artifacts directory: {artifacts_dir}", "success")

    # Initialize gai.md log
    initialize_gai_log(artifacts_dir, "new-failing-tests", workflow_tag)

    # Copy design documents to local .gai/context/ directory
    context_file_directory = state.get("context_file_directory")
    local_designs_dir = copy_design_docs_locally([context_file_directory])

    # Create log.md file for research and test coder output
    log_file = os.path.join(artifacts_dir, "log.md")
    with open(log_file, "w") as f:
        f.write(f"# Create-Test-CL Workflow Log ({workflow_tag})\n\n")
        f.write(f"**CL Name:** {cl_name}\n\n")
        f.write(f"**CL Description:**\n```\n{cl_description}\n```\n\n")
        f.write("---\n\n")

    print_status(f"Created log file: {log_file}", "success")

    # Write CL description to separate file for '@' reference
    cl_description_file = os.path.join(artifacts_dir, "cl_desc.txt")
    with open(cl_description_file, "w") as f:
        f.write(cl_description)

    print_status(f"Created CL description file: {cl_description_file}", "success")

    # Run clsurf command to get prior work
    project_name = state["project_name"]
    clsurf_output_file = os.path.join(artifacts_dir, "clsurf_output.txt")
    clsurf_cmd = f"clsurf 'a:me -tag:archive d:{project_name}'"

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
        "context_file_directory": local_designs_dir,  # Use local copy instead
        "log_file": log_file,
        "cl_description_file": cl_description_file,
        "success": False,
        "failure_reason": None,
        "messages": [],
        "research_results": None,
        "test_coder_response": None,
        "test_coder_success": False,
        "tests_failed_as_expected": False,
    }


def write_test_coder_to_log(state: NewFailingTestState) -> NewFailingTestState:
    """Write test coder agent output to log.md file."""
    print_status("Writing test coder output to log.md...", "progress")

    test_coder_response = state.get("test_coder_response")
    if not test_coder_response:
        print_status("Warning: No test coder response to write", "warning")
        return state

    log_file = state["log_file"]
    _write_test_coder_to_log(log_file, test_coder_response)

    print_status(f"Test coder output written to {log_file}", "success")
    return state


def verify_tests_fail(state: NewFailingTestState) -> NewFailingTestState:
    """Verify that the tests fail as expected (since feature is not implemented)."""
    if not state["test_coder_success"]:
        print_status(
            "Test coder did not succeed, skipping test verification", "warning"
        )
        return {**state, "tests_failed_as_expected": False}

    print_status("Verifying that tests fail as expected...", "progress")

    # TODO: Implement test verification logic
    # For now, we'll assume tests failed if the test coder succeeded
    # In a real implementation, we would run the tests and verify they fail

    print_status(
        "Test verification not yet implemented - assuming tests fail as expected",
        "warning",
    )

    # NOTE: CL creation has been moved to work-project workflow
    # This workflow now only adds the failing tests
    return {
        **state,
        "tests_failed_as_expected": True,
        "success": True,
    }


def handle_success(state: NewFailingTestState) -> NewFailingTestState:
    """Handle successful test CL creation."""
    success_message = f"""Test CL has been created successfully!

CL Name: {state["cl_name"]}
Project: {state["project_name"]}
Artifacts saved in: {state["artifacts_dir"]}
"""

    print_status("=" * 60, "info")
    print_status("SUCCESS! Test CL created!", "success")
    print_status("=" * 60, "info")
    print(success_message)

    # Finalize gai.md log
    artifacts_dir = state.get("artifacts_dir", "")
    workflow_tag = state.get("workflow_tag", "UNKNOWN")
    if artifacts_dir:
        finalize_gai_log(artifacts_dir, "new-failing-tests", workflow_tag, True)

    run_bam_command("Create-Test-CL Workflow Complete!")
    return state


def handle_failure(state: NewFailingTestState) -> NewFailingTestState:
    """Handle workflow failure."""
    reason = state.get("failure_reason", "Unknown error")

    failure_message = f"""Unable to create test CL.

Reason: {reason}
Artifacts saved in: {state.get("artifacts_dir", "N/A")}
"""

    print_status("=" * 60, "info")
    print_status("FAILURE! Unable to create test CL.", "error")
    print_status("=" * 60, "info")
    print(failure_message)

    # Finalize gai.md log
    artifacts_dir = state.get("artifacts_dir", "")
    workflow_tag = state.get("workflow_tag", "UNKNOWN")
    if artifacts_dir:
        finalize_gai_log(artifacts_dir, "new-failing-tests", workflow_tag, False)

    run_bam_command("Create-Test-CL Workflow Failed")
    return state
