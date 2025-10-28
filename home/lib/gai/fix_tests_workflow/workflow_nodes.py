import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from shared_utils import create_artifacts_directory, run_bam_command, run_shell_command

from .state import FixTestsState


def backup_and_update_artifacts_after_test_failure(
    state: FixTestsState,
) -> FixTestsState:
    """Backup original files on first test failure and update current artifacts with latest test results."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    # Files to backup and update
    test_output_src = os.path.join(
        artifacts_dir, f"editor_iter_{iteration}_test_output.txt"
    )
    test_output_dest = os.path.join(artifacts_dir, "test_output.txt")
    test_output_backup = os.path.join(artifacts_dir, "orig_test_output.txt")

    # Get the current CL changes diff
    cl_changes_dest = os.path.join(artifacts_dir, "cl_changes.diff")
    cl_changes_backup = os.path.join(artifacts_dir, "orig_cl_changes.diff")

    print(
        f"Backing up and updating artifacts after test failure (iteration {iteration})..."
    )

    try:
        # Backup original test_output.txt if this is the first test failure and backup doesn't exist
        if not os.path.exists(test_output_backup) and os.path.exists(test_output_dest):
            result = run_shell_command(
                f"cp '{test_output_dest}' '{test_output_backup}'"
            )
            if result.returncode == 0:
                print("✅ Backed up original test_output.txt to orig_test_output.txt")
            else:
                print(
                    f"⚠️ Warning: Failed to backup original test_output.txt: {result.stderr}"
                )

        # Update test_output.txt with latest test results
        if os.path.exists(test_output_src):
            result = run_shell_command(f"cp '{test_output_src}' '{test_output_dest}'")
            if result.returncode == 0:
                print(f"✅ Updated test_output.txt with iteration {iteration} results")
            else:
                print(f"⚠️ Warning: Failed to update test_output.txt: {result.stderr}")
        else:
            print(
                f"⚠️ Warning: Test output file for iteration {iteration} not found: {test_output_src}"
            )

        # Backup original cl_changes.diff if this is the first test failure and backup doesn't exist
        if not os.path.exists(cl_changes_backup) and os.path.exists(cl_changes_dest):
            result = run_shell_command(f"cp '{cl_changes_dest}' '{cl_changes_backup}'")
            if result.returncode == 0:
                print("✅ Backed up original cl_changes.diff to orig_cl_changes.diff")
            else:
                print(
                    f"⚠️ Warning: Failed to backup original cl_changes.diff: {result.stderr}"
                )

        # Re-create cl_changes.diff with current branch diff (same as initialization)
        result = run_shell_command("branch_diff")
        with open(cl_changes_dest, "w") as f:
            f.write(result.stdout)
        print("✅ Re-created cl_changes.diff with current branch state")

    except Exception as e:
        print(f"⚠️ Warning: Error during artifact backup/update: {e}")

    return state


def initialize_fix_tests_workflow(state: FixTestsState) -> FixTestsState:
    """Initialize the fix-tests workflow by creating artifacts and copying files."""
    print("Initializing fix-tests workflow...")
    print(f"Test command: {state['test_cmd']}")
    print(f"Test output file: {state['test_output_file']}")

    # Verify test output file exists
    if not os.path.exists(state["test_output_file"]):
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Test output file '{state['test_output_file']}' does not exist",
        }

    # Create artifacts directory
    artifacts_dir = create_artifacts_directory()
    print(f"Created artifacts directory: {artifacts_dir}")

    # Create initial artifacts
    try:
        # Copy test output file
        test_output_artifact = os.path.join(artifacts_dir, "test_output.txt")
        result = run_shell_command(
            f"cp '{state['test_output_file']}' '{test_output_artifact}'"
        )
        if result.returncode != 0:
            return {
                **state,
                "test_passed": False,
                "failure_reason": f"Failed to copy test output file: {result.stderr}",
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

        print("Created initial artifacts:")
        print(f"  - {test_output_artifact}")
        print(f"  - {cl_desc_artifact}")
        print(f"  - {cl_changes_artifact}")

        return {
            **state,
            "artifacts_dir": artifacts_dir,
            "current_iteration": 1,
            "max_iterations": 10,  # Default maximum of 10 iterations
            "test_passed": False,
            "todos_created": False,
            "research_updated": False,
            "context_agent_retries": 0,
            "max_context_retries": 3,
            "verification_retries": 0,
            "max_verification_retries": 3,
            "verification_passed": False,
            "needs_editor_retry": False,
            "first_verification_success": False,
            "messages": [],
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

    run_bam_command("Fix-Tests Workflow Complete!")
    return state


def handle_failure(state: FixTestsState) -> FixTestsState:
    """Handle workflow failure."""
    reason = state.get("failure_reason", "Unknown error")

    # If at least one verification succeeded but workflow failed, run unamend
    if state.get("first_verification_success", False):
        print(
            "🔄 At least one verification succeeded - running unamend to revert commits..."
        )
        try:
            result = run_shell_command("hg unamend", capture_output=True)
            if result.returncode == 0:
                print("✅ Successfully reverted commits with unamend")
            else:
                print(f"⚠️ Warning: unamend failed: {result.stderr}")
        except Exception as e:
            print(f"⚠️ Warning: Error running unamend: {e}")

    print(
        f"""
❌ FAILURE! Unable to fix test.

Reason: {reason}
Test command: {state["test_cmd"]}
Artifacts saved in: {state["artifacts_dir"]}
"""
    )

    run_bam_command("Fix-Tests Workflow Failed")
    return state
