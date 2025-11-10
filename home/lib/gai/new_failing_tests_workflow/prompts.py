"""Prompts for the new-failing-tests workflow agents."""

import os

from .state import NewFailingTestState


def build_test_coder_prompt(state: NewFailingTestState) -> str:
    """Build prompt for the test coder agent."""
    cl_name = state["cl_name"]
    cl_description = state["cl_description"]
    context_file_directory = state.get("context_file_directory")

    # Build context section
    context_section = ""
    if context_file_directory:
        if os.path.isfile(context_file_directory):
            # Single file
            context_section = f"""
# CONTEXT FILE:

The following file contains project context and design information:

* @{context_file_directory} - Project context
"""
        elif os.path.isdir(context_file_directory):
            # Directory of files
            try:
                md_files = sorted(
                    [
                        f
                        for f in os.listdir(context_file_directory)
                        if f.endswith(".md") or f.endswith(".txt")
                    ]
                )
                if md_files:
                    context_section = "\n# CONTEXT FILES:\n\nThe following files contain project context and design information:\n\n"
                    for md_file in md_files:
                        file_path = os.path.join(context_file_directory, md_file)
                        context_section += f"* @{file_path} - {md_file}\n"
            except Exception as e:
                print(f"Warning: Could not list context files: {e}")
                context_section = (
                    f"\n# CONTEXT DIRECTORY:\n\n@{context_file_directory}\n"
                )

    prompt = f"""You are an expert test engineer tasked with adding NEW TESTS using Test-Driven Development (TDD). You will add tests that are DESIGNED TO FAIL because the feature has not been implemented yet.

# CL NAME:
{cl_name}

# CL DESCRIPTION:
{cl_description}
{context_section}

# YOUR TASK:

You must complete the following steps IN ORDER:

## STEP 0: Research the Feature and Test Strategy

**CRITICAL**: Before adding any tests, you must perform COMPREHENSIVE research using code search:

1. **Research Test Patterns in the Codebase**
   - Find similar features and study how they are tested
   - Identify testing frameworks, fixtures, and utilities in use
   - Understand test organization and naming conventions

2. **Research the Feature Implementation**
   - Search for existing features that are similar to the one being implemented
   - Identify patterns, architectures, and design approaches used in the codebase
   - Understand how related functionality is currently implemented

3. **Find Test Files and Examples**
   - Search for existing test files that cover related functionality
   - Study patterns, assertions, and test structure
   - Identify reusable test utilities, fixtures, and helper functions
   - Extract specific test examples that can serve as templates

4. **Come Up With a Test Strategy**
   - Determine what scenarios need to be tested
   - Consider edge cases and error conditions
   - Decide which test files to modify or create
   - Plan test data requirements

## STEP 1: Add NEW Tests That Will Fail

- Add comprehensive new tests to cover the feature described in the CL description
- Follow the test patterns and strategies from your research
- These tests should FAIL because the feature is not yet implemented
- Use the test file locations, patterns, and examples from your research
- Ensure tests cover both happy paths and edge cases

## STEP 2: Run the New Tests

- Run the new tests you added
- Verify that they FAIL as expected (because the feature is not implemented)
- If any test PASSES unexpectedly, that's a problem - the test may not be testing the right thing

## STEP 3: Verify Test Quality

- Ensure the tests are well-structured and follow codebase conventions
- Verify the tests use appropriate assertions and test utilities
- Make sure the tests will be meaningful once the feature is implemented

# IMPORTANT REQUIREMENTS:

- Do NOT implement any feature code - only add tests
- The tests MUST fail because the feature doesn't exist yet
- Follow existing test patterns and conventions from your research
- Add clear, descriptive test names that explain what is being tested
- Document your work thoroughly as you go

# FINAL OUTPUT:

At the end of your work, you MUST provide the following sections:

## 1. Summary of Changes
   - What tests you added and where
   - What scenarios they cover

## 2. Test Results
   - Confirmation that tests FAILED as expected
   - Any unexpected results (tests passing when they shouldn't)

## 3. Test Quality Assessment
   - How the tests align with the research findings
   - What will be validated once the feature is implemented

## 4. Test Targets (CRITICAL - REQUIRED!)

**THIS IS ABSOLUTELY REQUIRED AND NON-NEGOTIABLE:**

You MUST output a line with this EXACT format:

```
TEST_TARGETS:
  <target1>
  <target2>
```

Or for a single target or backwards compatibility:

```
TEST_TARGETS: <target>
```

Rules:
- Use bazel/rabbit test targets with format: `//path/to/package:test_name`
- **Multi-line format** (preferred for multiple targets): Each target on its own line, 2-space indented, no blank lines
- **Single-line format**: For single target or space-separated multiple targets (backwards compatible)
- If you created new test files, output their bazel targets
- If you only modified existing test files, output the existing target(s)
- Example (multi-line): `TEST_TARGETS:\n  //my/package:my_test\n  //other/package:integration_test`
- Example (single-line): `TEST_TARGETS: //my/package:my_test` or `TEST_TARGETS: //my/package:test1 //other:test2`

**WARNING**: If you do not output this line, the workflow will FAIL. This line is parsed and used to run the tests.
"""

    return prompt
