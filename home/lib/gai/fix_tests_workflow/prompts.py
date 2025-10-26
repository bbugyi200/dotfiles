import os

from .state import (
    FixTestsState,
    collect_all_agent_artifacts,
)


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

    # Check if requirements.md exists and include requirements directly in prompt
    requirements_path = os.path.join(artifacts_dir, "requirements.md")
    requirements_content = ""
    if os.path.exists(requirements_path):
        try:
            with open(requirements_path, "r") as f:
                requirements_content = f.read().strip()
            state["requirements_exists"] = True
        except Exception as e:
            print(f"Warning: Could not read requirements file: {e}")

    prompt += """

YOUR TASK:
- Analyze the test failure in test_output.txt
- Review the current CL changes and description for context"""

    if requirements_content:
        prompt += """
- Carefully follow all ADDITIONAL REQUIREMENTS listed below as strict rules
- Pay special attention to any shell commands mentioned in the requirements - you MUST run these if instructed
- Ensure you don't repeat any mistakes documented in the requirements"""

    prompt += """
- Make targeted code changes to fix the test failure
- Explain your reasoning and changes clearly"""

    prompt += """

RESPONSE FORMAT:
- Provide analysis of the test failure
- Explain your fix approach and reasoning
- Show the specific code changes you're making
- Do NOT run the test command - the workflow handles testing"""

    # Add ADDITIONAL REQUIREMENTS section at the bottom
    if requirements_content:
        prompt += f"""

### ADDITIONAL REQUIREMENTS
{requirements_content}"""

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

    prompt = f"""You are a research and context agent (iteration {iteration}). Your goal is to update the {artifacts_dir}/requirements.md and {artifacts_dir}/research.md files with new insights and requirements learned from the latest test failure.

CRITICAL INSTRUCTIONS:
- If you have nothing novel or useful to add to either file, respond with EXACTLY: "NO UPDATES"
- If you output "NO UPDATES", the workflow will abort
- If you don't output "NO UPDATES" but also don't update at least one of the files, you'll get up to 3 retries
- Focus on adding truly useful, actionable information that will help the next editor agent succeed
- NEVER recommend that the editor agent run test commands - the workflow handles all test execution automatically

AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output)
@{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output)
@{artifacts_dir}/test_output.txt - Original test failure output
@{artifacts_dir}/agent_reply.md - Full response from the last editor agent"""

    # Check if research.md exists
    research_path = os.path.join(artifacts_dir, "research.md")
    if os.path.exists(research_path):
        prompt += f"\n@{artifacts_dir}/research.md - Current research log and findings"

    # Add ALL agent artifacts from all iterations
    all_agent_artifacts = collect_all_agent_artifacts(artifacts_dir, iteration)
    if all_agent_artifacts:
        prompt += f"\n{all_agent_artifacts}"

    prompt += f"""

FILE STRUCTURE AND PURPOSE:

REQUIREMENTS.MD:
- Contains a bulleted list of short, clear, and descriptive requirements using "-" bullets
- Each bullet point should be a specific, actionable requirement for the editor agent
- Requirements should describe:
  - What went wrong in previous attempts and how to avoid it
  - Clear actionable advice for the editor agent
  - Specific conditions when the advice applies
  - May include shell commands the editor MUST run
  - NEVER include recommendations to run test commands (workflow handles testing automatically)
- This file content is included DIRECTLY in the editor agent's prompt under "ADDITIONAL REQUIREMENTS"
- CRITICAL: Ensure diversity from previous requirements - avoid creating requirements too similar to previous iterations

RESEARCH.MD:
- Contains a detailed log of all research activities and findings
- Should include questions asked, answers found, and tool calls made
- Document both useful findings AND dead ends (what didn't work)
- Use clear structure with timestamps or iteration markers
- Include specific file paths, CL numbers, bug IDs, and other concrete references
- This file is ONLY for the context agent and should be reviewed thoroughly before each research session
- Use this to avoid repeating unsuccessful research approaches

DIVERSITY REQUIREMENTS:
- Review all PREVIOUS REQUIREMENTS FILES above to understand what requirements were given to previous editor agents
- While improving the editor agent's result is ideal, diversity of editor agent output is CRITICAL
- Make sure the new requirements.md file is NOT too similar to ones given to previous editor agents
- Vary your approach: if previous requirements focused on one aspect, try a different angle
- Balance effectiveness with diversity to encourage different approaches to solving the problem

YOUR TASK:
- Analyze the latest test failure and editor attempt
- THOROUGHLY REVIEW all historical iteration files and previous requirements to identify patterns, repeated mistakes, and research opportunities
- Research relevant information using available tools (code search, etc.)
- Create a NEW {artifacts_dir}/requirements.md with diverse, actionable requirements for the next editor agent (ensuring it's different from previous iterations)
   - Use ONLY "-" characters for bullet points (but alternate between + and - for subbullets, if those are needed).
   - Format: "- Requirement text here"
- Update {artifacts_dir}/research.md with detailed research findings, dead ends, and analysis of historical attempts
- Respond "NO UPDATES" only if you have absolutely nothing useful to add to either file

RESPONSE FORMAT:
Either:
- "NO UPDATES" (if nothing new to add to either file)
- Explanation of updates made to the files with reasoning"""

    return prompt
