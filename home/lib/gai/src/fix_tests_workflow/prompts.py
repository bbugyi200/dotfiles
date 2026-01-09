import os

from .state import (
    FixTestsState,
    extract_file_modifications_from_response,
    get_latest_planner_response,
)


def build_editor_prompt(state: FixTestsState) -> str:
    """Build the prompt for the editor/fixer agent."""
    verifier_notes = state.get("verifier_notes", [])

    # Get the planner response which contains the + bullets
    planner_response = get_latest_planner_response(state)
    file_modifications = extract_file_modifications_from_response(planner_response)

    # Handle case where no modifications are found
    if not file_modifications:
        file_modifications = "ERROR: No structured file modifications found in planner response. Please check the planner agent output."

    prompt = f"""You are an expert file-editing agent. Your goal is to process the structured file modifications
and make the specified file changes EXACTLY as requested.

# FILE MODIFICATIONS TO PROCESS:
{file_modifications}

# INSTRUCTIONS:
- You MUST follow the file modifications above EXACTLY as specified.
- The modifications use a structured format with + bullets for files and - sub-bullets for changes.
- For each + bullet, process all its - sub-bullets in the exact sequence provided.
- You should make code changes to fix the failing test, but do NOT run the test command yourself.
- Do NOT run any validation commands like `hg fix` - the verification agent will handle syntax checking.
- You MAY run a command to edit one or more files ONLY IF running this command
  is explicitly requested in a sub-bullet item."""

    # Add verifier notes if any exist
    if verifier_notes:
        prompt += """

# IMPORTANT NOTES FROM PREVIOUS VERIFICATIONS:
Previous verification agents have provided the following guidance to help you succeed:
"""
        for i, note in enumerate(verifier_notes, 1):
            prompt += f"  {i}. {note}\n"

        prompt += "\nPlease keep these notes in mind while completing your tasks."

    prompt += """

# STRUCTURED OUTPUT FORMAT:
Your response MUST follow this exact format:

## Files Processed

For each + bullet from the file modifications above, output:

+ <PATH> (copy the exact file path from the modifications)
  - [description of change made for first sub-bullet]
  - [description of change made for second sub-bullet]
  - [etc for all sub-bullets processed]

## Summary
- Brief summary of all changes made across all files."""

    return prompt


