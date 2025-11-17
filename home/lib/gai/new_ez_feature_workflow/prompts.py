"""Prompts for the new-ez-feature workflow agents."""

from .state import NewEzFeatureState


def build_editor_prompt(state: NewEzFeatureState) -> str:
    """Build the prompt for the editor agent."""
    cl_description = state["cl_description"]
    guidance = state.get("guidance")

    # Build CL description section
    cl_description_section = f"""## Change Description
{cl_description}
"""
    prompt = f"""Can you implement the file changes described in the change description below? Ensure
all aspects of the change description are implemented via the file changes you
make, but do NOT actually create a new CL.

{cl_description_section}"""

    # Append guidance if provided
    if guidance:
        prompt += f"\n## Implementation Guidance\n{guidance}"

    return prompt
