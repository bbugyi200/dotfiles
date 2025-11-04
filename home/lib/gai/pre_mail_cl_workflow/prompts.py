"""Prompts for the pre-mail-cl workflow agents."""

import os
from pathlib import Path

from .state import PreMailCLState


def build_feature_implementation_research_prompt(state: PreMailCLState) -> str:
    """Build prompt for the feature implementation research agent."""
    cl_description = state["cl_description"]
    test_output_content = state["test_output_content"]

    prompt = f"""You are a deep research agent specializing in feature implementation analysis. Your task is to perform COMPREHENSIVE research on how to best implement the feature described below to make the failing tests pass.

# CL DESCRIPTION:

{cl_description}

# FAILING TEST OUTPUT:

The following tests are currently failing and need to be fixed by implementing the feature:

```
{test_output_content}
```

# YOUR TASK:

Use code search extensively to:

1. **Understand the Current Codebase Architecture**
   - Search for existing patterns and abstractions that relate to this feature
   - Identify key modules, classes, and functions that will be involved
   - Understand data flows and dependencies

2. **Find Similar Implementations**
   - Search for similar features already implemented in the codebase
   - Identify patterns and best practices used in existing code
   - Find utility functions and libraries that can be reused

3. **Identify Integration Points**
   - Determine where this feature will integrate with existing code
   - Identify APIs, interfaces, and contracts that need to be respected
   - Find configuration points and initialization sequences

4. **Analyze Test Failures**
   - Review the failing tests to understand what needs to be implemented
   - Identify the expected behavior from the test assertions
   - Determine what code changes are needed to make tests pass

5. **Research Best Approaches**
   - Based on existing patterns in the codebase, recommend the best approach
   - Consider trade-offs between different implementation strategies
   - Identify potential pitfalls or challenges

# OUTPUT FORMAT:

Provide a detailed research report with:
- Analysis of the failing tests and what they expect
- Key findings from code search
- Relevant code examples and patterns
- Recommended implementation approach to make tests pass
- Integration points and dependencies
- Potential challenges and solutions

Be thorough and cite specific files, functions, and line numbers where relevant.
"""

    return prompt


def build_architecture_research_prompt(state: PreMailCLState) -> str:
    """Build prompt for the architecture research agent."""
    cl_description = state["cl_description"]
    clsurf_output_file = state.get("clsurf_output_file")
    design_docs_dir = state["design_docs_dir"]

    # Get list of design doc files
    design_docs_dir_path = Path(design_docs_dir)
    md_files = sorted(design_docs_dir_path.glob("*.md"))

    prompt = f"""You are a deep research agent specializing in architectural analysis. Your task is to perform COMPREHENSIVE research on how this CL fits into the overall project architecture.

# CL DESCRIPTION:

{cl_description}

# CONTEXT FILES:

## Design Documents

The following design documents describe the overall project architecture and requirements:

"""

    # Reference design docs with @ prefix
    for md_file in md_files:
        prompt += f"@{md_file}\n"

    prompt += "\n"

    # Reference clsurf output if available
    if clsurf_output_file and os.path.exists(clsurf_output_file):
        prompt += f"""## Prior Work Analysis

The following is output from analyzing previous CLs related to this project:

@{clsurf_output_file}

"""

    prompt += """# YOUR TASK:

1. **Analyze Project Architecture**
   - Study the design documents to understand the overall project goals
   - Identify how this CL fits into the bigger picture
   - Understand dependencies between this CL and other planned CLs

2. **Research Architectural Patterns**
   - Use code search to understand existing architectural patterns
   - Identify design principles and conventions used in the codebase
   - Find similar architectural decisions made in prior work

3. **Identify Design Considerations**
   - Determine what architectural constraints must be respected
   - Identify interfaces and contracts that need to be maintained
   - Consider how this CL enables or blocks other planned work

4. **Provide Architectural Guidance**
   - Recommend how to structure the implementation to align with architecture
   - Suggest ways to maintain clean boundaries and separation of concerns
   - Identify opportunities to improve or refactor existing architecture

# OUTPUT FORMAT:

Provide a detailed architectural analysis with:
- Overview of where this CL fits in the project architecture
- Key architectural patterns and principles to follow
- Design considerations and constraints
- Recommendations for maintaining architectural integrity
- Connections to prior work and future CLs

Be thorough and reference specific design documents, prior CLs, and code patterns.
"""

    return prompt


def build_feature_coder_prompt(state: PreMailCLState) -> str:
    """Build prompt for the feature coder agent."""
    cl_name = state["cl_name"]
    cl_description = state["cl_description"]
    artifacts_dir = state["artifacts_dir"]
    test_output_content = state["test_output_content"]

    prompt = f"""You are an expert software engineer tasked with implementing a feature to make failing tests pass. The tests have already been added (TDD style), and your job is to implement the feature.

# CL NAME:
{cl_name}

# CL DESCRIPTION:
{cl_description}

# FAILING TEST OUTPUT:

The following tests are currently failing and need to be fixed:

```
{test_output_content}
```

# RESEARCH FINDINGS:

The following research has been conducted by specialized research agents. Review the log file for complete details:

@{artifacts_dir}/log.md

# YOUR TASK:

You must complete the following steps IN ORDER:

## STEP 1: Implement the Feature

- Implement the complete feature as described in the CL description
- Use the research findings to guide your implementation
- Follow existing patterns and conventions in the codebase
- Focus on making the failing tests pass

## STEP 2: Run the Tests

- Run the tests that were failing
- Verify that they now pass with your implementation
- If tests still fail, analyze the failure and fix the code

## STEP 3: Fix Test Failures (if any)

- If any tests fail, analyze the failure and fix the code
- Re-run the tests until they all pass
- If you cannot fix a test failure after trying very hard:
  * Revert ONLY the changes causing that specific build failure
  * Leave the rest of your implementation intact
  * Document what you reverted and why in your final summary

# IMPORTANT REQUIREMENTS:

- Try VERY HARD to fix any test failures before giving up
- Only revert specific changes causing failures, not the entire implementation
- Keep the implementation as complete as possible even if some tests fail
- Document your work thoroughly as you go
- Do NOT add new tests - only implement the feature

# FINAL OUTPUT:

At the end of your work, provide:

1. **Summary of Changes**
   - What you implemented and why
   - How the implementation makes the tests pass

2. **Test Results**
   - Which tests now pass
   - Which tests still fail (if any)
   - What you did to fix failures

3. **Postmortem Analysis**
   - Any challenges encountered
   - What you reverted (if anything) and why
   - Lessons learned

4. **Status Code**
   - Output either **SUCCESS** or **FAILURE** on its own line at the very end
   - SUCCESS means all tests passed
   - FAILURE means some tests are still failing despite your best efforts

Begin your implementation now. Good luck!
"""

    return prompt