def build_research_prompt(state: FixTestsState, research_focus: str) -> str:
    """Build the prompt for research agents with different focus areas."""
    artifacts_dir = state["artifacts_dir"]
    local_artifacts: dict[str, str] = state.get("local_artifacts", {})
    iteration = state["current_iteration"]

    focus_prompts = {
        "cl_scope": f"""You are a research agent focusing on CL SCOPE analysis (iteration {iteration}). Your goal is to perform deep research on non-test files to understand the scope and impact of the current change list (CL) being worked on.

# YOUR RESEARCH FOCUS:
- Analyze the CL changes to understand what new functionality or modifications are being introduced.
- Research the codebase to understand how the changed code fits into the larger system.
- Identify dependencies, related components, and potential impact areas.
- Look for patterns in how similar functionality is implemented elsewhere in the codebase.
- Understand the business logic and technical architecture around the changes.""",
        "similar_tests": f"""You are a research agent focusing on SIMILAR TESTS analysis (iteration {iteration}). Your goal is to perform deep research on test files to find examples and patterns that could inspire solutions for fixing the failing test(s).

# YOUR RESEARCH FOCUS:
- Find other test files that test similar functionality to what's failing.
- Look for test patterns, setup methods, and assertion styles that could be applicable.
- Research how similar test failures have been resolved in the codebase.
- Identify test utilities, helpers, or frameworks that might be useful.
- Look for examples of tests that cover edge cases or complex scenarios similar to the failing test.""",
        "test_failure": f"""You are a research agent focusing on TEST FAILURE analysis (iteration {iteration}). Your goal is to perform deep research specifically on the test failure itself to understand root causes and potential solutions.

# YOUR RESEARCH FOCUS:
- Analyze the specific error messages and stack traces in detail.
- Research the failing test code to understand what it's trying to accomplish.
- Look up documentation, comments, or related code that explains the expected behavior.
- Research error patterns and common causes for this type of failure.
- Investigate recent changes or issues that might have introduced this failure.""",
        "prior_work_analysis": f"""You are a research agent focusing on PRIOR WORK ANALYSIS (iteration {iteration}). Your goal is to investigate whether previous work related to this project may have been incorrect and identify potential issues with prior implementations.

# YOUR RESEARCH FOCUS:
- Research the git/hg history to understand what changes were made in prior CLs related to this project.
- Analyze whether previous implementations or fixes may have been flawed or incomplete.
- Look for patterns of repeated fixes or reverts that suggest underlying issues.
- Investigate if current test failures are related to incorrect assumptions made in previous work.
- Examine code comments, TODOs, or issue tracking that might indicate known problems with prior work.
- Research whether the current approach conflicts with or contradicts previous design decisions.
- Identify areas where prior work may need to be reconsidered or corrected.""",
        "cl_analysis": f"""You are a research agent focusing on PREVIOUS CL ANALYSIS (iteration {iteration}). Your goal is to analyze previous change lists (CLs) submitted by the author to understand patterns, implementations, and solutions that might help fix the current test failure.

# YOUR RESEARCH FOCUS:
- Analyze the provided clsurf output to understand all previous CLs submitted by the author for this project.
- Select the most interesting and relevant files that were changed in those CLs with regards to fixing the current test.
- Deep dive into those files to understand implementation patterns, coding styles, and solution approaches.
- Look for similar problems that were solved in previous CLs and how they were addressed.
- Identify reusable patterns, utilities, or approaches from previous work.
- Research dependencies, configurations, or infrastructure changes made in previous CLs.
- Look for clues about the intended architecture and design decisions from previous work.""",
    }

    base_prompt = focus_prompts.get(research_focus, focus_prompts["test_failure"])
    prompt = f"""{base_prompt}

# RESEARCH INSTRUCTIONS:
- Use your code search tools extensively to perform deep research.
- Look beyond the immediate files - explore the broader codebase.
- Search for relevant patterns, examples, and documentation.
- Document your findings clearly and thoroughly.
- Focus on actionable insights that will help the planner agents.

# AVAILABLE CONTEXT FILES:
@{artifacts_dir}/log.md - Complete workflow history with all previous iterations, research findings, planning attempts, and test outputs.
#cl"""

    # Add clsurf output for cl_analysis research focus
    if research_focus == "cl_analysis":
        clsurf_output_local = local_artifacts.get("clsurf_output_txt")
        if clsurf_output_local:
            prompt += f"""
@{clsurf_output_local} - Previous CLs submitted by author (clsurf output)"""

    # Add previous iteration context
    prompt += """

# PREVIOUS ITERATION CONTEXT:
Review log.md to understand what has been tried in all previous iterations. The log.md file contains:
- All previous research findings organized by iteration
- All previous planning attempts and todo lists  
- All previous test outputs and whether they represented meaningful changes
- Any postmortem analyses from iterations that didn't make progress"""

    prompt += f"""

# YOUR TASK:
1. **DEEP CODE RESEARCH**: Use your code search tools to thoroughly investigate your focus area.
2. **PATTERN IDENTIFICATION**: Look for patterns, examples, and best practices relevant to your focus.
3. **INSIGHT GENERATION**: Generate actionable insights that will help planner agents create better todos.
4. **DOCUMENTATION**: Document your findings clearly with specific examples and references.

# RESPONSE FORMAT:
CRITICAL: You MUST structure your response with a "### Research" section. ONLY the content in the "### Research" section will be stored to log.md. Everything outside this section will be discarded.

You may include explanatory text before the ### Research section, but the actual research findings must be in the ### Research section.

### Research

[Put all your research findings here. Structure them as follows:]

#### RESEARCH METHODOLOGY
- Describe your search strategy and approach.
- List the key search terms and patterns you investigated.

#### KEY FINDINGS
- Document your most important discoveries
- Include specific file paths, code examples, and references.
- Explain how each finding relates to the test failure.

#### ACTIONABLE INSIGHTS
- Provide specific insights that planner agents can use.
- Suggest concrete approaches or solutions based on your research.
- Highlight patterns or examples that could be applied.

#### RECOMMENDATIONS
- Specific recommendations for how to approach fixing the test failure.
- Priority ranking of different approaches based on your research.
- Potential pitfalls or considerations to keep in mind.

# IMPORTANT NOTES:
- Focus on your specific research area ({research_focus.replace("_", " ")}).
- Use code search tools extensively - don't just rely on provided context files.
- Look for concrete examples and patterns in the codebase.
- Document specific file paths and code snippets in your findings.
- Your research will be aggregated with other research agents' findings.
- Do NOT make AnY code changes or attempt to run the tests yourself - your role is purely research-focused."""

    # Add user instructions if available
    user_instructions_content = ""
    user_instructions_file = state.get("user_instructions_file")
    if user_instructions_file and os.path.exists(user_instructions_file):
        try:
            with open(user_instructions_file) as f:
                user_instructions_content = f.read().strip()
        except Exception as e:
            print(f"Warning: Could not read user instructions file: {e}")

    if user_instructions_content:
        prompt += f"""

# ADDITIONAL INSTRUCTIONS:
{user_instructions_content}"""

    return prompt


