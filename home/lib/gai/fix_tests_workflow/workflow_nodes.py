import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from shared_utils import (
    add_test_output_to_log,
    create_artifacts_directory,
    generate_workflow_tag,
    run_bam_command,
    run_shell_command,
    run_shell_command_with_input,
    initialize_gai_log,
    initialize_workflow_log,
    initialize_tests_log,
    finalize_workflow_log,
)

from .state import FixTestsState


def backup_and_update_artifacts_after_test_failure(
    state: FixTestsState,
) -> FixTestsState:
    """Update CL changes diff after test failure - most artifacts are now handled in log.md."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    print(f"Updating artifacts after test failure (iteration {iteration})...")

    try:
        # Re-create cl_changes.diff with current branch diff to capture any code changes
        cl_changes_dest = os.path.join(artifacts_dir, "cl_changes.diff")
        result = run_shell_command("branch_diff")
        with open(cl_changes_dest, "w") as f:
            f.write(result.stdout)
        print("✅ Updated cl_changes.diff with current branch state")

    except Exception as e:
        print(f"⚠️ Warning: Error during artifact update: {e}")

    return state


def initialize_fix_tests_workflow(state: FixTestsState) -> FixTestsState:
    """Initialize the fix-tests workflow by creating artifacts and copying files."""
    print("Initializing fix-tests workflow...")
    print(f"Test command: {state['test_cmd']}")
    print(f"Test output file: {state['test_output_file']}")

    # Check for local modifications before starting workflow
    print("Checking for local modifications...")
    result = run_shell_command("branch_local_changes", capture_output=True)
    if result.stdout.strip():
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Local modifications detected. Please commit or stash changes before running fix-tests workflow. Local changes:\n{result.stdout}",
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

    # Initialize the gai.md log with the artifacts directory and workflow tag
    initialize_gai_log(artifacts_dir, "fix-tests", workflow_tag)

    # Initialize the workflow log.md file
    initialize_workflow_log(artifacts_dir, "fix-tests", workflow_tag)

    # Initialize the tests.md file
    initialize_tests_log(artifacts_dir, "fix-tests", workflow_tag)

    # Create initial artifacts
    try:
        # Read and process the initial test output file (for log.md)
        initial_test_output = None
        try:
            # Read the original test output file
            with open(state["test_output_file"], "r") as f:
                original_output = f.read()

            # Pipe through trim_test_output
            trim_result = run_shell_command_with_input(
                "trim_test_output", original_output, capture_output=True
            )
            if trim_result.returncode == 0:
                initial_test_output = trim_result.stdout
            else:
                # If trim_test_output fails, use original output
                initial_test_output = original_output
                print(
                    "Warning: trim_test_output command failed during initialization, using original output"
                )

        except Exception as e:
            return {
                **state,
                "test_passed": False,
                "failure_reason": f"Failed to process test output file: {str(e)}",
            }

        # Create cl_desc.txt using hdesc
        cl_desc_artifact = os.path.join(artifacts_dir, "cl_desc.txt")
        result = run_shell_command("hdesc")
        with open(cl_desc_artifact, "w") as f:
            f.write(result.stdout)

        # Create cl_changes.diff using branch_diff
        cl_changes_artifact = os.path.join(artifacts_dir, "cl_changes.diff")
        result = run_shell_command("branch_diff")
        with open(cl_changes_artifact, "w") as f:
            f.write(result.stdout)

        # Note: User instructions file (if provided) is referenced directly at its original path
        # No copying or versioning is performed - the file path remains unchanged

        # Run clsurf command if clquery is provided
        clsurf_output_file = None
        if state.get("clquery"):
            clquery = state["clquery"]
            print(f"Running clsurf command with query: {clquery}")

            clsurf_output_file = os.path.join(artifacts_dir, "clsurf_output.txt")
            clsurf_cmd = f"clsurf 'a:me is:submitted {clquery}'"

            try:
                result = run_shell_command(clsurf_cmd, capture_output=True)
                with open(clsurf_output_file, "w") as f:
                    f.write(f"# Command: {clsurf_cmd}\n")
                    f.write(f"# Return code: {result.returncode}\n\n")
                    f.write(result.stdout)
                    if result.stderr:
                        f.write(f"\n# STDERR:\n{result.stderr}")
                print(f"  - {clsurf_output_file} (clsurf output)")
            except Exception as e:
                print(f"⚠️ Warning: Failed to run clsurf command: {e}")
                # Create an empty file to avoid issues later
                with open(clsurf_output_file, "w") as f:
                    f.write(f"# Command: {clsurf_cmd}\n")
                    f.write(f"# Error running clsurf: {str(e)}\n")

        print("Created initial artifacts:")
        print(f"  - {cl_desc_artifact}")
        print(f"  - {cl_changes_artifact}")
        if clsurf_output_file:
            print(f"  - {clsurf_output_file}")

        # Add initial test output to log.md so first planner agent can access it
        add_test_output_to_log(
            artifacts_dir=artifacts_dir,
            iteration=1,
            test_output=initial_test_output,
            test_output_is_meaningful=True,
        )

        return {
            **state,
            "artifacts_dir": artifacts_dir,
            "workflow_tag": workflow_tag,
            "clsurf_output_file": clsurf_output_file,
            "initial_test_output": initial_test_output,  # Store for first iteration log entry
            "commit_iteration": 1,
            "current_iteration": 1,
            "max_iterations": 10,  # Default maximum of 10 iterations
            "test_passed": False,
            "structured_modifications_received": False,
            "research_updated": False,
            "context_agent_retries": 0,
            "max_context_retries": 3,
            "verification_retries": 0,
            "max_verification_retries": 5,
            "verification_passed": False,
            "needs_editor_retry": False,
            "first_verification_success": False,
            "messages": [],
            "matched_iteration": None,
        }

    except Exception as e:
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Error during initialization: {str(e)}",
        }


def should_continue_verification(state: FixTestsState) -> str:
    """Determine the next step after verification."""
    if state.get("verification_passed", False):
        # Reset verification state for next iteration
        state["verification_retries"] = 0
        state["verification_passed"] = False
        return "verification_passed"
    elif state.get("needs_planner_retry", False):
        # Planner needs to retry - reset flags and go back to planner
        state["needs_planner_retry"] = False
        state["verification_retries"] = 0  # Reset verification retries since this is a planner issue
        print("🔄 Verification identified planner issue - retrying planner agent")
        return "retry_planner"
    elif state.get("needs_editor_retry", False):
        # Check if we've exceeded max verification retries
        if state["verification_retries"] >= state["max_verification_retries"]:
            print(
                f"⚠️ Maximum verification retries ({state['max_verification_retries']}) reached - workflow failed"
            )
            state["failure_reason"] = (
                f"Maximum verification retries ({state['max_verification_retries']}) reached"
            )
            return "failure"
        else:
            # Increment verification retries and retry editor
            state["verification_retries"] += 1
            state["needs_editor_retry"] = False
            print(
                f"🔄 Retrying editor agent (verification retry {state['verification_retries']}/{state['max_verification_retries']})"
            )
            return "retry_editor"
    else:
        # Shouldn't reach here, but default to proceeding
        return "verification_passed"


def should_continue_workflow(state: FixTestsState) -> str:
    """Determine the next step in the workflow."""
    if state["test_passed"]:
        return "success"
    elif state.get("failure_reason"):
        return "failure"
    elif state["current_iteration"] > state["max_iterations"]:
        # Maximum iterations reached - fail the workflow
        state["failure_reason"] = (
            f"Maximum iterations ({state['max_iterations']}) reached."
        )
        return "failure"
    elif state["context_agent_retries"] > 0:
        return "retry_context_agent"
    else:
        return "continue"


def handle_success(state: FixTestsState) -> FixTestsState:
    """Handle successful test fix."""
    print(
        f"""
