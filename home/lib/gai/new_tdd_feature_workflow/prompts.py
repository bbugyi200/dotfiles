"""Prompt builders for new-tdd-feature workflow."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from .state import NewTddFeatureState


def build_implementation_prompt(state: NewTddFeatureState) -> str:
    """Build the prompt for the implementation agent."""
    local_artifacts = state.get("local_artifacts", {})

    # Use local artifact paths (which are relative) or fallback to relative paths
    test_output_path = local_artifacts.get(
        "test_output_file", state["test_output_file"]
    )
    cl_desc_path = local_artifacts.get(
        "cl_desc_txt", "bb/gai/new-tdd-feature/cl_desc.txt"
    )
    cl_changes_path = local_artifacts.get(
        "cl_changes_diff", "bb/gai/new-tdd-feature/cl_changes.diff"
    )

    # Build context section with required context files
    context_section = f"""# AVAILABLE CONTEXT FILES
+ @{test_output_path} - Test failure output
+ @{cl_desc_path} - This CL's description
+ @{cl_changes_path} - A diff of this CL's changes"""

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
                context_section += "\n"
                for md_file in md_files:
                    file_path = os.path.join(context_file_directory, md_file)
                    context_section += f"+ @{file_path} - {md_file}\n"
        except Exception as e:
            print(f"⚠️ Warning: Could not list context files: {e}")

    prompt = f"""You are an expert software engineer implementing a feature using Test-Driven Development (TDD).

Your task is to implement the feature described in the CL description.

{context_section}

# INSTRUCTIONS
+ **Review the test failures, CL description, and context files** to understand what feature needs to be implemented
+ **Determine the appropriate test command** by examining the diff file and the test failure output
+ **Implement the feature** by making code changes to satisfy the failing tests
+ **Run the tests** after making changes to verify your implementation works
+ **DO NOT modify the tests** - unless you have to because they are incorrect, but think HARD before deciding to do this
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