def build_synthesis_research_prompt(
    state: FixTestsState, research_results: dict
) -> str:
    """Build the prompt for the synthesis research agent that aggregates all research findings."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    # Build list of research agent file paths
    research_file_paths = []
    for focus, result in research_results.items():
        research_file_path = os.path.join(
            artifacts_dir, f"research_{focus}_iter_{iteration}_response.txt"
        )
        if os.path.exists(research_file_path):
            research_file_paths.append((focus, result["title"], research_file_path))

    prompt = f"""You are a synthesis research agent (iteration {iteration}). Your goal is to analyze, synthesize, de-duplicate, verify, and enhance the research findings from all the specialized research agents.

# YOUR TASK:
You will receive research findings from multiple specialized research agents, each focusing on different aspects:
- CL Scope Analysis
- Similar Tests Analysis
- Test Failure Analysis
- Prior Work Analysis
- Previous CL Analysis (if applicable)

Your job is to:
1. **SYNTHESIZE**: Combine insights from all research agents into a coherent understanding
2. **DE-DUPLICATE**: Identify and remove redundant information across different research findings
3. **VERIFY**: Cross-check findings for consistency and accuracy
4. **ENHANCE**: Add additional research or insights where you identify gaps
5. **PRIORITIZE**: Rank the most important insights for the planner agent

# CRITICAL REQUIREMENT - PRESERVE ALL INFORMATION:
**DO NOT LEAVE OUT ANY INFORMATION** from the other research agents unless it is truly redundant (i.e., the exact same information appears multiple times). Your role is to:
- **INCLUDE** all unique findings, insights, and recommendations from all research agents
- **ORGANIZE** the information in a coherent structure
- **ADD TO** the findings with your own additional research and insights
- **VERIFY** the accuracy of the findings through cross-checking
- **DE-DUPLICATE** only information that is genuinely repeated across agents

You are NOT allowed to:
- Exclude information simply because you think it's less important
- Omit findings that don't fit your preferred narrative
- Remove insights that contradict each other (instead, present both and analyze the contradiction)
- Skip over details that seem minor (they may be crucial for the planner)

