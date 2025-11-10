"""Prompts for the new-ez-feature workflow agents."""

import os

from .state import NewEzFeatureState


def build_editor_prompt(state: NewEzFeatureState) -> str:
    """Build the prompt for the editor agent."""
    cl_description = state["cl_description"]
    context_file_directory = state.get("context_file_directory")

    # Build CL description section
    cl_description_section = f"""# CL DESCRIPTION

{cl_description}
"""

    # Build context section
    context_section = ""

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
                if not context_section:
                    context_section = "# CONTEXT FILES\n"
                context_section += "\n## Additional Context Files\n"
                for md_file in md_files:
                    file_path = os.path.join(context_file_directory, md_file)
                    context_section += f"* @{file_path}\n"
        except Exception as e:
            print(f"Warning: Could not list context files: {e}")

    prompt = f"""You are an expert software engineer implementing a simple change that does not require tests.

{cl_description_section}
{context_section}

# YOUR TASK
Implement the changes described in the CL description above. This change has been marked as not requiring tests (TEST TARGETS: None), so focus solely on implementing the described functionality.

## Important Guidelines
1. **Read and analyze** all context files and design documents provided above
2. **Implement the changes** as described in the CL description - YOU MUST EDIT THE NECESSARY FILES
3. **Make actual file edits** - Do not just describe what needs to be changed, actually edit the files using your tools
4. **Follow best practices** for code quality and maintainability
5. **Do NOT add or modify tests** - this change is marked as test-exempt
6. **Be thorough** - ensure all aspects of the CL description are implemented

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
2. The actual file modifications (USE YOUR EDIT TOOLS)
3. A final summary of what was implemented

Begin implementing the changes now. Remember: YOU MUST ACTUALLY EDIT THE FILES.
"""

    return prompt
