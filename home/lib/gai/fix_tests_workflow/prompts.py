import os

from .state import (
    FixTestsState,
    collect_historical_iteration_files,
    collect_all_test_output_files,
)


def build_editor_prompt(state: FixTestsState) -> str:
    """Build the prompt for the editor/fixer agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    prompt = f"""You are an expert test-fixing agent (iteration {iteration}). Your goal is to analyze test failures and make targeted code changes to fix them.

IMPORTANT INSTRUCTIONS:
- You should make code changes to fix the failing test, but do NOT run the test command yourself
- The workflow will handle running tests automatically after your changes
- You can only run shell commands if explicitly instructed to do so in the lessons.md file
- Focus on making minimal, targeted changes to fix the specific test failure

AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output)
@{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output) 
@{artifacts_dir}/test_output.txt - Test failure output"""

    # Check if lessons.md exists and include it
    lessons_path = os.path.join(artifacts_dir, "lessons.md")
    if os.path.exists(lessons_path):
        prompt += (
            f"\n@{artifacts_dir}/lessons.md - Lessons learned from previous attempts"
        )
        state["lessons_exists"] = True

    prompt += """

YOUR TASK:
1. Analyze the test failure in test_output.txt
2. Review the current CL changes and description for context
3. If lessons.md exists, carefully review all lessons learned and follow them as strict rules"""

    if state["lessons_exists"]:
        prompt += """
4. Pay special attention to any shell commands mentioned in lessons.md - you MUST run these if instructed
5. Ensure you don't repeat any mistakes documented in the lessons"""

    prompt += """
4. Make targeted code changes to fix the test failure
5. Explain your reasoning and changes clearly

RESPONSE FORMAT:
- Provide analysis of the test failure
- Explain your fix approach and reasoning
- Show the specific code changes you're making
- Do NOT run the test command - the workflow handles testing"""

    return prompt


def build_context_prompt(state: FixTestsState) -> str:
    """Build the prompt for the context/research agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    prompt = f"""You are a research and context agent (iteration {iteration}). Your goal is to update the {artifacts_dir}/lessons.md and {artifacts_dir}/research.md files with new insights and lessons learned from the latest test failure.

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

    # Check if lessons.md and research.md exist
    lessons_path = os.path.join(artifacts_dir, "lessons.md")
    if os.path.exists(lessons_path):
        prompt += f"\n@{artifacts_dir}/lessons.md - Current lessons learned"

    research_path = os.path.join(artifacts_dir, "research.md")
    if os.path.exists(research_path):
        prompt += f"\n@{artifacts_dir}/research.md - Current research log and findings"

    # Add all available test output files
    all_test_outputs = collect_all_test_output_files(artifacts_dir, iteration)
    if all_test_outputs:
        prompt += f"\n{all_test_outputs}"

    # Add historical iteration files for context agent review
    historical_files = collect_historical_iteration_files(artifacts_dir, iteration)
    if historical_files:
        prompt += f"\n{historical_files}"

    prompt += f"""

FILE STRUCTURE AND PURPOSE:

LESSONS.MD:
- Contains H1 sections, each representing a specific lesson learned
- Each H1 section should have a descriptive title that captures the lesson
- Content should describe:
  - What went wrong in a previous attempt  
  - Clear actionable advice for the editor agent
  - Specific conditions when the advice applies
  - May include shell commands the editor MUST run
  - NEVER include recommendations to run test commands (workflow handles testing automatically)
- This file is shared with the editor agent and should contain only actionable lessons

RESEARCH.MD:
- Contains a detailed log of all research activities and findings
- Should include questions asked, answers found, and tool calls made
- Document both useful findings AND dead ends (what didn't work)
- Use clear structure with timestamps or iteration markers
- Include specific file paths, CL numbers, bug IDs, and other concrete references
- This file is ONLY for the context agent and should be reviewed thoroughly before each research session
- Use this to avoid repeating unsuccessful research approaches

YOUR TASK:
1. Analyze the latest test failure and editor attempt
2. THOROUGHLY REVIEW all historical iteration files above to identify patterns, repeated mistakes, and research opportunities
3. Research relevant information using available tools (code search, etc.)
4. Update {artifacts_dir}/lessons.md with new actionable lessons for the editor agent (based on current failure AND historical patterns)
5. Update {artifacts_dir}/research.md with detailed research findings, dead ends, and analysis of historical attempts
6. Respond "NO UPDATES" only if you have absolutely nothing useful to add to either file

RESPONSE FORMAT:
Either:
- "NO UPDATES" (if nothing new to add to either file)
- Explanation of updates made to the files with reasoning"""

    return prompt
