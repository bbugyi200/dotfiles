"""Agent implementations for the new-failing-tests workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import print_status
from shared_utils import ensure_str_content

from .prompts import build_test_coder_prompt
from .state import NewFailingTestState


def run_test_coder_agent(state: NewFailingTestState) -> NewFailingTestState:
    """Run the test coder agent to add failing tests."""
    print_status("Running test coder agent to add failing tests...", "progress")

    # Build prompt for test coder
    prompt = build_test_coder_prompt(state)

    # Create Gemini wrapper with big model
    model = GeminiCommandWrapper(model_size="big")
    model.set_logging_context(
        agent_type="test_coder",
        iteration=1,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
        workflow="new-failing-tests",
    )

    # Send prompt
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)

    response_content = ensure_str_content(response.content)
    print_status("Test coder agent response received", "success")

    # Save test coder response to artifacts
    test_coder_response_path = os.path.join(
        state["artifacts_dir"], "test_coder_agent_response.txt"
    )
    with open(test_coder_response_path, "w") as f:
        f.write(response_content)
    print_status(f"Saved test coder response to: {test_coder_response_path}", "info")

    # Check if changes were made using hg diff and hg status
    import subprocess

    try:
        # Check for modified tracked files
        diff_result = subprocess.run(
            ["hg", "diff"],
            capture_output=True,
            text=True,
            check=False,
        )
        has_diff_changes = bool(diff_result.stdout.strip())

        # Check for untracked files (new files that haven't been added yet)
        status_result = subprocess.run(
            ["hg", "status", "-u"],  # -u shows only untracked files
            capture_output=True,
            text=True,
            check=False,
        )
        has_untracked_files = bool(status_result.stdout.strip())

        # Success if either we have diff changes OR new untracked files
        has_changes = has_diff_changes or has_untracked_files
        test_coder_success = has_changes

        if has_changes:
            if has_diff_changes and has_untracked_files:
                print_status(
                    "Test coder agent made changes (modified existing files and added new files)",
                    "success",
                )
            elif has_diff_changes:
                print_status(
                    "Test coder agent made changes (modified existing files)", "success"
                )
            else:
                print_status(
                    "Test coder agent made changes (added new files)", "success"
                )
        else:
            print_status(
                "WARNING: Test coder agent did not make any changes (no diff and no new files)",
                "warning",
            )
    except Exception as e:
        print_status(f"Error checking for changes: {e}", "error")
        test_coder_success = False

    # Test targets are already in state (passed in from ChangeSpec)
    test_targets = state["test_targets"]
    print_status(f"Using test targets from ChangeSpec: {test_targets}", "info")

    return {
        **state,
        "test_coder_response": response_content,
        "test_coder_success": test_coder_success,
        "messages": state["messages"] + messages + [response],
    }
