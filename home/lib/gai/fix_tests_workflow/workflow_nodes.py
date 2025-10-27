import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from shared_utils import create_artifacts_directory, run_bam_command, run_shell_command

from .state import FixTestsState


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
            "current_judge_iteration": 1,
            "max_judges": 3,  # Default maximum of 3 judge iterations
            "test_passed": False,
            "todos_created": False,
            "research_updated": False,
            "context_agent_retries": 0,
            "max_context_retries": 3,
            "judge_applied_changes": 0,
            "messages": [],
        }

    except Exception as e:
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Error during initialization: {str(e)}",
        }


def should_continue_workflow(state: FixTestsState) -> str:
    """Determine the next step in the workflow."""
    if state["test_passed"]:
        return "success"
    elif state.get("failure_reason"):
        return "failure"
    elif state["current_iteration"] > state["max_iterations"]:
        # Check if we should run judge agent
        if state["current_judge_iteration"] <= state["max_judges"]:
            return "run_judge"
        else:
            # Maximum judge iterations reached
            state["failure_reason"] = (
                f"Maximum iterations ({state['max_iterations']}) and judge iterations ({state['max_judges']}) reached. Applied {state['judge_applied_changes']} judge changes."
            )
            return "failure"
    elif state["context_agent_retries"] > 0:
        return "retry_context_agent"
    else:
        return "continue"


def handle_judge_result(state: FixTestsState) -> str:
    """Handle the result after judge agent runs."""
    if state.get("failure_reason"):
        return "failure"
    else:
        # Restart the workflow with the judge's selected changes
        return "restart_workflow"


def restart_workflow_after_judge(state: FixTestsState) -> FixTestsState:
    """Restart the workflow with a new artifacts directory after judge applies changes."""
    print(
        f"Restarting workflow after judge iteration {state['current_judge_iteration'] - 1}..."
    )

    # Import here to avoid circular imports
    from .main import FixTestsWorkflow

    try:
        # Create a new workflow with the updated test output file
        new_workflow = FixTestsWorkflow(
            state["test_cmd"],
            state["test_output_file"],
            state["user_instructions_file"],
            state["max_iterations"],
            state["max_judges"],
            state["no_human_approval"],
            state["comment_out_lines"],
        )

        # Run the new workflow
        success = new_workflow.run()

        if success:
            return {
                **state,
                "test_passed": True,
            }
        else:
            # If the restarted workflow failed, continue with judge logic
            return {
                **state,
                "test_passed": False,
                # Don't set failure_reason here, let the main logic handle it
            }

    except Exception as e:
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Error restarting workflow after judge: {str(e)}",
        }


def handle_success(state: FixTestsState) -> FixTestsState:
    """Handle successful test fix."""
    strategy = (
        "COMMENT-OUT STRATEGY"
        if state.get("comment_out_lines", False)
        else "STANDARD FIX"
    )

    print(
        f"""
🎉 SUCCESS! Test has been fixed in iteration {state["current_iteration"]}!

Strategy used: {strategy}
Test command: {state["test_cmd"]}
Artifacts saved in: {state["artifacts_dir"]}
"""
    )

    run_bam_command(f"Fix-Tests Workflow Complete! ({strategy})")
    return state


def handle_failure(state: FixTestsState) -> FixTestsState:
    """Handle workflow failure."""
    reason = state.get("failure_reason", "Unknown error")
    strategy = (
        "COMMENT-OUT STRATEGY"
        if state.get("comment_out_lines", False)
        else "STANDARD FIX"
    )

    print(
        f"""
❌ FAILURE! Unable to fix test.

Strategy used: {strategy}
Reason: {reason}
Test command: {state["test_cmd"]}
Artifacts saved in: {state["artifacts_dir"]}
"""
    )

    run_bam_command(f"Fix-Tests Workflow Failed ({strategy})")
    return state
