import os

from .state import FixTestsState, collect_all_agent_artifacts


def build_editor_prompt(state: FixTestsState) -> str:
    """Build the prompt for the editor/fixer agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    strategy_instruction = """
STANDARD FIX MODE:
- Your goal is to make actual code changes to fix the underlying issues causing test failures
- Modify production code, test code, configuration, or dependencies as needed
- Focus on addressing the root cause of test failures rather than just masking symptoms"""

    prompt = f"""You are an expert test-fixing agent (iteration {iteration}). Your goal is to follow the research agent's todo list precisely to fix the failing test.

{strategy_instruction}

AGENT INSTRUCTIONS:
- You MUST follow the todo list in {artifacts_dir}/editor_todos.md EXACTLY as specified
- Complete each todo item in the exact sequence provided
- Mark each todo as COMPLETED by changing `- [ ]` to `- [X]` IMMEDIATELY after completing it
- You should make code changes to fix the failing test, but do NOT run the test command yourself
- Do NOT run any validation commands like `hg fix` - the verification agent will handle syntax checking
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
- Read and understand the todo list in editor_todos.md
- Follow the todo list EXACTLY in the order specified
- Complete each task as specified
- Mark each todo as COMPLETED by changing `- [ ]` to `- [X]` after completing it
- Verification agent will handle syntax checking after implementation"""

    if user_instructions_content:
        prompt += """
- Carefully review all USER INSTRUCTIONS listed below."""

    prompt += f"""

TODO EXECUTION (MANDATORY):
- Open and read {artifacts_dir}/editor_todos.md
- Complete EVERY SINGLE todo in the EXACT sequence they are defined
- Mark each todo as COMPLETED by changing `- [ ]` to `- [X]` IMMEDIATELY after completing it
- Edit the editor_todos.md file after each step to mark progress
- Do NOT skip any todos - ALL must be completed
- Do NOT run any validation commands - the verification agent will handle syntax checking

IMPLEMENTATION:
- Follow the todo list step by step
- Make the specific code changes recommended in the todos
- Update the todo file to mark completed items
- Verification agent will handle syntax validation

RESPONSE FORMAT:
- Confirm you've read the todo list
- Report on each todo item as you complete it
- Explain the specific changes you made for each todo
- Summarize all changes made
- The verification agent will handle syntax checking after your work"""

    # Add USER INSTRUCTIONS section at the bottom
    if user_instructions_content:
        prompt += f"""

USER INSTRUCTIONS:
{user_instructions_content}"""

    return prompt


def build_verification_prompt(state: FixTestsState) -> str:
    """Build the prompt for the verification agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]
    verification_retry = state.get("verification_retries", 0)

    prompt = f"""You are a verification agent (iteration {iteration}, retry {verification_retry}). Your goal is to ensure basic quality: no syntax errors and that the editor agent made a reasonable attempt at each todo item.

SPECIAL CASE - TODO ISSUES:
If the editor agent reports problems with the todos themselves (unclear instructions, missing context, impossible tasks, etc.), you should FIX THE TODOS and then mark as "VERIFICATION: FAIL" so the editor can retry with the improved todos. Update editor_todos.md with clearer, more specific instructions.

CRITICAL: Only reject changes for these SERIOUS issues:
1. SYNTAX ERRORS: Code that breaks compilation/parsing (obvious syntax issues visible in diff)
2. COMPLETELY MISSED TODOS: Editor agent didn't even attempt a todo item (and didn't report todo issues)
3. NO CHANGES MADE: Editor agent made no code changes at all (empty diff file) and didn't report todo issues

DO NOT reject for:
- Imperfect implementations (as long as some attempt was made)
- Different approaches than you would take
- Minor style issues or missing edge cases
- Incomplete solutions (partial progress is acceptable)

AVAILABLE FILES TO REVIEW:
@{artifacts_dir}/editor_todos.md - The todo list the editor was supposed to follow
@{artifacts_dir}/agent_reply.md - The editor agent's response about what they did
@{artifacts_dir}/editor_iter_{iteration}_changes.diff - The actual code changes made by the editor

VERIFICATION PROCESS:
1. First, check if editor agent reported problems with the todos themselves - if so, FIX THE TODOS and FAIL (so editor retries with improved todos)
2. Check if diff file is empty - FAIL if no changes were made and no todo issues reported
3. Visually inspect code changes for obvious syntax errors - FAIL if any found
4. Check each todo item was attempted (not necessarily perfectly) - FAIL if completely ignored without explanation
5. If all pass, always PASS regardless of implementation quality

YOUR RESPONSE MUST END WITH:
- "VERIFICATION: PASS" if changes were made AND no syntax errors AND all todos were attempted
- "VERIFICATION: FAIL" if todos were fixed OR no changes made OR syntax errors exist OR any todos were completely ignored

BE LENIENT: If the editor made any reasonable attempt at a todo, count it as attempted. If editor reports todo problems, fix the todos and then FAIL so the editor can retry with improved instructions.
"""

    return prompt


def build_context_prompt(state: FixTestsState) -> str:
    """Build the prompt for the context/research agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    strategy_guidance = """
