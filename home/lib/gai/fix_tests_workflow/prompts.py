import os

from .state import (
    FixTestsState,
    collect_all_research_md_files,
    collect_distinct_test_outputs_info,
)


def build_editor_prompt(state: FixTestsState) -> str:
    """Build the prompt for the editor/fixer agent."""
    artifacts_dir = state["artifacts_dir"]
    prompt = f"""You are an expert file-editing agent. Your goal is to follow the todo list precisely
to edit the specified files EXACTLY as specified.

# INSTRUCTIONS:
- You MUST follow the todo list in @{artifacts_dir}/editor_todos.md EXACTLY as specified.
- Complete each todo item in the exact sequence provided.
- Mark each todo as COMPLETED by changing `- [ ]` to `- [X]` IMMEDIATELY after completing it.
- Do NOT skip any todos - ALL must be completed.
- You should make code changes to fix the failing test, but do NOT run the test command yourself.
- Do NOT run any validation commands like `hg fix` - the verification agent will handle syntax checking.
- You MAY run a command to edit one or more files ONLY IF running this command
  is explicitly requested in a todo item.

# RESPONSE FORMAT:
- Confirm you've read the todo list.
- Explain the specific changes you made for each todo.
- Summarize all changes made."""

    return prompt


def build_research_prompt(state: FixTestsState, research_focus: str) -> str:
    """Build the prompt for research agents with different focus areas."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    focus_prompts = {
        "cl_scope": f"""You are a research agent focusing on CL SCOPE analysis (iteration {iteration}). Your goal is to perform deep research on non-test files to understand the scope and impact of the current change list (CL) being worked on.

# YOUR RESEARCH FOCUS:
- Analyze the CL changes to understand what new functionality or modifications are being introduced
- Research the codebase to understand how the changed code fits into the larger system
- Identify dependencies, related components, and potential impact areas
- Look for patterns in how similar functionality is implemented elsewhere in the codebase
- Understand the business logic and technical architecture around the changes""",
        "similar_tests": f"""You are a research agent focusing on SIMILAR TESTS analysis (iteration {iteration}). Your goal is to perform deep research on test files to find examples and patterns that could inspire solutions for fixing the failing test(s).

# YOUR RESEARCH FOCUS:
- Find other test files that test similar functionality to what's failing
- Look for test patterns, setup methods, and assertion styles that could be applicable
- Research how similar test failures have been resolved in the codebase
- Identify test utilities, helpers, or frameworks that might be useful
- Look for examples of tests that cover edge cases or complex scenarios similar to the failing test""",
        "test_failure": f"""You are a research agent focusing on TEST FAILURE analysis (iteration {iteration}). Your goal is to perform deep research specifically on the test failure itself to understand root causes and potential solutions.

# YOUR RESEARCH FOCUS:
- Analyze the specific error messages and stack traces in detail
- Research the failing test code to understand what it's trying to accomplish
- Look up documentation, comments, or related code that explains the expected behavior
- Research error patterns and common causes for this type of failure
- Investigate recent changes or issues that might have introduced this failure""",
        "prior_work_analysis": f"""You are a research agent focusing on PRIOR WORK ANALYSIS (iteration {iteration}). Your goal is to investigate whether previous work related to this project may have been incorrect and identify potential issues with prior implementations.

# YOUR RESEARCH FOCUS:
- Research the git/hg history to understand what changes were made in prior CLs related to this project
- Analyze whether previous implementations or fixes may have been flawed or incomplete
- Look for patterns of repeated fixes or reverts that suggest underlying issues
- Investigate if current test failures are related to incorrect assumptions made in previous work
- Examine code comments, TODOs, or issue tracking that might indicate known problems with prior work
- Research whether the current approach conflicts with or contradicts previous design decisions
- Identify areas where prior work may need to be reconsidered or corrected""",
    }

    base_prompt = focus_prompts.get(research_focus, focus_prompts["test_failure"])
    prompt = f"""{base_prompt}

# RESEARCH INSTRUCTIONS:
- Use your code search tools extensively to perform deep research
- Look beyond the immediate files - explore the broader codebase
- Search for relevant patterns, examples, and documentation
- Document your findings clearly and thoroughly
- Focus on actionable insights that will help the planner agents

# AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output)
@{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output)
@{artifacts_dir}/test_output.txt - Current test failure output"""

    # Add conditionally available files
    orig_test_output = os.path.join(artifacts_dir, "orig_test_output.txt")
    if os.path.exists(orig_test_output):
        prompt += f"""
