"""Prompt builders for new-tdd-feature workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from .state import NewTddFeatureState


def build_implementation_prompt(state: NewTddFeatureState) -> str:
    """Build the prompt for the implementation agent."""
    artifacts_dir = state["artifacts_dir"]
    test_output_file = state["test_output_file"]
    current_iteration = state["current_iteration"]

    # Build context section with required context files
    context_section = f"""
# AVAILABLE CONTEXT FILES

* @{test_output_file} - Test failure output from new-failing-tests workflow
* @{artifacts_dir}/cl_desc.txt - This CL's description (from hdesc command)
* @{artifacts_dir}/cl_changes.diff - A diff of this CL's changes (from branch_diff command)"""

    # Add context files from context_file_directory if provided
    context_file_directory = state.get("context_file_directory")
    if context_file_directory and os.path.isdir(context_file_directory):
        try:
            md_files = sorted(
                [
                    f
                    for f in os.listdir(context_file_directory)
                    if f.endswith(".md") or f.endswith(".txt")
                ]
            )
            if md_files:
                context_section += "\n\n## Design Documents\n"
                for md_file in md_files:
                    file_path = os.path.join(context_file_directory, md_file)
                    context_section += f"* @{file_path} - {md_file}\n"
        except Exception as e:
            print(f"⚠️ Warning: Could not list context files: {e}")

    # Build test targets section
    test_targets = state["test_targets"]
    test_targets_section = f"""

# TEST TARGETS

Run these specific test targets to verify your implementation:
```
rabbit test -c opt --noshow_progress {test_targets}
```
"""

    prompt = f"""This is iteration {current_iteration} of the TDD feature implementation workflow.

Your task is to implement the feature described in the failing tests. The tests were created in a previous "new-failing-tests" workflow and now need to be made to pass.

{context_section}{test_targets_section}

# INSTRUCTIONS

1. **Review the test failures** in @{test_output_file} to understand what feature needs to be implemented
2. **Review the CL description** in @{artifacts_dir}/cl_desc.txt to understand the context
3. **Review any design documents** provided in the context files above
4. **Implement the feature** by making code changes to satisfy the failing tests
5. **Run the tests** after making changes to verify your implementation
6. **DO NOT modify the tests** - only implement the feature code to make the existing tests pass
7. **Leave your changes in place** even if tests still fail - do NOT revert your changes

# IMPORTANT NOTES

- This is a TDD (Test-Driven Development) workflow, so the tests define the requirements
- Focus on making the tests pass while following best practices and design patterns
- If you cannot make all tests pass in this iteration, that's okay - focus on making progress
- Document what you implemented and what still needs work

# RESPONSE FORMAT

Please end your response with a "### Implementation Log" section that documents:
- What feature you implemented and why
- What code changes you made
- What tests you ran and what the results were
- Whether the tests passed, partially passed, or still failed
- What still needs to be implemented (if tests still fail)

Example format:

### Implementation Log

#### Feature Implemented
- Implemented feature X based on test requirements
- Added helper functions Y and Z to support the feature

#### Code Changes
- Created new file/module: path/to/file.py
- Modified existing file: path/to/other.py
  - Added function foo() to handle...
  - Updated class Bar to support...

#### Test Results
- Ran tests: [command used]
- Result: [passed/failed/partial]
- Details: [specific information about what passed/failed]

#### Status
- [COMPLETED/IN_PROGRESS/NEEDS_MORE_WORK]
"""

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