# RESEARCH FINDINGS FROM SPECIALIZED AGENTS:"""

    # Add file paths for each research agent's output
    for focus, title, file_path in research_file_paths:
        prompt += f"""
@{file_path} - {title}"""

    prompt += f"""

# AVAILABLE CONTEXT FILES:
@{artifacts_dir}/log.md - Complete workflow history with all previous iterations, research findings, planning attempts, and test outputs.
#cl

# YOUR SYNTHESIS TASK:
1. **CROSS-REFERENCE**: Look for connections and contradictions between different research findings
2. **FILL GAPS**: Identify areas where more research might be needed and perform additional code searches
3. **CONSOLIDATE**: Merge similar insights from different agents into unified recommendations (while preserving ALL unique information)
4. **VERIFY CLAIMS**: Double-check key findings using code search tools
5. **PRIORITIZE**: Rank insights by importance and likelihood of solving the test failure (but include ALL insights, not just high-priority ones)

# RESPONSE FORMAT:
CRITICAL: You MUST structure your response with a "### Research" section. ONLY the content in the "### Research" section will be stored to log.md. Everything outside this section will be discarded.

You may include explanatory text before the ### Research section, but the actual synthesized research must be in the ### Research section.

### Research

[Put all your synthesized research here. Structure it as follows:]

#### SYNTHESIS OVERVIEW
- High-level summary of all research findings
- Key themes and patterns identified across all research
- Overall assessment of what's causing the test failure

#### CONSOLIDATED FINDINGS
- Merged and de-duplicated findings organized by importance
- Include specific file paths, code examples, and references
- Cross-references between different research areas

#### VERIFIED INSIGHTS
- Insights you've verified through additional code searches
- Corrections to any inconsistencies found in the research
- Additional discoveries made during synthesis

#### GAP ANALYSIS
- Areas where research was incomplete or contradictory
- Additional research performed to fill those gaps
- Remaining unknowns or uncertainties

#### PRIORITIZED RECOMMENDATIONS
1. **Top Priority**: Most likely solutions based on synthesized research
2. **Medium Priority**: Alternative approaches worth considering
3. **Lower Priority**: Long-shot solutions or edge cases

#### ACTION PLAN FOR PLANNER
- Specific, actionable recommendations for the planner agent
- Ordered list of approaches to try based on research confidence
- Key considerations and potential pitfalls to avoid

# IMPORTANT NOTES:
- **PRESERVE ALL INFORMATION**: Include all unique findings from all research agents - do not leave anything out
- Use code search tools to verify and enhance the research findings
- Look for patterns and connections that individual agents might have missed
- Resolve any contradictions between different research findings (by presenting both sides, not by choosing one)
- Focus on actionable insights that will help the planner create effective todos
- Your goal is to SYNTHESIZE and ADD TO the research, not to FILTER or REDUCE it
- Do NOT make any code changes or run tests - your role is synthesis and verification only"""

    # Add user instructions if available
    user_instructions_content = ""
    user_instructions_file = state.get("user_instructions_file")
    if user_instructions_file and os.path.exists(user_instructions_file):
        try:
            with open(user_instructions_file) as f:
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
editor agent made a reasonable attempt at each structured task.

# CRITICAL - Only reject changes for these SERIOUS issues:
1. SYNTAX ERRORS: Code that breaks compilation/parsing (obvious syntax issues visible in diff).
2. COMPLETELY MISSED FILES: Editor agent didn't attempt to process a + bullet file from the structured todos.
3. NO CHANGES MADE (Invalid): Editor agent made no code changes at all AND provided no valid explanation.
4. UNRELATED CHANGES: Editor agent made changes that are completely unrelated to any structured todo item and appear unnecessary.
5. INCORRECT OUTPUT FORMAT: Editor agent didn't follow the required structured output format in their response.

# SPECIAL CASE - Valid No Changes:
If the editor made NO CHANGES but provided a reasonable explanation that the requested changes were not needed (e.g., "the code is already correct", "the issue is elsewhere", "the requested change would break things"), then this should trigger a PLANNER RETRY instead of editor retry.

# DO NOT reject for:
- Imperfect implementations (as long as some attempt was made).
- Different approaches than you would take.
- Minor style issues or missing edge cases.
- Incomplete solutions (partial progress is acceptable).
- Related changes that support the structured todo items (even if not explicitly mentioned).

