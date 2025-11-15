"""Workflow node functions for new-tdd-feature workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from shared_utils import (
    copy_design_docs_locally,
    create_artifacts_directory,
    finalize_workflow_log,
    generate_workflow_tag,
    initialize_gai_log,
    initialize_tests_log,
    initialize_workflow_log,
    run_shell_command,
)

from .state import NewTddFeatureState


def _parse_test_command_from_output_file(test_output_file: str) -> str | None:
    """
    Parse the test command from the test output file.

    The test output file should contain a line like:
    Test command: rabbit test -c opt --noshow_progress //path/to:target

    Returns the command without the "Test command: " prefix, or None if not found.
    """
    try:
        with open(test_output_file) as f:
            for line in f:
                if line.startswith("Test command:"):
                    # Extract command after "Test command: " prefix
                    command = line.replace("Test command:", "").strip()
                    return command
        return None
    except Exception as e:
        print(f"⚠️ Warning: Could not parse test command from {test_output_file}: {e}")
        return None


def initialize_workflow(state: NewTddFeatureState) -> NewTddFeatureState:
    """Initialize the new-tdd-feature workflow."""
    print("Initializing new-tdd-feature workflow...")
    print(f"Test output file: {state['test_output_file']}")

    # Check for local modifications before starting workflow
    print("Checking for local modifications...")
    result = run_shell_command("branch_local_changes", capture_output=True)
    if result.stdout.strip():
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Local modifications detected. Please commit or stash changes before running new-tdd-feature workflow. Local changes:\n{result.stdout}",
        }
    print("✅ No local modifications detected - safe to proceed")

    # Verify test output file exists
    if not os.path.exists(state["test_output_file"]):
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Test output file '{state['test_output_file']}' does not exist",
        }

    # Parse test command from test output file
    test_command = _parse_test_command_from_output_file(state["test_output_file"])
    if not test_command:
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Could not parse test command from test output file '{state['test_output_file']}'",
        }
    print(f"Parsed test command: {test_command}")

    # Generate unique workflow tag
    workflow_tag = generate_workflow_tag()
    print(f"Generated workflow tag: {workflow_tag}")

    # Create artifacts directory
    artifacts_dir = create_artifacts_directory()
    print(f"Created artifacts directory: {artifacts_dir}")

    # Initialize logs
    initialize_gai_log(artifacts_dir, "new-tdd-feature", workflow_tag)
    initialize_workflow_log(artifacts_dir, "new-tdd-feature", workflow_tag)
    initialize_tests_log(artifacts_dir, "new-tdd-feature", workflow_tag)

    # Create context files
    try:
        # Create cl_desc.txt from hdesc command
        cl_desc_dest = os.path.join(artifacts_dir, "cl_desc.txt")
        result = run_shell_command("hdesc", capture_output=True)
        with open(cl_desc_dest, "w") as f:
            f.write(result.stdout)
        print("✅ Created cl_desc.txt from hdesc command")

        # Create cl_changes.diff from branch_diff command
        cl_changes_dest = os.path.join(artifacts_dir, "cl_changes.diff")
        result = run_shell_command("branch_diff", capture_output=True)
        with open(cl_changes_dest, "w") as f:
            f.write(result.stdout)
        print("✅ Created cl_changes.diff from branch_diff command")

        # Copy design documents to local .gai/context/ directory
        context_file_directory = state.get("context_file_directory")
        local_designs_dir = copy_design_docs_locally([context_file_directory])

    except Exception as e:
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Error creating context files: {e}",
        }

    return {
        **state,
        "artifacts_dir": artifacts_dir,
        "workflow_tag": workflow_tag,
        "context_file_directory": local_designs_dir,  # Use local copy instead
        "test_command": test_command,
        "current_iteration": 1,
    }


def should_continue_workflow(
    state: NewTddFeatureState,
) -> str:
    """Determine if the workflow should continue, succeed, or fail."""
    # Check if tests passed
    if state.get("test_passed"):
        return "success"

    # Check if we've exceeded max iterations
    current_iteration = state.get("current_iteration", 0)
    max_iterations = state.get("max_iterations", 10)

    if current_iteration >= max_iterations:
        return "failure"

    # Check if there's a failure reason
    if state.get("failure_reason"):
        return "failure"

    # Continue to next iteration
    return "continue"


def handle_success(state: NewTddFeatureState) -> NewTddFeatureState:
    """Handle successful workflow completion."""
    artifacts_dir = state["artifacts_dir"]
    workflow_tag = state["workflow_tag"]

    print("✅ new-tdd-feature workflow completed successfully!")
    print(f"Artifacts saved to: {artifacts_dir}")

    # Finalize workflow log
    finalize_workflow_log(artifacts_dir, "new-tdd-feature", workflow_tag, success=True)

    return state


def handle_failure(state: NewTddFeatureState) -> NewTddFeatureState:
    """Handle workflow failure."""
    artifacts_dir = state.get("artifacts_dir", "")
    workflow_tag = state.get("workflow_tag", "")
    failure_reason = state.get("failure_reason", "Unknown error")

    print(f"❌ new-tdd-feature workflow failed: {failure_reason}")

    if artifacts_dir:
        print(f"Artifacts saved to: {artifacts_dir}")
        # Finalize workflow log
        finalize_workflow_log(
            artifacts_dir, "new-tdd-feature", workflow_tag, success=False
        )

    return state
