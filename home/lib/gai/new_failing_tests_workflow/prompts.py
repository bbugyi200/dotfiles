"""Prompts for the new-failing-tests workflow agents."""

from .state import NewFailingTestState


def build_test_coder_prompt(state: NewFailingTestState) -> str:
    """Build prompt for the test coder agent."""
    cl_name = state["cl_name"]
    cl_description = state["cl_description"]
    design_docs_dir = state["design_docs_dir"]

    prompt = f"""You are an expert test engineer tasked with adding NEW TESTS using Test-Driven Development (TDD). You will add tests that are DESIGNED TO FAIL because the feature has not been implemented yet.

# CL NAME:
{cl_name}

# CL DESCRIPTION:
{cl_description}

# DESIGN DOCUMENTATION:

The design documents for this project are available in the following directory. Review them for context:

@{design_docs_dir}

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
TEST_TARGETS: <target1> <target2> ...
```

Rules:
- Use space-separated bazel/rabbit test targets (e.g., `//path/to/package:test_name`)
- If you created new test files, output their bazel targets
- If you only modified existing test files, output the existing target(s)
- Example: `TEST_TARGETS: //my/package:my_test //other/package:integration_test`
- If truly NO tests are needed (config/docs only), output: `TEST_TARGETS: None`

**WARNING**: If you do not output this line, the workflow will FAIL. This line is parsed and used to run the tests.

## 5. Status Code
   - Output either **SUCCESS** or **FAILURE** on its own line at the very end
   - SUCCESS means tests were added, they fail as expected, AND you output TEST_TARGETS
   - FAILURE means there were problems adding tests, they didn't fail as expected, OR you couldn't determine test targets

Begin your test implementation now. Good luck!
"""

    return prompt


def build_verifier_prompt(state: NewFailingTestState) -> str:
    """Build prompt for the verifier agent."""
    cl_name = state["cl_name"]
    cl_description = state["cl_description"]
    design_docs_dir = state["design_docs_dir"]
    test_coder_response = state.get("test_coder_response", "")

    prompt = f"""You are a verification agent tasked with sanity checking the work of the test coder agent. Your job is to ensure the test coder agent made correct changes, NOT to nitpick the quality of the tests.

# CL NAME:
{cl_name}

# CL DESCRIPTION:
{cl_description}

# DESIGN DOCUMENTATION:

The design documents for this project are available in the following directory:

@{design_docs_dir}

# TEST CODER AGENT WORK:

The test coder agent has completed their work. Here is a summary of their output:

{test_coder_response}

# YOUR TASK:

**Focus ONLY on sanity checking for incorrect changes**, NOT on nitpicking test quality.

## CRITICAL: What to Check

1. **Verify Tests Target the Right Feature**
   - Do the tests actually test the feature described in the CL description?
   - Are field names, function names, and identifiers correct?
   - Are the tests testing the right component/module?

2. **Check for Obvious Errors**
   - Are there syntax errors or clear bugs in the test code?
   - Are there obvious typos in critical identifiers?
   - Are imports and dependencies correct?

3. **Verify Test Approach Makes Sense**
   - Does the overall test strategy align with the feature requirements?
   - Are the test files modified/created in reasonable locations?

## IMPORTANT: What NOT to Check

**DO NOT** reject changes for these reasons:
- Code style or formatting issues
- Missing edge cases or additional test scenarios
- Different test patterns than you would have used
- Lack of comprehensive coverage
- Minor improvements that could be made

Your job is to catch **incorrect changes**, not to ensure **perfect changes**.

# FINAL OUTPUT:

You MUST provide your verdict in this format:

## Verification Result

[Provide a brief summary of your verification findings]

## Decision

Output EXACTLY one of these two lines:

```
APPROVED
```

OR

```
REJECTED: <brief reason>
```

If you output REJECTED, provide a brief, specific reason explaining what is incorrect (not what could be better).

Begin your verification now.
"""

    return prompt