@{artifacts_dir}/orig_test_output.txt - Original test failure output"""

    orig_cl_changes = os.path.join(artifacts_dir, "orig_cl_changes.diff")
    if os.path.exists(orig_cl_changes):
        prompt += f"""
@{artifacts_dir}/orig_cl_changes.diff - Original CL changes"""

    # Add previous iteration context
    prompt += """

# PREVIOUS ITERATION CONTEXT:
Review all previous iterations to understand what has been tried:"""

    for prev_iter in range(1, iteration):
        prompt += f"""
- @{artifacts_dir}/research_iter_{prev_iter}_response.txt - Previous research analysis
- @{artifacts_dir}/editor_iter_{prev_iter}_response.txt - Previous editor attempt  
- @{artifacts_dir}/editor_iter_{prev_iter}_changes.diff - Previous code changes
- @{artifacts_dir}/editor_iter_{prev_iter}_test_output.txt - Previous test results
- @{artifacts_dir}/editor_iter_{prev_iter}_todos.txt - Previous todo list"""

    prompt += f"""

# YOUR TASK:
1. **DEEP CODE RESEARCH**: Use your code search tools to thoroughly investigate your focus area
2. **PATTERN IDENTIFICATION**: Look for patterns, examples, and best practices relevant to your focus
3. **INSIGHT GENERATION**: Generate actionable insights that will help planner agents create better todos
4. **DOCUMENTATION**: Document your findings clearly with specific examples and references

# RESPONSE FORMAT:
Structure your response as follows:

## RESEARCH METHODOLOGY
- Describe your search strategy and approach
- List the key search terms and patterns you investigated

## KEY FINDINGS
- Document your most important discoveries
- Include specific file paths, code examples, and references
- Explain how each finding relates to the test failure

## ACTIONABLE INSIGHTS
- Provide specific insights that planner agents can use
- Suggest concrete approaches or solutions based on your research
- Highlight patterns or examples that could be applied

## RECOMMENDATIONS
- Specific recommendations for how to approach fixing the test failure
- Priority ranking of different approaches based on your research
- Potential pitfalls or considerations to keep in mind

# IMPORTANT NOTES:
- Focus on your specific research area ({research_focus.replace('_', ' ')})
- Use code search tools extensively - don't just rely on provided context files
- Look for concrete examples and patterns in the codebase
- Document specific file paths and code snippets in your findings
- Your research will be aggregated with other research agents' findings"""

    # Add user instructions if available
    user_instructions_content = ""
    if state.get("user_instructions_file") and os.path.exists(
        state["user_instructions_file"]
    ):
        try:
            with open(state["user_instructions_file"], "r") as f:
                user_instructions_content = f.read().strip()
        except Exception as e:
            print(f"Warning: Could not read user instructions file: {e}")

    if user_instructions_content:
        prompt += f"""

# ADDITIONAL INSTRUCTIONS:
{user_instructions_content}"""

    return prompt


def build_verification_prompt(state: FixTestsState) -> str:
    """Build the prompt for the verification agent."""
    artifacts_dir = state["artifacts_dir"]
    # Use current_iteration - 1 for editor files since iteration gets incremented by judge/context agents
    editor_iteration = state["current_iteration"] - 1
    prompt = f"""You are a verification agent. Your goal is to ensure basic quality: no syntax errors and that the
editor agent made a reasonable attempt at each todo item.

# CRITICAL - Only reject changes for these SERIOUS issues:
1. SYNTAX ERRORS: Code that breaks compilation/parsing (obvious syntax issues visible in diff).
2. COMPLETELY MISSED TODOS: Editor agent didn't even attempt a todo item.
3. NO CHANGES MADE: Editor agent made no code changes at all (empty diff file).

# DO NOT reject for:
- Imperfect implementations (as long as some attempt was made).
- Different approaches than you would take.
- Minor style issues or missing edge cases.
- Incomplete solutions (partial progress is acceptable).

# AVAILABLE FILES TO REVIEW:
@{artifacts_dir}/editor_todos.md - The todo list the editor was supposed to follow.
@{artifacts_dir}/agent_reply.md - The editor agent's response about what they did.
@{artifacts_dir}/editor_iter_{editor_iteration}_changes.diff - The actual code changes made by the editor.

# VERIFICATION PROCESS:
- Check if diff file is empty - FAIL if no changes were made.
- Visually inspect code changes for obvious syntax errors - FAIL if any found.
- Check each todo item was attempted (not necessarily perfectly) - FAIL if completely ignored without explanation.
- If all pass, always PASS regardless of implementation quality.

# YOUR RESPONSE MUST END WITH:
- "VERIFICATION: PASS" if changes were made AND no syntax errors AND all todos were attempted.
- "VERIFICATION: FAIL" if todos were fixed OR no changes made OR syntax errors exist OR any todos were completely ignored.

# COMMIT MESSAGE GENERATION:
If verification passes, provide a short descriptive message (5-10 words) summarizing the main change made. This will be used in the commit message. Include it in your response as:
"COMMIT_MSG: <your descriptive message>"

IMPORTANT: The commit message should NOT end with punctuation (no periods, exclamation marks, etc.)

Examples:
- "COMMIT_MSG: Fix import paths and module references"
- "COMMIT_MSG: Update test setup and configuration"
- "COMMIT_MSG: Resolve API compatibility issues"

BE LENIENT: If the editor made any reasonable attempt at a todo, count it as attempted.
"""

    return prompt


