import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import HumanMessage
from shared_utils import run_shell_command

from .prompts import build_context_prompt, build_editor_prompt, build_judge_prompt
from .state import FixTestsState


def create_agent_changes_diff(artifacts_dir: str, iteration: int) -> None:
    """Create a diff file showing changes made by the current agent iteration."""
    try:
        # Get the current diff from the working directory
        diff_cmd = "hg diff"
        result = run_shell_command(diff_cmd, capture_output=True)

        if result.returncode == 0:
            diff_file_path = os.path.join(
                artifacts_dir, f"editor_iter_{iteration}_changes.diff"
            )
            with open(diff_file_path, "w") as f:
                f.write(result.stdout)
            print(f"✅ Created changes diff: {diff_file_path}")
        else:
            print(f"⚠️ Warning: Failed to create diff: {result.stderr}")

    except Exception as e:
        print(f"⚠️ Warning: Error creating agent changes diff: {e}")


def run_editor_agent(state: FixTestsState) -> FixTestsState:
    """Run the editor/fixer agent to attempt fixing the test."""
    iteration = state["current_iteration"]
    print(f"Running editor agent (iteration {iteration})...")

    # Build prompt for editor
    prompt = build_editor_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("Editor agent response received")

    # Save the agent's response with iteration-specific name (for context agent only)
    response_path = os.path.join(
        state["artifacts_dir"], f"editor_iter_{iteration}_response.txt"
    )
    with open(response_path, "w") as f:
        f.write(response.content)

    # Also save as agent_reply.md for current iteration processing by context agent
    agent_reply_path = os.path.join(state["artifacts_dir"], "agent_reply.md")
    with open(agent_reply_path, "w") as f:
        f.write(response.content)

    # Print the response
    print("\n" + "=" * 80)
    print(f"EDITOR AGENT RESPONSE (ITERATION {iteration}):")
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    # Create a diff of changes made by this agent for the judge to review
    create_agent_changes_diff(state["artifacts_dir"], iteration)

    return {**state, "messages": state["messages"] + messages + [response]}


def run_test(state: FixTestsState) -> FixTestsState:
    """Run the actual test command and check if it passes."""
    iteration = state["current_iteration"]
    test_cmd = state["test_cmd"]
    print(f"Running test command (iteration {iteration}): {test_cmd}")

    artifacts_dir = state["artifacts_dir"]

    # Run the actual test command
    print(f"Executing: {test_cmd}")
    result = run_shell_command(test_cmd, capture_output=True)

    # Check if test passed
    test_passed = result.returncode == 0

    if test_passed:
        print("✅ Test PASSED!")
    else:
        print("❌ Test failed")

    # Print test output
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"Test stderr: {result.stderr}")

    # Save iteration-specific full test output for context agent review
    test_output_content = f"Command: {test_cmd}\nReturn code: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\n"
    iter_test_output_path = os.path.join(
        artifacts_dir, f"editor_iter_{iteration}_test_output.txt"
    )
    with open(iter_test_output_path, "w") as f:
        f.write(test_output_content)

    # Delete requirements.md after editor has used it to ensure diversity for next iteration
    requirements_path = os.path.join(artifacts_dir, "requirements.md")
    if os.path.exists(requirements_path):
        try:
            os.remove(requirements_path)
            print("✅ Deleted requirements.md for next iteration diversity")
        except Exception as e:
            print(f"⚠️ Warning: Failed to delete requirements.md: {e}")

    return {**state, "test_passed": test_passed}


def apply_agent_changes(artifacts_dir: str, selected_agent: int, test_cmd: str) -> bool:
    """Apply the selected agent's changes to the codebase."""
    try:
        # Find the changes diff file for the selected agent
        changes_file = os.path.join(
            artifacts_dir, f"editor_iter_{selected_agent}_changes.diff"
        )

        if not os.path.exists(changes_file):
            print(f"Error: Changes file not found: {changes_file}")
            return False

        # Apply the patch
        apply_cmd = f"patch -p1 < '{changes_file}'"
        result = run_shell_command(apply_cmd, capture_output=True)

        if result.returncode != 0:
            print(f"Error applying patch: {result.stderr}")
            return False

        print(f"✅ Successfully applied changes from agent {selected_agent}")

        # Create a short description of the changes
        with open(changes_file, "r") as f:
            diff_content = f.read()

        # Extract file names from diff for description
        import re

        file_matches = re.findall(r"\+\+\+ b/(.+)", diff_content)
        if file_matches:
            files_changed = ", ".join(file_matches[:3])  # First 3 files
            if len(file_matches) > 3:
                files_changed += f" and {len(file_matches) - 3} more"
            desc = f"Applied agent {selected_agent} changes to {files_changed}"
        else:
            desc = f"Applied agent {selected_agent} changes"

        # Amend the commit
        amend_cmd = f'hg amend -n "@AI #fix-tests {desc}"'
        result = run_shell_command(amend_cmd, capture_output=True)

        if result.returncode != 0:
            print(f"Warning: Failed to amend commit: {result.stderr}")
            # Don't fail the whole operation for this
        else:
            print(f"✅ Amended commit with description: {desc}")

        return True

    except Exception as e:
        print(f"Error applying agent changes: {e}")
        return False


def get_new_test_output_file(artifacts_dir: str, selected_agent: int) -> str:
    """Get the test output file from the selected agent for workflow restart."""
    test_output_file = os.path.join(
        artifacts_dir, f"editor_iter_{selected_agent}_test_output.txt"
    )
    if os.path.exists(test_output_file):
        return test_output_file
    else:
        # Fallback to original test output
        return os.path.join(artifacts_dir, "test_output.txt")


