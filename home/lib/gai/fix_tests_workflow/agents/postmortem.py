import os

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import (
    print_status,
)
from shared_utils import (
    add_postmortem_to_log,
    ensure_str_content,
)

from ..state import (
    FixTestsState,
)


def run_postmortem_agent(state: FixTestsState) -> FixTestsState:
    """Run postmortem agent to analyze why the last iteration failed to make meaningful progress."""
    iteration = state["current_iteration"]
    print(f"Running postmortem agent (iteration {iteration})...")
    prompt = _build_postmortem_prompt(state)
    model = GeminiCommandWrapper(model_size="big")
    model.set_logging_context(
        agent_type="postmortem",
        iteration=iteration,
        workflow_tag=state.get("workflow_tag"),
        artifacts_dir=state.get("artifacts_dir"),
    )
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)
    print_status("Postmortem agent response received", "success")
    postmortem_response_path = os.path.join(
        state["artifacts_dir"], f"postmortem_iter_{iteration}_response.txt"
    )
    with open(postmortem_response_path, "w") as f:
        f.write(ensure_str_content(response.content))
    add_postmortem_to_log(
        artifacts_dir=state["artifacts_dir"],
        iteration=iteration,
        postmortem_content=ensure_str_content(response.content),
    )
    return {
        **state,
        "postmortem_completed": True,
        "postmortem_content": ensure_str_content(response.content),
        "messages": state["messages"] + messages + [response],
    }


def _build_postmortem_prompt(state: FixTestsState) -> str:
    """Build the prompt for the postmortem agent."""
    artifacts_dir = state["artifacts_dir"]
    local_artifacts = state.get("local_artifacts", {})
    iteration = state["current_iteration"]
    last_editor_iteration = iteration - 1

    cl_changes_path = local_artifacts.get(
        "cl_changes_diff", "bb/gai/fix-tests/cl_changes.diff"
    )
    cl_desc_path = local_artifacts.get("cl_desc_txt", "bb/gai/fix-tests/cl_desc.txt")

    prompt = f"You are a postmortem analysis agent (iteration {iteration}). Your goal is to analyze why the previous iteration failed to make meaningful progress in fixing the test failure.\n\n# CONTEXT:\nThe test failure comparison agent determined that the test output from iteration {last_editor_iteration} was not meaningfully different from previous test outputs. This suggests that the last editor iteration either:\n1. Made no effective changes to fix the underlying issue\n2. Made changes that didn't address the root cause\n3. Made changes that introduced new issues but didn't resolve the original problem\n4. Made changes that were syntactically correct but logically ineffective\n\n# YOUR ANALYSIS FOCUS:\nInvestigate what went wrong with iteration {last_editor_iteration} and why it failed to make meaningful progress.\n\n# AVAILABLE CONTEXT FILES:\n@{cl_changes_path} - Current CL changes\n@{cl_desc_path} - Current CL description"
    for iter_num in range(1, iteration):
        prompt += f"\n- @{artifacts_dir}/planner_iter_{iter_num}_response.txt - Planner response for iteration {iter_num}\n- @{artifacts_dir}/editor_iter_{iter_num}_response.txt - Editor response for iteration {iter_num}\n- @{artifacts_dir}/editor_iter_{iter_num}_changes.diff - Code changes from iteration {iter_num}\n- @{artifacts_dir}/editor_iter_{iter_num}_test_output.txt - Test output from iteration {iter_num}"
        todos_file = os.path.join(artifacts_dir, f"editor_iter_{iter_num}_todos.txt")
        if os.path.exists(todos_file):
            prompt += f"\n- @{artifacts_dir}/editor_iter_{iter_num}_todos.txt - Todo list for iteration {iter_num}"
    prompt += f"\n\n# ANALYSIS QUESTIONS TO ANSWER:\n1. **What was the planner's strategy for iteration {last_editor_iteration}?**\n   - Review the planner response and todo list\n   - Was the strategy sound or flawed?\n   - Did it address the right root causes?\n\n2. **How well did the editor execute the plan?**\n   - Review the editor response and actual code changes\n   - Did the editor complete all todos as requested?\n   - Were the code changes technically correct?\n   - Did the editor make any obvious mistakes?\n\n3. **Why didn't the changes fix the test failure?**\n   - Compare the test outputs before and after the iteration\n   - What specific aspects of the test failure remained unchanged?\n   - Were the changes addressing symptoms rather than root causes?\n\n4. **What patterns emerge from previous iterations?**\n   - Are we stuck in a loop of similar unsuccessful approaches?\n   - Have we been avoiding certain types of changes that might be necessary?\n   - Are there recurring themes in the failures?\n\n5. **What should be done differently in the next iteration?**\n   - What alternative approaches should be considered?\n   - What assumptions should be questioned?\n   - What areas need deeper investigation?\n\n# RESPONSE FORMAT:\nStructure your postmortem analysis as follows:\n\n## Iteration {last_editor_iteration} Strategy Analysis\n- Analyze the planner's approach and todo list\n- Assess whether the strategy was appropriate for the problem\n\n## Editor Execution Analysis  \n- Review how well the editor executed the plan\n- Identify any execution issues or deviations from the plan\n\n## Root Cause Analysis\n- Analyze why the changes didn't fix the test failure\n- Compare test outputs to identify what didn't change\n\n## Pattern Recognition\n- Identify recurring patterns or themes across iterations\n- Note if we're stuck in unproductive loops\n\n## Recommendations for Next Iteration\n- Specific suggestions for alternative approaches\n- Areas that need deeper investigation or different strategies\n- Assumptions that should be reconsidered\n\n# IMPORTANT NOTES:\n- Focus on actionable insights for improving the next iteration\n- Be specific about what went wrong and why\n- Avoid generic advice - provide concrete analysis based on the specific iteration\n- Look for root causes, not just symptoms\n- Consider whether the approach has been too narrow or missing key areas"
    user_instructions_content = ""
    user_instructions_file = state.get("user_instructions_file")
    if user_instructions_file and os.path.exists(user_instructions_file):
        try:
            with open(user_instructions_file) as f:
                user_instructions_content = f.read().strip()
        except Exception as e:
            print(f"Warning: Could not read user instructions file: {e}")
    if user_instructions_content:
        prompt += f"\n\n# ADDITIONAL INSTRUCTIONS:\n{user_instructions_content}"
    return prompt
