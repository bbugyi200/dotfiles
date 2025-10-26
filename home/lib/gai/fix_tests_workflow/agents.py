import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import HumanMessage
from shared_utils import run_shell_command

from .prompts import build_context_prompt, build_editor_prompt
from .state import FixTestsState


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

    return {**state, "test_passed": test_passed}


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

    # Check if either lessons.md or research.md was actually updated
    lessons_path = os.path.join(state["artifacts_dir"], "lessons.md")
    research_path = os.path.join(state["artifacts_dir"], "research.md")

    lessons_updated = os.path.exists(lessons_path)
    research_updated = os.path.exists(research_path)
    files_updated = lessons_updated or research_updated

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

    # Automatically stash local changes to give the next editor agent a fresh start
    print("Stashing local changes for next editor agent...")
    stash_result = run_shell_command("stash_local_changes", capture_output=True)
    if stash_result.returncode == 0:
        print("✅ Local changes stashed successfully")
    else:
        print(f"⚠️ Warning: Failed to stash local changes: {stash_result.stderr}")

    return {
        **state,
        "lessons_exists": lessons_updated,
        "research_exists": research_updated,
        "context_agent_retries": 0,  # Reset retries on success
        "current_iteration": state["current_iteration"]
        + 1,  # Increment iteration for next cycle
        "messages": state["messages"] + messages + [response],
    }