# AVAILABLE FILES TO REVIEW:
@{artifacts_dir}/agent_reply.md - The editor agent's response about what they did (should follow structured format with + bullets for files, - sub-bullets for changes).
@{artifacts_dir}/editor_iter_{editor_iteration}_changes.diff - The actual code changes made by the editor.

Note: The file modifications that the editor was supposed to follow come from the planner agent's response (with + bullets for files and - sub-bullets for changes), not from a separate file.

# VERIFICATION PROCESS:
- Check if diff file is empty:
  * If empty AND editor provided valid explanation for why changes weren't needed → PLANNER_RETRY
  * If empty AND no valid explanation → FAIL
- Visually inspect code changes for obvious syntax errors - FAIL if any found.
- Check that editor response follows structured format with + bullets and - sub-bullets.
- Check each + bullet file was attempted (not necessarily perfectly) - FAIL if completely ignored without explanation.
- Review all changes to ensure they relate to the structured todo items - FAIL if there are significant unrelated changes.
- If all pass, always PASS regardless of implementation quality.

# YOUR RESPONSE MUST END WITH:
- "VERIFICATION: PASS" if changes were made AND no syntax errors AND all todos were attempted AND no unrelated changes.
- "VERIFICATION: FAIL" if any serious issues exist (syntax errors, missed todos, invalid no changes, or unrelated changes).
- "VERIFICATION: PLANNER_RETRY" if no changes were made but editor provided valid explanation that changes weren't needed.

# COMMIT MESSAGE GENERATION:
If verification passes, provide a short descriptive message (5-10 words) summarizing the main change made. This will be used in the commit message. Include it in your response as:
"COMMIT_MSG: <your descriptive message>"

IMPORTANT: The commit message should NOT end with punctuation (no periods, exclamation marks, etc.)

Examples:
- "COMMIT_MSG: Fix import paths and module references"
- "COMMIT_MSG: Update test setup and configuration"
- "COMMIT_MSG: Resolve API compatibility issues"

# VERIFIER NOTE GENERATION:
If verification fails, provide a brief note (1-3 sentences) to help the next editor agent avoid the same issues. Keep in
mind that the last editor's changes will be cleared before the next editor agent runs. Include it in your response as:
"VERIFIER_NOTE: <your helpful note>"

Examples:
- "VERIFIER_NOTE: Make sure to double-check that you didn't make any syntax errors after editing files."
- "VERIFIER_NOTE: Focus only on changes that directly address the todo items - avoid unrelated modifications."
- "VERIFIER_NOTE: Ensure all todo items are addressed, even if only partially - don't skip any completely."

# PLANNER RETRY NOTE GENERATION:
If verification results in PLANNER_RETRY, provide a note (1-3 sentences) explaining why the planner's approach was incorrect and what the planner should consider instead. Include it in your response as:
"PLANNER_RETRY_NOTE: <your note for the planner>"

Examples:
- "PLANNER_RETRY_NOTE: The editor correctly identified that the requested changes are not needed because the code is already correct. The test failure may be due to a different issue."
- "PLANNER_RETRY_NOTE: The editor found that the requested changes would break existing functionality. Consider a different approach to fix the test failure."
- "PLANNER_RETRY_NOTE: The editor determined the issue is in a different file than what was specified in the todos. Re-analyze the test failure to identify the correct location."

