"""Workflow node functions for new-tdd-feature workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from shared_utils import (
    create_artifacts_directory,
    finalize_workflow_log,
    generate_workflow_tag,
    initialize_gai_log,
    initialize_tests_log,
    initialize_workflow_log,
    run_shell_command,
)

from .state import NewTddFeatureState


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

        # Determine context_file_directory if not provided
        context_file_directory = state.get("context_file_directory")
        if not context_file_directory:
            # Get project name from workspace_name command
            result = run_shell_command("workspace_name", capture_output=True)
            if result.returncode == 0:
                project_name = result.stdout.strip()
                designs_dir = os.path.expanduser(f"~/.gai/designs/{project_name}")
                if os.path.isdir(designs_dir):
                    context_file_directory = designs_dir
                    print(
                        f"✅ Using default context directory: {context_file_directory}"
                    )
                else:
                    print(f"ℹ️ Default designs directory does not exist: {designs_dir}")
            else:
                print(
                    "⚠️ Warning: Could not determine project name from workspace_name command"
                )

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
        "context_file_directory": context_file_directory,
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
