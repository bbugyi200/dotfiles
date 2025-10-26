import os

from .state import (
    FixTestsState,
    collect_all_test_output_files,
    collect_historical_iteration_files,
    collect_previous_requirements_files,
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

ADDITIONAL REQUIREMENTS:
{requirements_content}"""

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

    # Add all available test output files
    all_test_outputs = collect_all_test_output_files(artifacts_dir, iteration)
    if all_test_outputs:
        prompt += f"\n{all_test_outputs}"

    # Add previous requirements files for diversity tracking
    previous_requirements = collect_previous_requirements_files(
        artifacts_dir, iteration
    )
    if previous_requirements:
        prompt += f"\n{previous_requirements}"

    # Add historical iteration files for context agent review
    historical_files = collect_historical_iteration_files(artifacts_dir, iteration)
    if historical_files:
        prompt += f"\n{historical_files}"

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
1. Analyze the latest test failure and editor attempt
2. THOROUGHLY REVIEW all historical iteration files and previous requirements to identify patterns, repeated mistakes, and research opportunities
3. Research relevant information using available tools (code search, etc.)
4. Create a NEW {artifacts_dir}/requirements.md with diverse, actionable requirements for the next editor agent (ensuring it's different from previous iterations)
   - Use ONLY "-" characters for bullet points (not *, +, or other symbols)
   - Format: "- Requirement text here"
5. Update {artifacts_dir}/research.md with detailed research findings, dead ends, and analysis of historical attempts
6. Respond "NO UPDATES" only if you have absolutely nothing useful to add to either file

RESPONSE FORMAT:
Either:
- "NO UPDATES" (if nothing new to add to either file)
- Explanation of updates made to the files with reasoning"""

    return prompt
