import os

from .state import (
    FixTestsState,
    collect_all_research_md_files,
    collect_editor_todos_files,
)


def build_editor_prompt(state: FixTestsState) -> str:
    """Build the prompt for the editor/fixer agent."""
    artifacts_dir = state["artifacts_dir"]
    prompt = f"""You are an expert file-editing agent. Your goal is to follow the todo list precisely
to edit the specified files EXACTLY as specified.

# INSTRUCTIONS:
- You MUST follow the todo list in {artifacts_dir}/editor_todos.md EXACTLY as specified.
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
{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output)
{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output)
{artifacts_dir}/test_output.txt - Current test failure output"""

    # Add conditionally available files
    orig_test_output = os.path.join(artifacts_dir, "orig_test_output.txt")
    if os.path.exists(orig_test_output):
        prompt += f"""
{artifacts_dir}/orig_test_output.txt - Original test failure output"""

    orig_cl_changes = os.path.join(artifacts_dir, "orig_cl_changes.diff")
    if os.path.exists(orig_cl_changes):
        prompt += f"""
{artifacts_dir}/orig_cl_changes.diff - Original CL changes"""

    # Add previous iteration context
    prompt += """

# PREVIOUS ITERATION CONTEXT:
Review all previous iterations to understand what has been tried:"""

    for prev_iter in range(1, iteration):
        prompt += f"""
- {artifacts_dir}/research_iter_{prev_iter}_response.txt - Previous research analysis
- {artifacts_dir}/editor_iter_{prev_iter}_response.txt - Previous editor attempt  
- {artifacts_dir}/editor_iter_{prev_iter}_changes.diff - Previous code changes
- {artifacts_dir}/editor_iter_{prev_iter}_test_output.txt - Previous test results
- {artifacts_dir}/editor_iter_{prev_iter}_todos.txt - Previous todo list"""

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


def build_judge_prompt(state: FixTestsState) -> str:
    """Build the prompt for the judge agent that selects the best plan."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]
    research_plans = state["research_agent_plans"]

    prompt = f"""You are a judge agent (iteration {iteration}). Your goal is to evaluate multiple research plans from different agents and select the plan most likely to make progress toward fixing the test failure.

# AVAILABLE RESEARCH PLANS:
You have {len(research_plans)} research plans to evaluate:"""

    # Add information about each plan
    for i, plan_path in enumerate(research_plans, 1):
        agent_id = (
            plan_path.split("_agent_")[1].split(".md")[0]
            if "_agent_" in plan_path
            else str(i)
        )
        prompt += f"""

## PLAN {agent_id} ({plan_path}):
- File path: {plan_path}
- Generated by research agent with focus on: {'ROOT CAUSE analysis' if agent_id == '1' else 'SYSTEMATIC fixes' if agent_id == '2' else 'QUICK wins and INCREMENTAL progress'}"""

    # Add context files available for judgment
    prompt += f"""

# CONTEXT FILES FOR JUDGMENT:
- {artifacts_dir}/cl_desc.txt - Current CL description.
- {artifacts_dir}/test_output.txt - Current test failure output.
- {artifacts_dir}/cl_changes.diff - Current CL changes."""

    # Conditionally include original files if they exist, otherwise use current files
    orig_test_output = os.path.join(artifacts_dir, "orig_test_output.txt")
    orig_cl_changes = os.path.join(artifacts_dir, "orig_cl_changes.diff")

    if os.path.exists(orig_test_output):
        prompt += f"""
- {artifacts_dir}/orig_test_output.txt - Original test failure output"""

    if os.path.exists(orig_cl_changes):
        prompt += f"""
- {artifacts_dir}/orig_cl_changes.diff - Original CL changes."""

    prompt += """

# PREVIOUS ITERATION CONTEXT:
Review all previous editor todo files and agent responses to understand what has been tried:"""

    # Add information about previous iterations
    for prev_iter in range(1, iteration):
        prompt += f"""
- {artifacts_dir}/research_iter_{prev_iter}_response.txt - Previous research analysis
- {artifacts_dir}/editor_iter_{prev_iter}_response.txt - Previous editor attempt  
- {artifacts_dir}/editor_iter_{prev_iter}_changes.diff - Previous code changes
- {artifacts_dir}/editor_iter_{prev_iter}_test_output.txt - Previous test results
- {artifacts_dir}/editor_iter_{prev_iter}_todos.txt - Previous todo list"""

    prompt += """

