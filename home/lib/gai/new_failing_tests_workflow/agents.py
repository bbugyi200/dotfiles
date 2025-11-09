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

    # Check if test coder agent succeeded (look for SUCCESS or FAILURE at the end)
    response_lines = response_content.strip().split("\n")
    test_coder_success = False
    test_targets = None

    # Check the last few lines for SUCCESS/FAILURE and TEST_TARGETS
    i = len(response_lines) - 1
    while i >= max(0, len(response_lines) - 20):  # Check last 20 lines
        line = response_lines[i]
        line_stripped = line.strip()
        if line_stripped == "SUCCESS":
            test_coder_success = True
        elif line_stripped == "FAILURE":
            test_coder_success = False
        elif line_stripped.startswith("TEST_TARGETS:"):
            # Extract test targets (single or multi-line format)
            inline_value = line_stripped[len("TEST_TARGETS:") :].strip()
            if inline_value:
                # Single-line format
                test_targets = inline_value
                print_status(
                    f"Extracted test targets (single-line): {test_targets}", "info"
                )
            else:
                # Multi-line format - collect indented lines following TEST_TARGETS:
                targets = []
                j = i + 1
                while j < len(response_lines):
                    next_line = response_lines[j]
                    if next_line.startswith("  "):
                        target = next_line.strip()
                        if target:
                            targets.append(target)
                        j += 1
                    elif next_line.strip():
                        break  # Non-indented line, end of field
                    else:
                        break  # Blank line, end of field
                test_targets = "\n".join(targets) if targets else ""
                print_status(
                    f"Extracted test targets (multi-line): {test_targets}", "info"
                )
        i -= 1

    # Validate TEST_TARGETS is present
    if not test_targets:
        print_status(
            "ERROR: Test coder agent did not output TEST_TARGETS - this is required!",
            "error",
        )
        test_coder_success = False
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
        test_coder_success = False
        return {
            **state,
            "test_coder_response": response_content,
            "test_coder_success": False,
            "test_targets": None,
            "messages": state["messages"] + messages + [response],
        }

    status_msg = "succeeded" if test_coder_success else "reported failures"
    print_status(
        f"Test coder agent {status_msg}", "success" if test_coder_success else "warning"
    )

    print_status(f"Test targets validated: {test_targets}", "success")

    return {
        **state,
        "test_coder_response": response_content,
        "test_coder_success": test_coder_success,
        "test_targets": test_targets,
        "messages": state["messages"] + messages + [response],
    }