BE LENIENT: If the editor made any reasonable attempt at a todo, count it as attempted.
"""

    return prompt


def build_test_failure_comparison_prompt(state: FixTestsState) -> str:
    """Build the prompt for the test failure comparison agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]

    # Check if new_test_output.txt should be embedded or referenced
    new_test_output_file = os.path.join(artifacts_dir, "new_test_output.txt")
    test_output_ref = ""
    try:
        with open(new_test_output_file) as f:
            lines = f.readlines()

        if len(lines) < 500:
            # Small file - embed the content
            content = "".join(lines)
            test_output_ref = f"""

## Current Test Output
```
{content}
```"""
        else:
            # Large file - use @ reference
            test_output_ref = f"@{artifacts_dir}/new_test_output.txt - Contains the current test output to be compared"
    except Exception:
        # Fallback to @ reference if we can't read the file
        test_output_ref = f"@{artifacts_dir}/new_test_output.txt - Contains the current test output to be compared"

    prompt = f"""You are a test failure comparison agent (iteration {iteration}). Your goal is to compare the current test failure output with ALL previous test failure outputs and determine whether the current failure is meaningfully different from any previous iteration.

# YOUR TASK:
Compare the new test output with EACH iteration's test output in tests.md and determine if the new test output represents a fundamentally different failure mode. Research agents should only be re-run when the failure is genuinely different from ALL previous iterations.

# AVAILABLE CONTEXT:
@{artifacts_dir}/tests.md - Contains test outputs from all previous iterations organized chronologically
{test_output_ref}

# COMPARISON STRATEGY:
1. **Review the current test failure** (provided above or in new_test_output.txt)
2. **Read tests.md** to review ALL previous test outputs from each iteration
3. **Compare the new test output against EACH previous iteration's test output**
4. **Determine if the new test output is meaningfully different from ALL previous iterations**

# MEANINGFUL CHANGE CRITERIA:
Consider the current failure MEANINGFUL (requiring research) if it has ALL of these characteristics compared to ALL previous iterations:
1. **Different error messages**: Core error message or exception type is different from all previous iterations
2. **Different failure location**: Test fails at a different point than all previous iterations
3. **Different error types**: Uses error types/stack traces not seen in any previous iteration
4. **Different root cause**: Underlying cause appears fundamentally different from all previous iterations
5. **New failure pattern**: Represents a failure pattern not captured by any previous iteration

Consider the current failure NOT MEANINGFUL (skip research) if it matches ANY previous iteration in:
1. **Same core error**: Essentially the same error with minor variations (line numbers, formatting, etc.)
2. **Same failure location**: Failing at the same logical point as a previous iteration
3. **Same error patterns**: Uses similar error types and patterns as a previous iteration
4. **Same root cause**: Underlying cause is the same as a previous iteration
5. **Covered failure mode**: Failure mode is already represented by a previous iteration

# ANALYSIS APPROACH:
1. **Analyze the current test output** and extract its core characteristics
2. **For EACH iteration in tests.md**:
   - Extract that iteration's test output characteristics
   - Compare with the new test output
   - Note any similarities in error type, location, or root cause
3. **Make final determination**: Is the new test output meaningfully different from ALL previous iterations?

# IMPORTANT CONSIDERATIONS:
- **Conservative approach**: Only re-run research when truly novel - research is expensive
- **Focus on root causes**: Look beyond superficial differences to underlying failure modes
- **Pattern matching**: Consider whether the current failure fits patterns already seen
- **Research efficiency**: Avoid redundant research on similar failure modes

# RESPONSE FORMAT:
Provide your analysis including:
1. **Current failure summary**: Brief description of the new test failure
2. **Comparison with each previous iteration**: Note similarities/differences for each iteration
3. **Novelty assessment**: Is this failure meaningfully different from ALL previous iterations?
4. **Final decision**: End with exactly one of:
   - "MEANINGFUL_CHANGE: YES" (novel failure - run research agents)
   - "MEANINGFUL_CHANGE: NO" (similar to previous iteration - skip research agents)

If you determine MEANINGFUL_CHANGE: NO, also include:
   - "MATCHED_ITERATION: N" (where N is the iteration number that this test output most closely matches)

Example response format when no meaningful change:
```
MEANINGFUL_CHANGE: NO
MATCHED_ITERATION: 3
```"""

    return prompt


