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

        # Copy and split blackboard file if provided
        lessons_exists = False
        research_exists = False

        if state.get("blackboard_file") and os.path.exists(state["blackboard_file"]):
            # Read the blackboard file content
            with open(state["blackboard_file"], "r") as f:
                blackboard_content = f.read()

            # Split content into lessons and research
            lessons_content = ""
            research_content = ""

            # Parse sections from blackboard file
            lines = blackboard_content.split("\n")
            current_section = None
            current_content = []

            for line in lines:
                if line.startswith("# Questions and Answers"):
                    # Save previous section
                    if current_section == "lessons" and current_content:
                        lessons_content = "\n".join(current_content).strip()
                    # Start research section
                    current_section = "research"
                    current_content = [line]
                elif line.startswith("# Lessons Learned"):
                    # Save previous section
                    if current_section == "research" and current_content:
                        research_content = "\n".join(current_content).strip()
                    # Start lessons section (but don't include the header since we want H1s for each lesson)
                    current_section = "lessons"
                    current_content = []
                elif line.startswith("## ") and current_section == "lessons":
                    # Convert H2 lessons to H1
                    current_content.append("# " + line[3:])
                else:
                    current_content.append(line)

            # Save final section
            if current_section == "lessons" and current_content:
                lessons_content = "\n".join(current_content).strip()
            elif current_section == "research" and current_content:
                research_content = "\n".join(current_content).strip()

            # Create lessons.md if there's content
            if lessons_content:
                lessons_artifact = os.path.join(artifacts_dir, "lessons.md")
                with open(lessons_artifact, "w") as f:
                    f.write(lessons_content)
                lessons_exists = True
                print(
                    f"  - {lessons_artifact} (lessons from {state['blackboard_file']})"
                )

            # Create research.md if there's content
            if research_content:
                research_artifact = os.path.join(artifacts_dir, "research.md")
                with open(research_artifact, "w") as f:
                    f.write(research_content)
                research_exists = True
                print(
                    f"  - {research_artifact} (research from {state['blackboard_file']})"
                )

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
            "lessons_exists": lessons_exists,
            "research_exists": research_exists,
            "context_agent_retries": 0,
            "max_context_retries": 3,
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
        # Set failure reason when max iterations reached
        state["failure_reason"] = f"Maximum iterations ({state['max_iterations']}) reached without fixing the test"
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
