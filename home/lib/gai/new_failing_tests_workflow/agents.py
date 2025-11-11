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

    # Extract TEST_TARGETS from response
    response_lines = response_content.strip().split("\n")
    test_targets = None

    # Check the last few lines for TEST_TARGETS
    i = len(response_lines) - 1
    while i >= max(0, len(response_lines) - 20):  # Check last 20 lines
        line = response_lines[i]
        line_stripped = line.strip()
        if line_stripped.startswith("TEST_TARGETS:"):
            # Extract test targets (single or multi-line format)
            inline_value = line_stripped[len("TEST_TARGETS:") :].strip()
            if inline_value:
                # Single-line format
                test_targets = inline_value
                print_status(
                    f"Extracted test targets (single-line): {test_targets}", "info"
                )
            else:
                # Multi-line format - collect lines following TEST_TARGETS:
                # Lines can have any amount of leading whitespace (including none)
                targets = []
                j = i + 1
                while j < len(response_lines):
                    next_line = response_lines[j]
                    stripped = next_line.strip()
                    # Continue collecting until we hit a blank line
                    if not stripped:
                        break  # Blank line, end of field
                    else:
                        targets.append(stripped)
                        j += 1
                test_targets = "\n".join(targets) if targets else ""
                print_status(
                    f"Extracted test targets (multi-line): {test_targets}", "info"
                )
            break  # Found TEST_TARGETS, stop searching
        i -= 1

    # Validate TEST_TARGETS is present
    if not test_targets:
        print_status(
            "ERROR: Test coder agent did not output TEST_TARGETS - this is required!",
            "error",
        )
        return {
            **state,
            "test_coder_response": response_content,
            "test_coder_success": False,
            "test_targets": None,
            "messages": state["messages"] + messages + [response],
        }

    # Validate TEST_TARGETS is not empty
    if not test_targets or test_targets.lower() == "":
        print_status(
            "ERROR: Test coder agent output empty TEST_TARGETS - must provide valid targets or 'None'",
            "error",
        )
        return {
            **state,
            "test_coder_response": response_content,
            "test_coder_success": False,
            "test_targets": None,
            "messages": state["messages"] + messages + [response],
        }

    # Check if changes were made using hg diff
    import subprocess

    try:
        result = subprocess.run(
            ["hg", "diff"],
            capture_output=True,
            text=True,
            check=False,
        )
        has_changes = bool(result.stdout.strip())
        test_coder_success = has_changes

        if has_changes:
            print_status(
                "Test coder agent made changes (hg diff shows output)", "success"
            )
        else:
            print_status(
                "WARNING: Test coder agent did not make any changes (hg diff is empty)",
                "warning",
            )
    except Exception as e:
        print_status(f"Error checking hg diff: {e}", "error")
        test_coder_success = False

    print_status(f"Test targets validated: {test_targets}", "success")

    return {
        **state,
        "test_coder_response": response_content,
        "test_coder_success": test_coder_success,
        "test_targets": test_targets,
        "messages": state["messages"] + messages + [response],
    }
