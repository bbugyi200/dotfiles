import os

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import AIMessage, HumanMessage
from rich_utils import (
    print_status,
)
from shared_utils import (
    ensure_str_content,
)

from ..state import (
    FixTestsState,
)


def _build_oneshot_prompt(
    state: FixTestsState, context_log_file: str | None = None
) -> str:
    """Build the prompt for the oneshot test fixer agent."""
    artifacts_dir = state["artifacts_dir"]
    design_docs_note = ""
    bb_design_dir = os.path.expanduser("~/bb/design")
    if os.path.isdir(bb_design_dir):
        design_docs_note = (
            f"\n+ The @{bb_design_dir} directory contains relevant design docs."
        )
    context_section = f"\n# AVAILABLE CONTEXT FILES\n\n* @{artifacts_dir}/test_output.txt - Test failure output\n* @{artifacts_dir}/cl_desc.txt - This CL's description\n* @{artifacts_dir}/cl_changes.diff - A diff of this CL's changes"
    if context_log_file and os.path.exists(context_log_file):
        context_section += f"\n* @{context_log_file} - Previous workflow attempts log"
    context_file_directory = state.get("context_file_directory")
    if context_file_directory and os.path.isdir(context_file_directory):
        try:
            md_files = sorted(
                [
                    f
                    for f in os.listdir(context_file_directory)
                    if f.endswith(".md") or f.endswith(".txt")
                ]
            )
            if md_files:
                context_section += "\n\n## Additional Context Files\n"
                for md_file in md_files:
                    file_path = os.path.join(context_file_directory, md_file)
                    context_section += f"* @{file_path} - {md_file}\n"
        except Exception as e:
            print(f"⚠️ Warning: Could not list context files: {e}")
    clsurf_output_file = state.get("clsurf_output_file")
    if clsurf_output_file and os.path.exists(clsurf_output_file):
        context_section += f"\n* @{clsurf_output_file} - Submitted CLs for this project"
    prompt = f"""Can you help me fix the test failure?{design_docs_note}\n\n{context_section}\n\n# IMPORTANT INSTRUCTIONS\n\n1. **Make code changes** to attempt to fix the test failures\n2. **Run tests** after making changes to verify if the fix worked\n3. **Leave your changes in place** even if tests still fail - do NOT revert your changes\n4. **End your response** with a "### Test Fixer Log" section\n\n# RESPONSE FORMAT\n\nCRITICAL: You MUST end your response with a "### Test Fixer Log" section. This section should document:\n- What changes you made and why\n- What tests you ran and what the results were\n- Whether the tests passed, partially passed, or still failed\n- Any errors or issues encountered (e.g., build failures, new test failures, etc.)\n\nExample format:\n\n### Test Fixer Log\n\n#### Changes Made\n- Modified file X to fix issue Y\n- Updated test setup in file Z\n\n#### Test Results\n- Ran tests: [command used]\n- Result: [passed/failed/partial]\n- Details: [specific information about what passed/failed]\n\n#### Status\n- [FIXED/PARTIALLY_FIXED/FAILED/BUILD_ERROR]\n"""
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


def _build_oneshot_postmortem_prompt(
    state: FixTestsState, test_fixer_log_file: str
) -> str:
    """Build the prompt for the oneshot postmortem agent."""
    artifacts_dir = state["artifacts_dir"]
    prompt = f"""You are a postmortem analyst reviewing a failed attempt to fix test failures.\n\n# YOUR TASK:\nAnalyze the test fixer's attempt and provide insights on what went wrong and what should be tried next.\n\n# AVAILABLE CONTEXT FILES:\n* @{artifacts_dir}/test_output.txt - Original test failure output\n* @{test_fixer_log_file} - Log of what the test fixer tried and the results\n* @{artifacts_dir}/cl_desc.txt - This CL's description\n* @{artifacts_dir}/cl_changes.diff - Changes made by this CL (before test fixer ran)\n\n# RESPONSE FORMAT:\n\nCRITICAL: You MUST structure your response with a "### Postmortem" section. ONLY the content in the "### Postmortem" section will be stored as an artifact. Everything outside this section will be discarded.\n\nYou may include explanatory text before the ### Postmortem section, but the actual analysis must be in the ### Postmortem section.\n\n### Postmortem\n\n[Put all your analysis here. Structure it as follows:]\n\n#### What the Test Fixer Tried\n- Summary of changes made\n- Approach taken\n\n#### Why It Failed\n- Root cause analysis\n- What was wrong with the approach\n- What was missed or misunderstood\n\n#### Recommended Next Steps\n1. [First thing to try]\n2. [Second thing to try]\n3. [Alternative approaches]\n\n#### Key Insights\n- Important observations about the codebase\n- Patterns or dependencies that should be considered\n- Potential pitfalls to avoid\n"""
    return prompt