# JUDGMENT CRITERIA:
Evaluate each plan based on:

1. **FEASIBILITY**: Can this plan realistically be implemented by the editor agent?
2. **PROGRESS POTENTIAL**: Is this plan likely to move us closer to a working test?
3. **NOVELTY**: Does this plan try something different from previous failed attempts?
4. **COMPLETENESS**: Does this plan address the right issues based on the test failure?
5. **ACTIONABILITY**: Are the todo items specific and clear enough for the editor agent?

# SELECTION FACTORS:
- Consider what has already been tried in previous iterations.
- Favor plans that address root causes over symptoms.
- Consider the complexity vs. likelihood of success.
- Look for plans that build on previous progress rather than starting over.
- Prefer plans with clear, specific, actionable steps.

# RESPONSE FORMAT:
1. Provide a brief analysis of each plan (2-3 sentences per plan)
2. Compare the plans against the judgment criteria
3. Explain your reasoning for the selection
4. End your response with: "SELECTED PLAN: [agent_number]" (e.g., "SELECTED PLAN: 2")

# IMPORTANT:
- You MUST select exactly one plan.
- Your selection should be based on objective analysis, not randomness.
- Consider both immediate progress and long-term viability.
- Focus on plans most likely to succeed given the current context.
"""

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
    iteration = state["current_iteration"]
    prompt = f"""You are a verification agent. Your goal is to ensure basic quality: no syntax errors and that the
editor agent made a reasonable attempt at each todo item.

# CRITICAL - Only reject changes for these SERIOUS issues:
1. SYNTAX ERRORS: Code that breaks compilation/parsing (obvious syntax issues visible in diff).
2. COMPLETELY MISSED TODOS: Editor agent didn't even attempt a todo item (and didn't report todo issues).
3. NO CHANGES MADE: Editor agent made no code changes at all (empty diff file) and didn't report todo issues.

# DO NOT reject for:
- Imperfect implementations (as long as some attempt was made).
- Different approaches than you would take.
- Minor style issues or missing edge cases.
- Incomplete solutions (partial progress is acceptable).

# AVAILABLE FILES TO REVIEW:
{artifacts_dir}/editor_todos.md - The todo list the editor was supposed to follow.
{artifacts_dir}/agent_reply.md - The editor agent's response about what they did.
{artifacts_dir}/editor_iter_{iteration}_changes.diff - The actual code changes made by the editor.

# VERIFICATION PROCESS:
1. First, check if editor agent reported problems with the todos themselves - if so, FIX THE TODOS and FAIL (so editor retries with improved todos).
2. Check if diff file is empty - FAIL if no changes were made and no todo issues reported.
3. Visually inspect code changes for obvious syntax errors - FAIL if any found.
4. Check each todo item was attempted (not necessarily perfectly) - FAIL if completely ignored without explanation.
5. If all pass, always PASS regardless of implementation quality.

# YOUR RESPONSE MUST END WITH:
- "VERIFICATION: PASS" if changes were made AND no syntax errors AND all todos were attempted.
- "VERIFICATION: FAIL" if todos were fixed OR no changes made OR syntax errors exist OR any todos were completely ignored.

# COMMIT MESSAGE GENERATION:
If verification passes, provide a short descriptive message (5-10 words) summarizing the main change made. This will be used in the commit message. Include it in your response as:
"COMMIT_MSG: <your descriptive message>"

Examples:
- "COMMIT_MSG: Fix import paths and module references"
- "COMMIT_MSG: Update test setup and configuration"
- "COMMIT_MSG: Resolve API compatibility issues"

BE LENIENT: If the editor made any reasonable attempt at a todo, count it as attempted. If editor reports todo problems, fix the todos and then FAIL so the editor can retry with improved instructions.
"""

    return prompt


def build_synthesis_prompt(state: FixTestsState) -> str:
    """Build the prompt for the synthesis agent that consolidates research findings."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    prompt = f"""You are a synthesis agent (iteration {iteration}). Your goal is to analyze and consolidate the raw research findings from multiple research agents, preserving valuable information while filtering out misleading or unhelpful content.

# YOUR TASK:
Your job is to create a high-quality research.md file that will guide planner agents effectively. You must:

1. **PRESERVE VALUABLE INSIGHTS**: Identify and retain information that will genuinely help planner agents understand the problem and create effective solutions.

