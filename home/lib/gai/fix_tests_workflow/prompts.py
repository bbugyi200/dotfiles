import os

from .state import FixTestsState, collect_all_agent_artifacts


def build_editor_prompt(state: FixTestsState) -> str:
    """Build the prompt for the editor/fixer agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    prompt = f"""You are an expert test-fixing agent (iteration {iteration}). Your goal is to follow the research agent's todo list precisely to fix the failing test.

AGENT INSTRUCTIONS:
- You MUST follow the todo list in {artifacts_dir}/editor_todos.md EXACTLY as specified
- Complete each todo item in the exact sequence provided
- Mark each todo as DONE IMMEDIATELY after completing it
- You should make code changes to fix the failing test, but do NOT run the test command yourself
- You MUST run `hg fix` after making all changes to ensure no syntax errors
- The workflow will handle running tests automatically after your changes

AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output)
@{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output) 
@{artifacts_dir}/test_output.txt - Test failure output
@{artifacts_dir}/editor_todos.md - Your todo list to follow (MANDATORY)"""

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
- Read and understand the code change todo list in editor_todos.md
- Follow the todo list EXACTLY in the order specified
- Complete each code change task as specified
- Mark each todo as DONE after completing it
- The final todo will be running `hg fix` to ensure no syntax errors"""

    if user_instructions_content:
        prompt += """
- Carefully review all USER INSTRUCTIONS listed below."""

    prompt += f"""

CODE MODIFICATION GUIDANCE:
- Updating non-test code is COMPLETELY FINE and EXPECTED when it fixes the test failure
- You should modify ANY code necessary to make tests pass, including production code, configuration, dependencies, etc.
- UNACCEPTABLE: Changes that undermine the work being done (e.g., removing new fields/features the CL adds just to fix tests)
- ACCEPTABLE: Fixing bugs, updating APIs, modifying implementation details, fixing infrastructure issues

TODO EXECUTION (MANDATORY):
- Open and read {artifacts_dir}/editor_todos.md
- Complete EVERY SINGLE todo in the EXACT sequence they are defined
- Mark each todo as DONE IMMEDIATELY after completing it (edit the file after each step)
- Do NOT skip any todos - ALL must be completed
- The final todo should always be running `hg fix` to validate syntax

IMPLEMENTATION:
- Follow the todo list step by step
- Make the specific code changes recommended in the todos
- Update the todo file to mark completed items
- Run `hg fix` as specified in the validation section

RESPONSE FORMAT:
- Confirm you've read the code change todo list
- Report on each todo item as you complete it
- Explain the specific code changes you made for each todo
- Confirm you've run `hg fix` and report any issues found
- Summarize all code changes made"""

    # Add USER INSTRUCTIONS section at the bottom
    if user_instructions_content:
        prompt += f"""

USER INSTRUCTIONS:
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

    prompt = f"""You are a research and analysis agent (iteration {iteration}). Your goal is to analyze the test failure and create a comprehensive todo list for the next editor agent, while also maintaining a research log of your findings.

CRITICAL INSTRUCTIONS:
- You must always create an editor_todos.md file - there is no option to skip this step
- Focus on creating actionable, specific todo items that will guide the editor agent to fix the test
- Log all research findings to a persistent research.md file for future reference
- Ensure todo lists are diverse - NEVER create identical todo lists for different iterations
- NEVER recommend that editor agents run test commands - the workflow handles all test execution automatically

AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output)
@{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output)
@{artifacts_dir}/test_output.txt - Original test failure output
@{artifacts_dir}/agent_reply.md - Full response from the last editor agent
@{artifacts_dir}/research.md - Your persistent research log (if it exists)"""

    # Add ALL agent artifacts from all iterations
    all_agent_artifacts = collect_all_agent_artifacts(artifacts_dir, iteration)
    if all_agent_artifacts:
        prompt += f"\n{all_agent_artifacts}"

    prompt += f"""

IMPORTANT CONTEXT FOR ANALYSIS:
- Remember that updating non-test code is EXPECTED and appropriate when it fixes test failures
- Editor agents should modify ANY code necessary (production code, config, dependencies, etc.) to make tests pass
- UNACCEPTABLE changes: Removing new fields/features the CL adds just to make tests pass
- ACCEPTABLE changes: Bug fixes, API updates, implementation changes, infrastructure fixes

COMMON TEST FAILURE PATTERNS:
- NEW TESTS that never passed: Often test framework, setup, or dependency issues
- EXISTING TESTS broken by CL: Usually legitimate bugs that need fixing in the code
- UPSTREAM INFRASTRUCTURE failures: Need to be tracked down and resolved at the root cause
- Tests expecting old behavior: May need test updates if new behavior is correct

YOUR TASK:
1. RESEARCH AND ANALYSIS:
   - Analyze the latest test failure and editor attempt
   - THOROUGHLY REVIEW all historical iteration files to identify patterns and avoid repetition
   - Research relevant information using available tools (code search, etc.)
   - Update {artifacts_dir}/research.md with your findings (append new insights, don't overwrite)

2. TODO LIST CREATION:
   - Create a comprehensive todo list: {artifacts_dir}/editor_todos.md
   - Ensure the todo list is DIFFERENT from previous iterations (review past editor_todos files)
   - Include ONLY specific code changes that need to be made (no investigation or analysis tasks)
   - Each todo should specify exactly what code change to make and in which file
   - Order code changes logically, ending with `hg fix` for syntax validation

RESEARCH.MD FILE FORMAT:
Append to {artifacts_dir}/research.md with the following structure for this iteration:
## Iteration {iteration} Research - [timestamp]
- Test failure analysis
- Root cause investigation findings
- Code patterns discovered
- Previous attempts reviewed
- New insights gained
- Dead ends identified
- Successful approaches from other iterations

EDITOR_TODOS.MD FILE FORMAT:
Create {artifacts_dir}/editor_todos.md with the following structure:
# Editor Todos - Iteration {iteration}

## Code Changes (ONLY)
- [ ] [specific code change needed in file X]
- [ ] [specific fix to apply in file Y]
- [ ] [specific modification to implement in file Z]
- [ ] Run `hg fix` to ensure no syntax errors

IMPORTANT: 
- Include ONLY concrete code changes that need to be made
- Do NOT include investigation, analysis, or research tasks
- Do NOT include general validation tasks beyond `hg fix`
- Each todo should specify exactly what code change to make and in which file
- The research agent has already done all investigation - editor just needs to implement

DIVERSITY REQUIREMENT:
- Review previous editor_todos files to ensure your new todo list takes a different approach
- If previous attempts focused on files X, try modifying files Y
- Vary the implementation strategy, specific fixes, or code change approach
- Ensure each iteration tries different code modifications to solve the problem

RESPONSE FORMAT:
Provide a summary of:
1. Research findings added to research.md
2. Key insights from reviewing previous iterations
3. The approach taken in the new editor_todos.md file
4. How this todo list differs from previous attempts"""

    return prompt
