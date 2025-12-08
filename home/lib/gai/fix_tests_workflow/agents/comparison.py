import os

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import (
    print_status,
)
from shared_utils import (
    add_test_output_to_log,
    ensure_str_content,
)

from ..prompts import (
    build_test_failure_comparison_prompt,
)
from ..state import (
    FixTestsState,
)


def run_test_failure_comparison_agent(state: FixTestsState) -> FixTestsState:
    """Run agent to compare current test failure with previous test failure and determine if research agents should be re-run."""
    iteration = state["current_iteration"]
    print(f"Running test failure comparison agent (iteration {iteration})...")
    artifacts_dir = state["artifacts_dir"]
    print(
        "Comparing current test failure against all previous test outputs in tests.md"
    )
    editor_iteration = iteration - 1
    current_test_output_file = os.path.join(
        artifacts_dir, f"editor_iter_{editor_iteration}_test_output.txt"
    )
    current_test_output_content = None
    try:
        with open(current_test_output_file) as f:
            current_test_output_content = f.read()
    except Exception as e:
        print(f"⚠️ Warning: Could not read current test output file: {e}")
        return {
            **state,
            "meaningful_test_failure_change": True,
            "comparison_completed": True,
            "messages": state["messages"],
        }
    new_test_output_file = os.path.join(artifacts_dir, "new_test_output.txt")
    try:
        with open(new_test_output_file, "w") as f:
            f.write(current_test_output_content)
        print("✅ Created new_test_output.txt for comparison")
    except Exception as e:
        print(f"⚠️ Warning: Could not create new_test_output.txt: {e}")
        return {
            **state,
            "meaningful_test_failure_change": True,
            "comparison_completed": True,
            "messages": state["messages"],
        }
    prompt = build_test_failure_comparison_prompt(state)
    model = GeminiCommandWrapper()
    model.set_logging_context(
        agent_type="test_failure_comparison",
        iteration=iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
        workflow="fix-tests",
    )
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)
    print_status("Test failure comparison agent response received", "success")
    comparison_response_path = os.path.join(
        artifacts_dir, f"test_failure_comparison_iter_{iteration}_response.txt"
    )
    with open(comparison_response_path, "w") as f:
        f.write(ensure_str_content(response.content))
    meaningful_change = False
    matched_iteration = None
    lines = ensure_str_content(response.content).split("\n")
    for line in lines:
        if line.startswith("MEANINGFUL_CHANGE:"):
            result = line.split(":", 1)[1].strip().upper()
            if result in ["YES", "TRUE", "1"]:
                meaningful_change = True
                print("✅ Novel test failure detected - research agents will be re-run")
            else:
                meaningful_change = False
                print(
                    "✅ Test failure matches previous iteration - skipping research agents"
                )
        elif line.startswith("MATCHED_ITERATION:"):
            try:
                matched_iteration = int(line.split(":", 1)[1].strip())
                print(f"✅ Test output matches iteration {matched_iteration}")
            except ValueError:
                print("⚠️ Warning: Could not parse MATCHED_ITERATION")
    if "MEANINGFUL_CHANGE:" not in ensure_str_content(response.content):
        meaningful_change = True
        print("⚠️ Could not parse comparison result - assuming novel failure")
    if meaningful_change and current_test_output_content:
        add_test_output_to_log(
            artifacts_dir=artifacts_dir,
            iteration=iteration,
            test_output=current_test_output_content,
            test_output_is_meaningful=True,
        )
        print(f"✅ Added meaningful test output for iteration {iteration} to log files")
    elif not meaningful_change:
        add_test_output_to_log(
            artifacts_dir=artifacts_dir,
            iteration=iteration,
            test_output=None,
            test_output_is_meaningful=False,
            matched_iteration=matched_iteration,
        )
        print(
            f"✅ Recorded non-meaningful test output for iteration {iteration} in log files"
        )
    return {
        **state,
        "meaningful_test_failure_change": meaningful_change,
        "comparison_completed": True,
        "matched_iteration": matched_iteration,
        "messages": state["messages"] + messages + [response],
    }