def build_planner_prompt(state: FixTestsState) -> str:
    """Build the prompt for the planner agent."""
    artifacts_dir = state["artifacts_dir"]
    iteration = state["current_iteration"]
    verifier_notes: list[str] = state.get("verifier_notes", [])
    planner_retry_notes: list[str] = state.get("planner_retry_notes", [])

    base_prompt = f"You are a planner agent (iteration {iteration}). Your goal is to analyze previous workflow history and create a comprehensive todo list for the editor agent to fix the test failures."

    prompt = f"""{base_prompt}

# INSTRUCTIONS:
- Review the log.md file thoroughly for insights on what approaches have been tried and what to do next.
- Create todo items that instruct the editor agent to make actual fixes to underlying issues.
- Focus on analysis and proper code modifications.
- Address bugs, API changes, implementation issues, or infrastructure problems.
- Avoid simple workarounds - aim for genuine fixes that resolve the test failures.
- Use insights from previous research findings in log.md to inform your planning decisions.
- Learn from previous planning attempts documented in log.md to avoid repeating ineffective approaches.

# STRUCTURED OUTPUT INSTRUCTIONS:
- Your response MUST end with structured + bullets for file modifications.
- Focus on creating actionable, specific changes that will guide the editor agent to fix the test.
- NEVER recommend that editor agents run test commands - the workflow handles all test execution automatically.
- Each change item must be completely self-contained with full context.
- Create a systematic approach that addresses root causes while also making incremental progress.
- Cite relevant findings from log.md where applicable.

# NOTES ABOUT THE EDITOR AGENT:
- The editor agent can ONLY see the todo list you create.
- You MUST include ALL necessary context and instructions directly in the todo list.
- Do NOT reference previous agent responses or assume the editor knows what was tried before.

# AVAILABLE CONTEXT FILES:
@{artifacts_dir}/log.md - Complete workflow history with all previous planning, research, and test outputs organized by iteration (REVIEW THIS THOROUGHLY).
#cl"""

    # Add context files from directory if provided
    context_file_directory: str | None = state.get("context_file_directory")
    if context_file_directory and os.path.isdir(context_file_directory):
        # Find all markdown files in the directory
        md_files = []
        try:
            for filename in sorted(os.listdir(context_file_directory)):
                if filename.endswith(".md") or filename.endswith(".txt"):
                    file_path = os.path.join(context_file_directory, filename)
                    if os.path.isfile(file_path):
                        md_files.append(file_path)
        except Exception as e:
            print(f"Warning: Could not list context file directory: {e}")

        if md_files:
            prompt += "\n\n# ADDITIONAL CONTEXT FILES:"
            for file_path in md_files:
                prompt += f"\n@{file_path}"
            print(
                f"Added {len(md_files)} context file(s) from {context_file_directory} to planner prompt"
            )

    # Add oneshot context files if available (from failed oneshot attempt)
    oneshot_context_dir = state.get("oneshot_context_dir")
    if oneshot_context_dir and os.path.isdir(oneshot_context_dir):
        # Find all files in the oneshot context directory
        oneshot_files = []
        try:
            for filename in sorted(os.listdir(oneshot_context_dir)):
                file_path = os.path.join(oneshot_context_dir, filename)
                if os.path.isfile(file_path):
                    oneshot_files.append(file_path)
        except Exception as e:
            print(f"Warning: Could not list oneshot context directory: {e}")

        if oneshot_files:
            prompt += "\n\n# ONESHOT ATTEMPT CONTEXT:"
            prompt += "\nThe initial oneshot test fixer attempted to fix the tests but failed. Review these files to understand what was tried:"
            for file_path in oneshot_files:
                prompt += f"\n@{file_path}"
            print(
                f"Added {len(oneshot_files)} oneshot context file(s) to planner prompt"
            )

    # Add verifier notes if any exist (e.g., from file path validation failures)
    if verifier_notes:
        prompt += """

# IMPORTANT NOTES FROM PREVIOUS VALIDATION FAILURES:
Previous validation steps (such as file path validation) have provided the following guidance to help you succeed:
"""
        for i, note in enumerate(verifier_notes, 1):
            prompt += f"  {i}. {note}\n"

        prompt += "\nPlease review these notes carefully and ensure your file modifications address these issues."

    # Add planner retry notes if any exist (from verification agent identifying invalid plans)
    if planner_retry_notes:
        prompt += """

# CRITICAL FEEDBACK FROM VERIFICATION AGENT:
The verification agent has identified issues with previous planning attempts. The editor correctly determined that your previous plans were invalid for the following reasons:
"""
        for i, note in enumerate(planner_retry_notes, 1):
            prompt += f"  {i}. {note}\n"

        prompt += "\nYou MUST take this feedback seriously and create a completely different approach. The editor was correct that your previous plan was not needed or would be harmful."

    prompt += """

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
   - Analyze the complete workflow history from log.md.
   - Review all previous planning attempts, research findings, and test outputs.
   - Use available context files to understand the current state.

2. STRUCTURED OUTPUT CREATION:
   - End your response with structured + bullets for file modifications.
   - Include ONLY specific code changes that need to be made (no investigation or analysis tasks).
   - Each change should specify exactly what code change to make and in which file.
   - Order tasks logically - verification agent will handle syntax validation.
   - Incorporate insights from log.md where applicable.

## RESPONSE FORMAT:
Your response must contain:

1. **Analysis and Planning Section**: Describe your approach, key insights from log.md, and rationale for changes.

2. **File Modifications Section**: Use this exact format:
+ @<relative_path> (for existing files) or + NEW <relative_path> (for new files)  
  - Specific change 1 for this file
  - Specific change 2 for this file
  - Additional changes as needed

Your complete response should follow this structure:
```
# Analysis and Planning
Based on my review of log.md, I found that [analysis here]...

The key insights are:
- [insight 1]
- [insight 2]

# File Modifications

+ @src/main.py
  - Fix import statement on line 5 to use correct module name
  - Update function signature on line 20 to accept new parameter

+ NEW tests/test_feature.py
  - Create new test file with basic test structure  
  - Add test for the new functionality
```

## IMPORTANT:
- Include ONLY concrete code changes that need to be made.
- Do NOT include investigation, analysis, or research tasks.
- Do NOT include validation tasks - the verification agent handles syntax checking.
- Each todo should specify exactly what code change to make and in which file.
- All investigation has already been done - you just need to plan implementation based on log.md.
- Each todo must be COMPLETELY SELF-CONTAINED with full context.
- Include file paths, line numbers, exact code snippets, and detailed explanations in each todo item.
- Do NOT assume the editor knows anything about previous attempts or failures
- Focus on todos that make actual fixes to the underlying issues.
- Address root causes rather than symptoms.
- Make comprehensive fixes that resolve the test failures properly.
- Do NOT EVER suggest that an editor agent modify a BUILD file. You MAY ask the
  editor agent to run the `build_cleaner` command, if you think it would help,
  or any commands that the test failure output suggests to fix dependencies via
  commands that the test failure output suggests.
- Do NOT EVER include an absolute file path! ALWAYS use relative file
  paths which are prefixed with the '@' character for existing files (ex: @path/to/file.txt).
  File paths should NOT be wrapped in backticks.
- Cite specific findings from log.md when creating file modifications.
- Do NOT EVER ask an editor agent to investigate / research anything! That is
  your job! There should be ZERO ambiguity with regards to what edits need to
  be made in which files and/or which commands need to be run!

## RESPONSE REQUIREMENTS:
Your response MUST include:
1. Analysis and Planning section with key insights from log.md
2. File Modifications section with structured + bullets as shown in the format above
3. Each + bullet must specify a file path and list of specific changes to make"""

    # Check if user instructions file was provided and include content directly in prompt
    user_instructions_content = ""
    user_instructions_file = state.get("user_instructions_file")
    if user_instructions_file and os.path.exists(user_instructions_file):
        try:
            with open(user_instructions_file) as f:
                user_instructions_content = f.read().strip()
        except Exception as e:
            print(f"Warning: Could not read user instructions file: {e}")

    # Add USER INSTRUCTIONS section at the bottom
    if user_instructions_content:
        prompt += f"""

# ADDITIONAL INSTRUCTIONS:
{user_instructions_content}"""

    return prompt