STANDARD FIX MODE:
- Create todo items that instruct the editor agent to make actual fixes to underlying issues
- Focus on root cause analysis and proper code modifications
- Address bugs, API changes, implementation issues, or infrastructure problems
- Avoid simple workarounds - aim for genuine fixes that resolve the test failures

CODE MODIFICATION GUIDANCE:
- Updating non-test code is COMPLETELY FINE and EXPECTED when it fixes the test failure
- You should modify ANY code necessary to make tests pass, including production code, configuration, dependencies, etc.
- UNACCEPTABLE: Changes that undermine the work being done (e.g., removing new fields/features the CL adds just to fix tests)
- ACCEPTABLE: Fixing bugs, updating APIs, modifying implementation details, fixing infrastructure issues
"""

    prompt = f"""You are a research and analysis agent (iteration {iteration}). Your goal is to analyze the test failure and create a comprehensive todo list for the next editor agent.

{strategy_guidance}

CRITICAL INSTRUCTIONS:
- You must always create an editor_todos.md file - there is no option to skip this step
- Focus on creating actionable, specific todo items that will guide the editor agent to fix the test
- Ensure todo lists are diverse - NEVER create identical todo lists for different iterations
- NEVER recommend that editor agents run test commands - the workflow handles all test execution automatically

IMPORTANT: EDITOR AGENT LIMITATIONS:
- The editor agent has NO ACCESS to previous iteration files or responses
- The editor agent starts with a CLEAN CODEBASE - all changes from previous iterations are reverted/stashed
- The editor agent can ONLY see the todo list you create and the base context files (cl_changes.diff, cl_desc.txt, test_output.txt)
- You must include ALL necessary context and instructions directly in the todo list
- Do NOT reference previous agent responses or assume the editor knows what was tried before
- Each todo item must be completely self-contained with full context

AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output)
@{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output)
@{artifacts_dir}/test_output.txt - Original test failure output
@{artifacts_dir}/agent_reply.md - Full response from the last editor agent"""

    # Add ALL agent artifacts from all iterations
    all_agent_artifacts = collect_all_agent_artifacts(artifacts_dir, iteration)
    if all_agent_artifacts:
        prompt += f"\n{all_agent_artifacts}"

    prompt += """

IMPORTANT CONTEXT FOR ANALYSIS:
- Remember that updating non-test code is EXPECTED and appropriate when it fixes test failures
- Editor agents should modify ANY code necessary (production code, config, dependencies, etc.) to make tests pass
- UNACCEPTABLE changes: Removing new fields/features the CL adds just to make tests pass
- ACCEPTABLE changes: Bug fixes, API updates, implementation changes, infrastructure fixes"""

    prompt += f"""

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
   - Your response will be saved for future research agents to reference

2. TODO LIST CREATION:
   - Create a comprehensive todo list: {artifacts_dir}/editor_todos.md
   - Ensure the todo list is DIFFERENT from previous iterations (review past editor_todos files)
   - Include ONLY specific code changes that need to be made (no investigation or analysis tasks)
   - Each todo should specify exactly what code change to make and in which file
   - Order tasks logically - verification agent will handle syntax validation

EDITOR_TODOS.MD FILE FORMAT:
Create {artifacts_dir}/editor_todos.md with the following structure:
# Editor Todos - Iteration {iteration}

## Code Changes (ONLY)
- [ ] [specific code change needed in file X]
- [ ] [specific fix to apply in file Y]
- [ ] [specific modification to implement in file Z]

IMPORTANT: 
- Include ONLY concrete code changes that need to be made
- Do NOT include investigation, analysis, or research tasks
- Do NOT include validation tasks - the verification agent handles syntax checking
- Each todo should specify exactly what code change to make and in which file
- The research agent has already done all investigation - editor just needs to implement
- Each todo must be COMPLETELY SELF-CONTAINED with full context since editor has no access to previous iterations
- Include file paths, line numbers, exact code snippets, and detailed explanations in each todo item
- Do NOT assume the editor knows anything about previous attempts or failures

STANDARD MODE SPECIFIC GUIDANCE:
- Focus on todos that make actual fixes to the underlying issues
- Address root causes rather than symptoms
- Make comprehensive fixes that resolve the test failures properly

DIVERSITY REQUIREMENT:
- Review previous editor_todos files to ensure your new todo list takes a different approach
- If previous attempts focused on files X, try modifying files Y
- Vary the implementation strategy, specific fixes, or code change approach
- Ensure each iteration tries different code modifications to solve the problem
- Remember: since editor agents can't see previous attempts, you must learn from history and create DIFFERENT approaches
- Use the previous research agent responses to track what has been tried and ensure each new todo list explores a fresh angle

RESPONSE FORMAT:
Provide a summary of:
1. Research findings and analysis from reviewing the test failure and previous iterations
2. Key insights discovered that inform your approach
3. The approach taken in the new editor_todos.md file
4. How this todo list differs from previous attempts"""

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

    # Add USER INSTRUCTIONS section at the bottom
    if user_instructions_content:
        prompt += f"""

USER INSTRUCTIONS:
{user_instructions_content}"""

    return prompt
