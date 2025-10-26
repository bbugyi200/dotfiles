import os

from .state import FixTestsState, collect_all_agent_artifacts


def build_editor_prompt(state: FixTestsState) -> str:
    """Build the prompt for the editor/fixer agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    prompt = f"""You are an expert test-fixing agent (iteration {iteration}). Your goal is to analyze test failures and make targeted code changes to fix them.

IMPORTANT INSTRUCTIONS:
- You should make code changes to fix the failing test, but do NOT run the test command yourself
- The workflow will handle running tests automatically after your changes
- Focus on making minimal, targeted changes to fix the specific test failure

AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output)
@{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output) 
@{artifacts_dir}/test_output.txt - Test failure output"""

    # Add ALL agent artifacts from all iterations for comprehensive context
    all_agent_artifacts = collect_all_agent_artifacts(
        artifacts_dir, state["current_iteration"]
    )
    if all_agent_artifacts:
        prompt += f"\n{all_agent_artifacts}"

    # Check if user instructions file was provided and include content directly in prompt
    user_instructions_content = ""
    if state.get("user_instructions_file") and os.path.exists(
        state["user_instructions_file"]
    ):
        try:
            with open(state["user_instructions_file"], "r") as f:
                user_instructions_content = f.read().strip()
        except Exception as e:
            print(f"Warning: Could not read user instructions file: {e}")

    prompt += """

YOUR TASK:
- Carefully review the CL description and changes (cl_desc.txt and cl_changes.diff).
- Carefully review the test failure in test_output.txt and identify the root cause.
- Review the current CL changes and description for context"""

    if all_agent_artifacts:
        prompt += """
- Carefully review ALL previous editor agent attempts and the corresponding postmortem files (in other words, ALL
  editor_iter_*.txt files) to understand what approaches have failed and why."""

    if user_instructions_content:
        prompt += """
- Carefully follow all USER INSTRUCTIONS listed below as strict rules
- Pay special attention to any shell commands mentioned in the instructions - you MUST run these if instructed
- Ensure you don't repeat any mistakes documented in the instructions"""

    prompt += f"""

TODO WORKFLOW (MANDATORY):
- BEFORE making any changes, create a comprehensive todo list in {artifacts_dir}/editor_todos.md
- The todo list MUST include ALL steps needed to fix the test failure
- You MUST complete EVERY SINGLE todo in the EXACT sequence they are defined
- You MUST mark each todo as DONE IMMEDIATELY after completing it (edit the file after each step - NOT all at once at the end)
- You MUST complete ALL todos before finishing your work - incomplete todos are NOT acceptable

IMPLEMENTATION:
- Make targeted code changes to fix the test failure following your todo list
- Explain your reasoning and changes clearly"""

    prompt += """

RESPONSE FORMAT:
1. Create the todo list file FIRST (editor_todos.md) with ALL necessary steps
2. Review postmortems and previous failures analysis
3. Provide analysis of the test failure
4. Explain your fix approach and reasoning
5. Complete each todo sequentially, updating the file IMMEDIATELY after each step (show your progress)
6. Show the specific code changes you're making as you complete each todo
7. Ensure ALL todos are marked as DONE before finishing
8. Do NOT run the test command - the workflow handles testing"""

    # Add USER INSTRUCTIONS section at the bottom
    if user_instructions_content:
        prompt += f"""

### USER INSTRUCTIONS
{user_instructions_content}"""

    return prompt