def run_judge_agent(state: FixTestsState) -> FixTestsState:
    """Run the judge agent to select the best changes from all iterations."""
    artifacts_dir = state["artifacts_dir"]
    judge_iteration = state["current_judge_iteration"]
    print(f"Running judge agent (judge iteration {judge_iteration})...")

    # Build judge prompt
    prompt = build_judge_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("Judge agent response received")

    # Save the judge's response
    response_path = os.path.join(
        artifacts_dir, f"judge_iter_{judge_iteration}_response.txt"
    )
    with open(response_path, "w") as f:
        f.write(response.content)

    # Print the response
    print("\n" + "=" * 80)
    print(f"JUDGE AGENT RESPONSE (JUDGE ITERATION {judge_iteration}):")
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    # Parse the judge's selection (expecting format like "SELECTED AGENT: 3")
    selected_agent = None
    lines = response.content.split("\n")
    for line in lines:
        if line.startswith("SELECTED AGENT:"):
            try:
                selected_agent = int(line.split(":")[1].strip())
                break
            except (ValueError, IndexError):
                continue

    if selected_agent is None:
        return {
            **state,
            "test_passed": False,
            "failure_reason": "Judge agent failed to select an agent",
            "messages": state["messages"] + messages + [response],
        }

    print(f"Judge selected agent iteration {selected_agent}")

    # Apply the selected agent's changes
    success = apply_agent_changes(artifacts_dir, selected_agent, state["test_cmd"])

    if not success:
        return {
            **state,
            "test_passed": False,
            "failure_reason": f"Failed to apply changes from agent {selected_agent}",
            "messages": state["messages"] + messages + [response],
        }

    # Get new test output file for restart
    new_test_output_file = get_new_test_output_file(artifacts_dir, selected_agent)

    return {
        **state,
        "test_output_file": new_test_output_file,
        "current_iteration": 1,  # Reset for new workflow run
        "current_judge_iteration": judge_iteration + 1,
        "judge_applied_changes": state["judge_applied_changes"] + 1,
        "artifacts_dir": "",  # Will be reset by new workflow
        "requirements_exists": False,
        "research_exists": False,
        "context_agent_retries": 0,
        "messages": state["messages"] + messages + [response],
    }


def run_context_agent(state: FixTestsState) -> FixTestsState:
    """Run the context/research agent to update blackboard.md."""
    iteration = state["current_iteration"]
    print(f"Running context agent (iteration {iteration})...")

    # Build prompt for context agent
    prompt = build_context_prompt(state)

    # Send prompt to Gemini
    model = GeminiCommandWrapper()
    messages = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    print("Context agent response received")

    # Save the agent's response
    response_path = os.path.join(
        state["artifacts_dir"], f"context_response_iter_{iteration}.txt"
    )
    with open(response_path, "w") as f:
        f.write(response.content)

    # Print the response
    print("\n" + "=" * 80)
    print(f"CONTEXT AGENT RESPONSE (ITERATION {iteration}):")
    print("=" * 80)
    print(response.content)
    print("=" * 80 + "\n")

    # Check if agent responded with "NO UPDATES"
    if response.content.strip() == "NO UPDATES":
        print("Context agent indicated no updates - workflow will abort")
        return {
            **state,
            "test_passed": False,
            "failure_reason": "Context agent found no new insights to add",
            "messages": state["messages"] + messages + [response],
        }

    # Check if either requirements.md or research.md was actually updated
    requirements_path = os.path.join(state["artifacts_dir"], "requirements.md")
    research_path = os.path.join(state["artifacts_dir"], "research.md")

    requirements_updated = os.path.exists(requirements_path)
    research_updated = os.path.exists(research_path)
    files_updated = requirements_updated or research_updated

    if not files_updated:
        # Agent didn't say "NO UPDATES" but also didn't update either file
        retries = state["context_agent_retries"] + 1
        if retries >= state["max_context_retries"]:
            print(
                f"Context agent failed to update files after {retries} retries - workflow will abort"
            )
            return {
                **state,
                "test_passed": False,
                "failure_reason": f"Context agent failed to update files after {retries} retries",
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }
        else:
            print(
                f"Context agent didn't update any files, retrying ({retries}/{state['max_context_retries']})"
            )
            return {
                **state,
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }

    print("✅ Files updated successfully")

    # Store current requirements for diversity tracking
    if requirements_updated:
        current_iteration = state["current_iteration"]
        requirements_backup_path = os.path.join(
            state["artifacts_dir"], f"requirements_iter_{current_iteration}.md"
        )
        try:
            import shutil

            shutil.copy2(requirements_path, requirements_backup_path)
            print(f"✅ Stored requirements backup: {requirements_backup_path}")
            # Note: requirements.md is kept for next editor agent, will be deleted after use
        except Exception as e:
            print(f"⚠️ Warning: Failed to backup requirements: {e}")

    # Automatically stash local changes to give the next editor agent a fresh start
    print("Stashing local changes for next editor agent...")
    stash_result = run_shell_command("stash_local_changes", capture_output=True)
    if stash_result.returncode == 0:
        print("✅ Local changes stashed successfully")
    else:
        print(f"⚠️ Warning: Failed to stash local changes: {stash_result.stderr}")

    return {
        **state,
        "requirements_exists": requirements_updated,
        "research_exists": research_updated,
        "context_agent_retries": 0,  # Reset retries on success
        "current_iteration": state["current_iteration"]
        + 1,  # Increment iteration for next cycle
        "messages": state["messages"] + messages + [response],
    }
