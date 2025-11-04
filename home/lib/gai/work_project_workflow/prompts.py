"""Prompts for the work-project workflow research agents."""

from .state import WorkProjectState


def build_test_strategy_research_prompt(state: WorkProjectState) -> str:
    """Build prompt for the test strategy research agent."""
    cl_description = state["cl_description"]

    prompt = f"""You are a deep research agent specializing in test strategy analysis. Your task is to perform COMPREHENSIVE research on the test strategy for the feature described below.

# CL DESCRIPTION:

{cl_description}

# YOUR TASK:

Use code search extensively to:

1. **Research Test Patterns in the Codebase**
   - Find similar features and study how they are tested
   - Identify testing frameworks, fixtures, and utilities in use
   - Understand test organization and naming conventions

2. **Determine Test Coverage Needed**
   - Identify what scenarios need to be tested
   - Consider edge cases and error conditions
   - Determine if unit tests, integration tests, or both are needed

3. **Plan Test Implementation**
   - Recommend specific test files to modify or create
   - Suggest test utilities or fixtures to use
   - Identify test data requirements

4. **Design Tests That Will Fail**
   - Since we're implementing TDD, these tests should be designed to FAIL initially
   - The tests should validate the behavior described in the CL description
   - Once the feature is implemented, these tests should pass

# OUTPUT FORMAT:

Provide a detailed test research report with:
- Test patterns and frameworks to use
- Recommended test coverage strategy
- Specific test scenarios to cover (that will fail until feature is implemented)
- Test utilities and fixtures to leverage
- Specific test files where tests should be added

Be thorough and cite specific test files, test names, and patterns.
"""

    return prompt


def build_deep_test_research_prompt(state: WorkProjectState) -> str:
    """Build prompt for the deep test research agent."""
    cl_description = state["cl_description"]
    artifacts_dir = state["artifacts_dir"]

    prompt = f"""You are a deep research agent specializing in test file analysis. Your task is to perform DEEP RESEARCH on test files that are likely to be relevant for testing the feature described below.

# CL DESCRIPTION:

{cl_description}

# CONTEXT:

You have access to research from a test strategy agent at:

@{artifacts_dir}/log.md

Review this research to understand the recommended test strategy.

# YOUR TASK:

Use code search EXTENSIVELY to:

1. **Find Test Files Where New Tests Will Be Added**
   - Search for existing test files that cover related functionality
   - Identify the most appropriate test files for adding new tests
   - Understand the structure and organization of these test files

2. **Analyze Similar Test Files**
   - Find test files that test similar features
   - Study patterns, assertions, and test structure
   - Identify reusable test utilities, fixtures, and helper functions

3. **Research Test Data and Mocking Patterns**
   - Find examples of test data setup for similar features
   - Identify mocking patterns and test doubles used in the codebase
   - Understand how dependencies are injected for testing

4. **Provide Concrete Examples**
   - Extract specific test examples that can serve as templates
   - Show how similar features are tested with actual code snippets
   - Include file paths and line numbers for reference

# OUTPUT FORMAT:

Provide a detailed test file analysis with:
- Specific test files where tests should be added
- Examples of similar tests that can serve as templates
- Test utilities, fixtures, and helper functions to use
- Test data and mocking patterns
- Concrete code examples with file paths and line numbers

Be thorough and include actual code snippets as examples.
"""

    return prompt