2. **FILTER OUT BAD INFORMATION**: Remove or correct information that could mislead planner agents, including:
   - Contradictory findings between agents
   - Speculative conclusions without evidence
   - Information that doesn't relate to the current test failure
   - Overly complex solutions that are unlikely to work
   - Misleading interpretations of error messages or code

3. **SYNTHESIZE FINDINGS**: Don't just concatenate - actively synthesize the research to create coherent, actionable insights.

4. **PRIORITIZE ACTIONABILITY**: Focus on findings that can be turned into concrete todo items by planner agents.

# AVAILABLE RAW RESEARCH:
{artifacts_dir}/raw_research_iter_{iteration}.md - Raw findings from all four research agents

# CONTEXT FILES:
{artifacts_dir}/cl_desc.txt - Current CL description
{artifacts_dir}/test_output.txt - Current test failure output
{artifacts_dir}/cl_changes.diff - Current CL changes"""

    # Add previous research.md files for context
    all_research_files = collect_all_research_md_files(artifacts_dir, iteration)
    if all_research_files:
        prompt += f"""

# PREVIOUS RESEARCH FINDINGS:
Review previous research findings to understand what has been learned about different test failure states:
{all_research_files}"""

    prompt += f"""

# INSTRUCTIONS:
1. **READ ALL RAW RESEARCH**: Carefully review the raw research findings from all four research agents (CL scope, similar tests, test failure analysis, and prior work analysis).

2. **IDENTIFY KEY INSIGHTS**: Extract the most valuable insights that will help planner agents understand:
   - Root causes of the test failure
   - Concrete steps needed to fix the issue
   - Relevant code patterns and examples
   - Potential pitfalls to avoid

3. **RESOLVE CONFLICTS**: When research agents provide conflicting information, use your judgment to determine which findings are most credible and useful.

4. **CREATE ACTIONABLE SYNTHESIS**: Organize findings into a structure that planner agents can easily use to create todo lists.

5. **WRITE research.md**: Create {artifacts_dir}/research.md with your synthesized findings.

# research.md FILE STRUCTURE:
Create a well-organized research.md file with these sections:

## EXECUTIVE SUMMARY
- Brief overview of the test failure and key insights
- High-level approach recommended for fixing the issue

## ROOT CAUSE ANALYSIS
- Confirmed or highly probable root causes
- Evidence supporting these conclusions

## ACTIONABLE INSIGHTS
- Specific code changes that need to be made
- Files and functions that need attention
- Configuration or setup issues to address

## CODE PATTERNS AND EXAMPLES
- Relevant examples from the codebase
- Successful patterns that should be followed
- Anti-patterns to avoid

## PRIOR WORK CONSIDERATIONS
- Issues with previous implementations that need correction
- Lessons learned from earlier attempts

## RECOMMENDATIONS FOR PLANNER AGENTS
- Prioritized list of approaches to try
- Specific guidance for creating effective todo lists

# QUALITY STANDARDS:
- Be specific and concrete - avoid vague generalizations
- Include file paths, function names, and specific error messages
- Prioritize information that leads to actionable todo items
- Eliminate speculation and focus on evidence-based conclusions
- Ensure recommendations are realistic and implementable