def build_judge_prompt(state: FixTestsState) -> str:
    """Build the prompt for the judge agent to select the best changes."""
    artifacts_dir = state["artifacts_dir"]
    judge_iteration = state["current_judge_iteration"]

    prompt = f"""You are a judge agent (judge iteration {judge_iteration}). Your goal is to select EXACTLY ONE agent's changes from all the editor agent iterations that are most likely to push the test-fixing effort forward.

CRITICAL INSTRUCTIONS:
- You MUST select exactly one agent iteration to apply
- Choose changes that will help fix the test, even if they don't fully solve it
- Prefer changes that fix syntax errors, compilation errors, or reveal new test failures
- AVOID changes that introduce new build errors or make the situation worse
- Your response MUST include a line: "SELECTED AGENT: X" where X is the iteration number

AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes before any agent modifications
@{artifacts_dir}/cl_desc.txt - Current CL description
@{artifacts_dir}/test_output.txt - Original test failure output"""

    # Add all agent artifacts
    agent_files_info = ""
    for iter_num in range(1, state["current_iteration"]):
        # Agent response files
        response_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_response.txt"
        )
        if os.path.exists(response_file):
            agent_files_info += (
                f"\n@{response_file} - Agent {iter_num} analysis and approach"
            )

        # Agent diff files
        diff_file = os.path.join(artifacts_dir, f"editor_iter_{iter_num}_changes.diff")
        if os.path.exists(diff_file):
            agent_files_info += f"\n@{diff_file} - Agent {iter_num} code changes"

        # Agent test output files
        test_output_file = os.path.join(
            artifacts_dir, f"editor_iter_{iter_num}_test_output.txt"
        )
        if os.path.exists(test_output_file):
            agent_files_info += (
                f"\n@{test_output_file} - Agent {iter_num} test execution results"
            )

    if agent_files_info:
        prompt += f"\n\nAGENT ITERATION FILES:{agent_files_info}"

    prompt += """

SELECTION CRITERIA:
- Choose changes that move toward fixing the test, even if incomplete
- Fixes that reveal new information about the test failure are GOOD
- Syntax/compilation fixes that allow tests to run are GOOD  
- Changes that introduce new build errors are BAD
- Changes that don't address the core test failure are LESS PREFERRED

YOUR TASK:
- Review all agent responses, changes, and test results
- Analyze which changes are most likely to help fix the test
- Consider the progression: does an agent's change reveal new test failure details?
- Select the agent iteration that makes the most progress toward fixing the test

RESPONSE FORMAT:
- Provide analysis of each agent's changes and their potential impact
- Explain your reasoning for the selection
- End with exactly this format: "SELECTED AGENT: X" (where X is the iteration number)

Remember: You are selecting changes to APPLY to the codebase, so choose carefully!"""

    return prompt


def build_context_prompt(state: FixTestsState) -> str:
    """Build the prompt for the context/research agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    prompt = f"""You are a research and context agent (iteration {iteration}). Your goal is to create a comprehensive postmortem analysis file with insights learned from the latest test failure and editor attempt.

CRITICAL INSTRUCTIONS:
- You must always create a postmortem analysis - there is no option to skip this step
- Focus on analyzing what went wrong, what patterns emerge, and what should be tried differently
- NEVER recommend that future editor agents run test commands - the workflow handles all test execution automatically

AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output)
@{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output)
@{artifacts_dir}/test_output.txt - Original test failure output
@{artifacts_dir}/agent_reply.md - Full response from the last editor agent"""

    # Add ALL agent artifacts from all iterations
    all_agent_artifacts = collect_all_agent_artifacts(artifacts_dir, iteration)
    if all_agent_artifacts:
        prompt += f"\n{all_agent_artifacts}"

    prompt += f"""
YOUR TASK:
- Analyze the latest test failure and editor attempt
- THOROUGHLY REVIEW all historical iteration files and previous attempts to identify patterns, repeated mistakes, and learning opportunities
- Research relevant information using available tools (code search, etc.)
- Create a comprehensive postmortem analysis file: {artifacts_dir}/editor_iter_{iteration}_postmortem.txt
   - Include what went wrong in this iteration
   - Identify patterns across multiple iterations
   - Note what approaches have been tried and failed
   - Suggest what different approaches might work
   - Document any dead ends or anti-patterns discovered

POSTMORTEM FILE FORMAT:
Create {artifacts_dir}/editor_iter_{iteration}_postmortem.txt with the following structure:
- What went wrong in this iteration (read the last agent's test output, response, and agenchanges VERY carefully).
- Patterns identified across multiple iterations
- Approaches that have been tried and failed
- Suggested different approaches for future attempts
- Any dead ends or anti-patterns discovered
- Concrete insights for future editor agents

RESPONSE FORMAT:
Provide a summary of the postmortem analysis created with key insights and patterns identified."""

    return prompt
