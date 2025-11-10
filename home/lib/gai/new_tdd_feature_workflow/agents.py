"""Agent functions for new-tdd-feature workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import print_iteration_header
from shared_utils import (
    add_iteration_section_to_log,
    add_test_output_to_log,
    ensure_str_content,
    run_shell_command,
)

from .prompts import build_implementation_prompt
from .state import NewTddFeatureState


def run_implementation_agent(state: NewTddFeatureState) -> NewTddFeatureState:
    """Run the implementation agent to implement the feature based on failing tests."""
    current_iteration = state["current_iteration"]
    artifacts_dir = state["artifacts_dir"]
    workflow_tag = state["workflow_tag"]

    print_iteration_header(current_iteration, "Implementation")

    # Build the prompt
    prompt = build_implementation_prompt(state)

    # Create Gemini wrapper
    gemini = GeminiCommandWrapper(model_size="big")
    gemini.set_logging_context(
        agent_type="implementation",
        iteration=current_iteration,
        workflow_tag=workflow_tag,
        artifacts_dir=artifacts_dir,
    )

    try:
        # Run the agent
        messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
        response = gemini.invoke(messages)
        response_str = ensure_str_content(response.content)

        # Add iteration to workflow log
        add_iteration_section_to_log(
            artifacts_dir,
            current_iteration,
            "Implementation",
            prompt,
            response_str,
        )

        # Add to message history
        state_messages = state.get("messages", [])
        state_messages.append(HumanMessage(content=prompt))
        state_messages.append(AIMessage(content=response_str))

        return {
            **state,
            "messages": state_messages,
        }

    except Exception as e:
        print(f"❌ Error running implementation agent: {e}")
        return {
            **state,
            "failure_reason": f"Implementation agent failed: {e}",
        }


def run_test(state: NewTddFeatureState) -> NewTddFeatureState:
    """Run tests to check if implementation is successful."""
    current_iteration = state["current_iteration"]
    artifacts_dir = state["artifacts_dir"]
    test_targets = state["test_targets"]

    print("\n🧪 Running tests...")

    # Build test command using the provided test targets
    test_cmd = f"rabbit test -c opt --noshow_progress {test_targets}"
    print(f"Running test command: {test_cmd}")

    result = run_shell_command(test_cmd, capture_output=True)
    test_output = result.stdout + result.stderr
    test_command_used = test_cmd
    test_passed = result.returncode == 0

    if test_passed:
        print("✅ Tests passed!")
    else:
        print("❌ Tests failed")

    # Save test output to artifacts
    test_output_dest = os.path.join(
        artifacts_dir, f"test_output_iter_{current_iteration}.txt"
    )
    with open(test_output_dest, "w") as f:
        f.write(f"Test command: {test_command_used}\n")
        f.write(f"Return code: {result.returncode if test_command_used else 'N/A'}\n")
        f.write("\n")
        f.write(test_output)

    print(f"Test output saved to: {test_output_dest}")

    # Add test output to log
    add_test_output_to_log(
        artifacts_dir,
        current_iteration,
        test_output,
        test_passed,
    )

    # Increment iteration counter
    next_iteration = current_iteration + 1

    return {
        **state,
        "test_passed": test_passed,
        "current_iteration": next_iteration,
    }
