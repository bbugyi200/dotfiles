import os

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import (
    print_status,
)
from shared_utils import (
    add_iteration_section_to_log,
    ensure_str_content,
)

from ..prompts import (
    build_planner_prompt,
)
from ..state import (
    FixTestsState,
    extract_file_modifications_from_response,
)


def run_context_agent(state: FixTestsState) -> FixTestsState:
    """Run the context/planner agent to create editor todos."""
    iteration = state["current_iteration"]
    print(f"Running planner agent (iteration {iteration})...")
    prompt = build_planner_prompt(state)
    model = GeminiCommandWrapper(model_size="big")
    model.set_logging_context(
        agent_type="planner",
        iteration=iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)
    print_status("Planner agent response received", "success")
    planner_response_path = os.path.join(
        state["artifacts_dir"], f"planner_iter_{iteration}_response.txt"
    )
    with open(planner_response_path, "w") as f:
        f.write(ensure_str_content(response.content))
    artifacts_dir = state["artifacts_dir"]
    file_modifications = extract_file_modifications_from_response(
        ensure_str_content(response.content)
    )
    if not file_modifications:
        retries = state["context_agent_retries"] + 1
        if retries >= state["max_context_retries"]:
            print(
                f"Planner agent failed to provide structured file modifications after {retries} retries - workflow will abort"
            )
            return {
                **state,
                "test_passed": False,
                "failure_reason": f"Planner agent failed to provide structured file modifications after {retries} retries",
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }
        else:
            print(
                f"Planner agent didn't provide structured format, retrying ({retries}/{state['max_context_retries']})"
            )
            return {
                **state,
                "context_agent_retries": retries,
                "messages": state["messages"] + messages + [response],
            }
    print("✅ Structured file modifications received successfully")
    planner_logged_iteration = state.get("planner_logged_iteration", None)
    is_first_planner_for_iteration = planner_logged_iteration != iteration
    if is_first_planner_for_iteration:
        try:
            add_iteration_section_to_log(
                artifacts_dir=artifacts_dir,
                iteration=iteration,
                planner_response=ensure_str_content(response.content),
            )
            print(f"✅ Added planner response to log.md for iteration {iteration}")
        except Exception as e:
            print(f"⚠️ Warning: Failed to add iteration section to log.md: {e}")
    else:
        print(
            f"⚠️ Skipping duplicate log entry - planner response already logged for iteration {iteration}"
        )
    return {
        **state,
        "structured_modifications_received": True,
        "research_updated": True,
        "context_agent_retries": 0,
        "current_iteration": state["current_iteration"]
        + (1 if is_first_planner_for_iteration else 0),
        "verifier_notes": [],
        "planner_retry_notes": [],
        "planner_logged_iteration": (
            iteration if is_first_planner_for_iteration else planner_logged_iteration
        ),
        "messages": state["messages"] + messages + [response],
    }