Your synthesized research.md file will be the primary resource that planner agents use to create todo lists, so make it as helpful and accurate as possible."""

    return prompt


def build_test_failure_comparison_prompt(state: FixTestsState) -> str:
    """Build the prompt for the test failure comparison agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]
    # Use current_iteration - 1 for editor files since iteration gets incremented by judge/context agents
    editor_iteration = iteration - 1

    prompt = f"""You are a test failure comparison agent (iteration {iteration}). Your goal is to compare the current test failure output with the previous test failure output and determine whether the test failure has meaningfully changed.

# YOUR TASK:
Analyze whether the test failure has changed in a way that would require re-running research agents to understand the new failure mode.

# AVAILABLE FILES:
{artifacts_dir}/test_output.txt - Current test failure output
{artifacts_dir}/editor_iter_{editor_iteration}_test_output.txt - Previous test failure output (after last editor attempt)

# COMPARISON CRITERIA:
Consider the change MEANINGFUL if:
1. **Different error messages**: The core error message or exception type has changed
2. **Different failure location**: The test is failing at a different point in the code
3. **New error types**: Previously unseen error types or stack traces appear
4. **Different root cause**: The underlying cause of the failure appears to be different
5. **Progression/regression**: The test has moved from one type of failure to another

Consider the change NOT MEANINGFUL if:
1. **Same error with minor variations**: The core error is the same with only minor text differences
2. **Line number changes**: Same error but line numbers shifted due to code changes
3. **Formatting differences**: Same content but different formatting or whitespace
4. **Verbose vs. terse output**: Same information with different levels of detail
5. **Irrelevant details**: Changes to timestamps, process IDs, or other non-functional details

# ANALYSIS APPROACH:
1. **Extract core error information** from both test outputs
2. **Identify the primary failure mode** in each case
3. **Compare the essential failure characteristics**
4. **Determine if the failure represents a fundamentally different problem**

# IMPORTANT CONSIDERATIONS:
- Focus on whether the CAUSE of the failure has changed, not just the symptoms
- Consider whether different research would be needed to understand the new failure
- Err on the side of caution - if uncertain, consider it meaningful
- Look beyond superficial differences to understand the underlying failure mode

# RESPONSE FORMAT:
Provide your analysis and end with one of:
- "MEANINGFUL_CHANGE: YES" (research agents should be re-run)
- "MEANINGFUL_CHANGE: NO" (skip research agents, use existing research)

Include your reasoning for the decision, comparing specific aspects of the two test failures."""

    return prompt


def build_context_prompt(state: FixTestsState, agent_variation: int = 1) -> str:
    """Build the prompt for the planner agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    # Add variation prompts for different agent perspectives
    variation_prompts = {
        1: "You are a planner agent focusing on ROOT CAUSE analysis (iteration {iteration}, agent {agent_variation}). Your goal is to identify the fundamental underlying issues causing test failures and create a comprehensive todo list for the next editor agent.",
        2: "You are a planner agent focusing on SYSTEMATIC fixes (iteration {iteration}, agent {agent_variation}). Your goal is to create a methodical, step-by-step approach to fixing test failures with a comprehensive todo list for the next editor agent.",
        3: "You are a planner agent focusing on QUICK wins and INCREMENTAL progress (iteration {iteration}, agent {agent_variation}). Your goal is to identify the most straightforward fixes that can make immediate progress toward fixing test failures.",
    }

    base_prompt = variation_prompts.get(agent_variation, variation_prompts[1]).format(
        iteration=iteration, agent_variation=agent_variation
    )

    prompt = f"""{base_prompt}

# INSTRUCTIONS:
- Create todo items that instruct the editor agent to make actual fixes to underlying issues.
- Focus on analysis and proper code modifications.
- Address bugs, API changes, implementation issues, or infrastructure problems.
- Avoid simple workarounds - aim for genuine fixes that resolve the test failures.
- Use insights from the research.md file to inform your planning decisions.

# editor_todos.md FILE INSTRUCTIONS:
- You MUST always create an editor_todos.md file - there is no option to skip this step.
- Focus on creating actionable, specific todo items that will guide the editor agent to fix the test.
- NEVER recommend that editor agents run test commands - the workflow handles all test execution automatically.
- Each todo item must be completely self-contained with full context.
- Your approach should reflect your agent variation focus (root cause, systematic, or quick wins).
- Cite relevant findings from research.md where applicable.

# NOTES ABOUT THE EDITOR AGENT:
- The editor agent can ONLY see the todo list you create.
- You MUST include ALL necessary context and instructions directly in the todo list.
- Do NOT reference previous agent responses or assume the editor knows what was tried before.

# AVAILABLE CONTEXT FILES:
{artifacts_dir}/cl_changes.diff - Current CL changes (branch_diff output).
{artifacts_dir}/cl_desc.txt - Current CL description (hdesc output).
{artifacts_dir}/test_output.txt - Current test failure output.
{artifacts_dir}/research.md - Current research findings from research agents.
{collect_editor_todos_files(artifacts_dir, iteration)}{collect_all_research_md_files(artifacts_dir, iteration)}
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
   - Create a comprehensive todo list: {artifacts_dir}/editor_todos.md.
   - Include ONLY specific code changes that need to be made (no investigation or analysis tasks).
   - Each todo should specify exactly what code change to make and in which file.
   - Order tasks logically - verification agent will handle syntax validation.
   - Incorporate insights from research.md where applicable.

## editor_todos.md FILE FORMAT:
Create {artifacts_dir}/editor_todos.md with the following structure:
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