def build_test_failure_comparison_prompt(state: FixTestsState) -> str:
    """Build the prompt for the test failure comparison agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]
    distinct_test_outputs = state.get("distinct_test_outputs", [])

    prompt = f"""You are a test failure comparison agent (iteration {iteration}). Your goal is to compare the current test failure output with ALL previously distinct test failure outputs and determine whether the current failure is truly novel.

# YOUR TASK:
Determine if the current test failure represents a fundamentally new failure mode that has NEVER been seen before. Research agents should only be re-run when the failure is genuinely different from ALL previous distinct failures.

# CURRENT TEST FAILURE:
@{artifacts_dir}/test_output.txt - Current test failure output to analyze

# PREVIOUS DISTINCT TEST FAILURES:
{collect_distinct_test_outputs_info(distinct_test_outputs)}

# COMPARISON STRATEGY:
1. **Extract the core failure signature** from the current test output (error type, location, root cause)
2. **Compare against EACH distinct previous test output** to find similarities
3. **Determine novelty**: Is this failure mode fundamentally different from ALL previous distinct failures?

# MEANINGFUL CHANGE CRITERIA:
Consider the current failure NOVEL (requiring research) if it has ALL of these characteristics compared to ALL previous distinct failures:
1. **Different error messages**: Core error message or exception type is different from all previous
2. **Different failure location**: Test fails at a different point than all previous failures  
3. **Different error types**: Uses error types/stack traces not seen in any previous distinct failure
4. **Different root cause**: Underlying cause appears fundamentally different from all previous
5. **New failure pattern**: Represents a failure pattern not captured by any previous distinct failure

Consider the current failure NOT NOVEL (skip research) if it matches ANY previous distinct failure in:
1. **Same core error**: Essentially the same error with minor variations (line numbers, formatting, etc.)
2. **Same failure location**: Failing at the same logical point as a previous distinct failure
3. **Same error patterns**: Uses similar error types and patterns as a previous distinct failure
4. **Same root cause**: Underlying cause is the same as a previous distinct failure
5. **Covered failure mode**: Failure mode is already represented by a previous distinct failure

# ANALYSIS APPROACH:
1. **Read the current test failure** and extract its core characteristics
2. **For EACH distinct previous test failure**:
   - Read and extract its core characteristics
   - Compare with the current failure
   - Note any similarities in error type, location, or root cause
3. **Make final determination**: Is the current failure novel compared to ALL previous distinct failures?

# IMPORTANT CONSIDERATIONS:
- **Conservative approach**: Only re-run research when truly novel - research is expensive
- **Focus on root causes**: Look beyond superficial differences to underlying failure modes
- **Pattern matching**: Consider whether the current failure fits patterns already seen
- **Research efficiency**: Avoid redundant research on similar failure modes

# RESPONSE FORMAT:
Provide your analysis including:
1. **Current failure summary**: Brief description of the current test failure
2. **Comparison with each previous distinct failure**: Note similarities/differences  
3. **Novelty assessment**: Is this failure fundamentally different from ALL previous?
4. **Final decision**: End with exactly one of:
   - "MEANINGFUL_CHANGE: YES" (novel failure - run research agents)
   - "MEANINGFUL_CHANGE: NO" (similar to previous - skip research agents)