🎉 SUCCESS! Test has been fixed in iteration {state["current_iteration"]}!

Test command: {state["test_cmd"]}
Artifacts saved in: {state["artifacts_dir"]}
"""
    )

    # Finalize the workflow log
    artifacts_dir = state.get("artifacts_dir", "")
    workflow_tag = state.get("workflow_tag", "UNKNOWN")
    if artifacts_dir:
        finalize_workflow_log(artifacts_dir, "fix-tests", workflow_tag, True)

    run_bam_command("Fix-Tests Workflow Complete!")
    return state


def handle_failure(state: FixTestsState) -> FixTestsState:
    """Handle workflow failure."""
    reason = state.get("failure_reason", "Unknown error")

    # Only run unamend if it's safe to do so (we've had at least one successful amend)
    if state.get("safe_to_unamend", False):
        print(
            "🔄 Safe to run unamend (successful amend occurred) - reverting commits..."
        )
        try:
            result = run_shell_command("hg unamend", capture_output=True)
            if result.returncode == 0:
                print("✅ Successfully reverted commits with unamend")
            else:
                print(f"⚠️ Warning: unamend failed: {result.stderr}")
        except Exception as e:
            print(f"⚠️ Warning: Error running unamend: {e}")
    elif state.get("first_verification_success", False):
        print(
            "⚠️ Cannot safely run unamend - no successful amend recorded or last amend failed"
        )

    print(
        f"""
❌ FAILURE! Unable to fix test.

Reason: {reason}
Test command: {state["test_cmd"]}
Artifacts saved in: {state["artifacts_dir"]}
"""
    )

    # Finalize the workflow log
    artifacts_dir = state.get("artifacts_dir", "")
    workflow_tag = state.get("workflow_tag", "UNKNOWN")
    if artifacts_dir:
        finalize_workflow_log(artifacts_dir, "fix-tests", workflow_tag, False)

    run_bam_command("Fix-Tests Workflow Failed")
    return state
