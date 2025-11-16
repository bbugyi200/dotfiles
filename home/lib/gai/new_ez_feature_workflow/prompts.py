"""Prompts for the new-ez-feature workflow agents."""

import os

from .state import NewEzFeatureState


def build_editor_prompt(state: NewEzFeatureState) -> str:
    """Build the prompt for the editor agent."""
    cl_description = state["cl_description"]
    context_file_directory = state.get("context_file_directory")
    guidance = state.get("guidance")

    # Build CL description section
    cl_description_section = f"""## CL DESCRIPTION
{cl_description}
"""

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
                context_section += "\n## Context Files\n"
                for md_file in md_files:
                    file_path = os.path.join(context_file_directory, md_file)
                    context_section += f"+ @{file_path}\n"
        except Exception as e:
            print(f"Warning: Could not list context files: {e}")

    prompt = f"""Can you implement the file changes described in the change description below? Ensure all
aspects of the change description are implemented via the file changes you make, but do NOT actually
create a new CL.

{cl_description_section}
{context_section}"""

    # Append guidance if provided
    if guidance:
        prompt += f"\n\nIMPLEMENTATION GUIDANCE: {guidance}"

    return prompt
