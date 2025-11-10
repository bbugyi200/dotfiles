"""Prompts for the new-ez-feature workflow agents."""

import os

from .state import NewEzFeatureState


def build_editor_prompt(state: NewEzFeatureState) -> str:
    """Build the prompt for the editor agent."""
    design_docs_dir = state["design_docs_dir"]
    artifacts_dir = state["artifacts_dir"]
    context_file_directory = state.get("context_file_directory")

    # Build context section
    context_section = f"""
# CONTEXT FILES
* @{artifacts_dir}/cl_desc.txt - This CL's description (from hdesc command)
* @{artifacts_dir}/cl_changes.diff - A diff of this CL's changes (from branch_diff command)
"""

    # Add design documents
    if os.path.isdir(design_docs_dir):
        try:
            md_files = sorted(
                [
                    f
                    for f in os.listdir(design_docs_dir)
                    if f.endswith(".md") or f.endswith(".txt")
                ]
            )
            if md_files:
                context_section += "\n## Design Documents\n"
                for md_file in md_files:
                    file_path = os.path.join(design_docs_dir, md_file)
                    context_section += f"* @{file_path} - {md_file}\n"
        except Exception as e:
            print(f"Warning: Could not list design doc files: {e}")

    # Add additional context files from context_file_directory
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
                context_section += "\n## Additional Context Files\n"
                for md_file in md_files:
                    file_path = os.path.join(context_file_directory, md_file)
                    context_section += f"* @{file_path} - {md_file}\n"
        except Exception as e:
            print(f"Warning: Could not list context files: {e}")

    prompt = f"""You are an expert software engineer implementing a simple change that does not require tests.

{context_section}

# YOUR TASK
Implement the changes described in the change description. This change has been marked as not requiring tests (TEST TARGETS: None), so focus solely on implementing the described functionality.

## Important Guidelines
1. **Read and analyze** all context files, design documents, and the CL description
2. **Review the current changes** in cl_changes.diff to understand the context
3. **Implement the changes** as described in the change specification
4. **Follow best practices** for code quality and maintainability
5. **Do NOT add or modify tests** - this change is marked as test-exempt
6. **Be thorough** - ensure all aspects of the change specification are implemented

## Common Use Cases for Test-Exempt Changes
- Configuration file updates
- Documentation-only changes
- Simple refactoring without behavior changes
- Build or deployment script updates
- Static resource updates
- Simple feature implementations that are too trivial to test

## Output Format
When making changes, structure your response as follows:

1. Brief summary of the changes being made
2. The actual file modifications
3. A final summary of what was implemented

Begin implementing the changes now.
"""

    return prompt