def run_oneshot_agent(
    state: FixTestsState, context_log_file: str | None = None
) -> FixTestsState:
    """
    Run the oneshot test fixer agent to attempt fixing the test failures.

    This is a simplified, single-shot approach that:
    1. Makes code changes to fix test failures
    2. Runs tests to verify the fix
    3. Logs what was done in a "Test Fixer Log" section

    If the tests still fail, a postmortem agent is run to analyze what went wrong.

    Args:
        state: Current workflow state
        context_log_file: Optional path to log.md from previous workflow attempts (for final retry)

    Returns:
        Updated state with oneshot results
    """
    artifacts_dir = state["artifacts_dir"]
    workflow_tag = state.get("workflow_tag", "UNKNOWN")
    is_final_retry = context_log_file is not None
    agent_label = "final oneshot retry" if is_final_retry else "initial oneshot"
    print_status(f"Running {agent_label} test fixer agent...", "progress")
    prompt = _build_oneshot_prompt(state, context_log_file)
    model = GeminiCommandWrapper(model_size="big")
    model.set_logging_context(
        agent_type="oneshot" if not is_final_retry else "oneshot_final",
        iteration=1,
        workflow_tag=workflow_tag,
        artifacts_dir=artifacts_dir,
    )
    messages: list[HumanMessage | AIMessage] = [HumanMessage(content=prompt)]
    response = model.invoke(messages)
    print_status(f"{agent_label.capitalize()} agent response received", "success")
    response_suffix = "_final" if is_final_retry else ""
    response_path = os.path.join(
        artifacts_dir, f"oneshot{response_suffix}_response.txt"
    )
    response_content = ensure_str_content(response.content)
    with open(response_path, "w") as f:
        f.write(response_content)
    print(f"✅ Saved oneshot response to {response_path}")
    from shared_utils import _extract_section

    test_fixer_log = _extract_section(response_content, "Test Fixer Log")
    test_fixer_log_path = os.path.join(
        artifacts_dir, f"oneshot{response_suffix}_test_fixer_log.txt"
    )
    with open(test_fixer_log_path, "w") as f:
        f.write(test_fixer_log)
    print(f"✅ Saved test fixer log to {test_fixer_log_path}")
    tests_fixed = any(
        status in test_fixer_log.upper()
        for status in ["FIXED", "PASSED", "ALL TESTS PASS"]
    )
    tests_failed = any(
        status in test_fixer_log.upper()
        for status in ["FAILED", "BUILD_ERROR", "PARTIALLY_FIXED"]
    )
    oneshot_success = tests_fixed and (not tests_failed)
    oneshot_postmortem = None
    if not oneshot_success:
        print_status(
            f"Tests still failing after {agent_label} - running postmortem...",
            "warning",
        )
        postmortem_prompt = _build_oneshot_postmortem_prompt(state, test_fixer_log_path)
        postmortem_model = GeminiCommandWrapper(model_size="big")
        postmortem_model.set_logging_context(
            agent_type=(
                "oneshot_postmortem"
                if not is_final_retry
                else "oneshot_final_postmortem"
            ),
            iteration=1,
            workflow_tag=workflow_tag,
            artifacts_dir=artifacts_dir,
        )
        postmortem_messages: list[HumanMessage | AIMessage] = [
            HumanMessage(content=postmortem_prompt)
        ]
        postmortem_response = postmortem_model.invoke(postmortem_messages)
        postmortem_response_path = os.path.join(
            artifacts_dir, f"oneshot{response_suffix}_postmortem_response.txt"
        )
        postmortem_content = ensure_str_content(postmortem_response.content)
        with open(postmortem_response_path, "w") as f:
            f.write(postmortem_content)
        print(f"✅ Saved postmortem response to {postmortem_response_path}")
        oneshot_postmortem = _extract_section(postmortem_content, "Postmortem")
        postmortem_path = os.path.join(
            artifacts_dir, f"oneshot{response_suffix}_postmortem.txt"
        )
        with open(postmortem_path, "w") as f:
            f.write(oneshot_postmortem)
        print(f"✅ Saved postmortem to {postmortem_path}")
    if is_final_retry:
        return {
            **state,
            "final_oneshot_completed": True,
            "test_passed": oneshot_success,
            "messages": state["messages"] + messages + [response],
        }
    else:
        return {
            **state,
            "oneshot_completed": True,
            "oneshot_success": oneshot_success,
            "oneshot_test_fixer_log": test_fixer_log,
            "oneshot_postmortem": oneshot_postmortem,
            "test_passed": oneshot_success,
            "messages": state["messages"] + messages + [response],
        }