If you determine MEANINGFUL_CHANGE: YES, the current test output will be added to the distinct test outputs list."""

    return prompt


def build_context_prompt(state: FixTestsState) -> str:
    """Build the prompt for the planner agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    base_prompt = f"You are a planner agent (iteration {iteration}). Your goal is to analyze the research findings and create a comprehensive todo list for the editor agent to fix the test failures."

    prompt = f"""{base_prompt}

# INSTRUCTIONS:
- Review the plan.md file thoroughly for insights on what approaches have been tried and what to do next.
- Create todo items that instruct the editor agent to make actual fixes to underlying issues.
- Focus on analysis and proper code modifications.
- Address bugs, API changes, implementation issues, or infrastructure problems.
- Avoid simple workarounds - aim for genuine fixes that resolve the test failures.
- Use insights from the research.md file to inform your planning decisions.
- Learn from previous planning attempts documented in plan.md to avoid repeating ineffective approaches.

# editor_todos.md FILE INSTRUCTIONS:
- You MUST always create an editor_todos.md file - there is no option to skip this step.
- Focus on creating actionable, specific todo items that will guide the editor agent to fix the test.
- NEVER recommend that editor agents run test commands - the workflow handles all test execution automatically.
- Each todo item must be completely self-contained with full context.
- Create a systematic approach that addresses root causes while also making incremental progress.
- Cite relevant findings from research.md where applicable.

# NOTES ABOUT THE EDITOR AGENT:
- The editor agent can ONLY see the todo list you create.
- You MUST include ALL necessary context and instructions directly in the todo list.
- Do NOT reference previous agent responses or assume the editor knows what was tried before.

# AVAILABLE CONTEXT FILES:
@{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output).
@{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output).
@{artifacts_dir}/test_output.txt - Current test failure output.
@{artifacts_dir}/research.md - Current research findings from research agents.
@{artifacts_dir}/plan.md - Previous planning attempts and approaches (REVIEW THIS THOROUGHLY).
{collect_all_research_md_files(artifacts_dir, iteration)}
# IMPORTANT CONTEXT FOR ANALYSIS:
- Remember that updating non-test code is EXPECTED and appropriate when it fixes test failures.
- Editor agents should modify ANY code necessary (production code, config, dependencies, etc.) to make tests pass.
- UNACCEPTABLE changes: Removing new fields/features the CL adds just to make tests pass.
- ACCEPTABLE changes: Bug fixes, API updates, implementation changes, infrastructure fixes.

# COMMON TEST FAILURE PATTERNS:
- NEW TESTS that never passed: Often test framework, setup, or dependency issues.
- EXISTING TESTS broken by CL: Usually legitimate bugs that need fixing in the code.
- UPSTREAM INFRASTRUCTURE failures: Need to be tracked down and resolved at the root cause.
- Tests expecting old behavior: May need test updates if new behavior is correct.

# YOUR TASK:
1. ANALYSIS AND PLANNING:
   - Analyze the latest test failure and editor attempt.
   - Review the research.md file for insights from the research agents.
   - Use available context files to understand the current state.

2. TODO LIST CREATION:
   - Create a comprehensive todo list: @{artifacts_dir}/editor_todos.md.
   - Include ONLY specific code changes that need to be made (no investigation or analysis tasks).
   - Each todo should specify exactly what code change to make and in which file.
   - Order tasks logically - verification agent will handle syntax validation.
   - Incorporate insights from research.md where applicable.

## editor_todos.md FILE FORMAT:
Create @{artifacts_dir}/editor_todos.md with the following structure:
- [ ] [specific code change needed in file X]
- [ ] [specific fix to apply in file Y]
- [ ] [specific modification to implement in file Z]

## IMPORTANT:
- Include ONLY concrete code changes that need to be made.
- Do NOT include investigation, analysis, or research tasks.
- Do NOT include validation tasks - the verification agent handles syntax checking.
- Each todo should specify exactly what code change to make and in which file.
- The research agents have already done all investigation - you just need to plan implementation.
- Each todo must be COMPLETELY SELF-CONTAINED with full context.
- Include file paths, line numbers, exact code snippets, and detailed explanations in each todo item.
- Do NOT assume the editor knows anything about previous attempts or failures
- Focus on todos that make actual fixes to the underlying issues.
- Address root causes rather than symptoms.
- Make comprehensive fixes that resolve the test failures properly.
- Do NOT EVER suggest that an editor agent modify a BUILD file. You MAY ask the
  editor agent to run the `build_cleaner` command, if you think it would help,
  or any commands that the test failure output suggests to fix dependencies via
  a todo in the editor_todos.md file.
- Do NOT EVER include an absolute file path in a todo! ALWAYS use relative file paths!
- Cite specific findings from research.md when creating todos.
- Do NOT EVER ask an editor agent to investigate / research anything! That is
  your job! There should be ZERO ambiguity with regards to what edits need to
  be made in which files and/or which commands the editor need to be run!

## RESPONSE FORMAT:
Provide a summary of:
1. Key insights from research.md that inform your approach.
2. Analysis of the current test failure state.
3. The approach taken in the new editor_todos.md file."""

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

# ADDITIONAL INSTRUCTIONS:
{user_instructions_content}"""

    return prompt
