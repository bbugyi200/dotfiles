"""Prompts for the new-change workflow agents."""

import os
from pathlib import Path

from .state import NewChangeState


def build_editor_prompt(state: NewChangeState) -> str:
    """Build the prompt for the editor agent."""
    cl_name = state["cl_name"]
    cl_description = state["cl_description"]
    design_docs_dir = state["design_docs_dir"]
    research_file = state.get("research_file")

    # Get list of design doc files
    design_docs_dir_path = Path(design_docs_dir)
    md_files = sorted(design_docs_dir_path.glob("*.md"))
    design_doc_references = "\n".join([f"@{str(f)}" for f in md_files])

    prompt = f"""You are an expert software engineer implementing a change that does not require tests.

# CHANGE SPECIFICATION

**Name:** {cl_name}

**Description:**
{cl_description}

# CONTEXT FILES

## Design Documents
{design_doc_references}
"""

    if research_file and os.path.exists(research_file):
        prompt += f"""
## Research Findings
@{research_file}
"""

    prompt += """
# YOUR TASK

Implement the changes described in the change specification above. This change has been marked as not requiring tests (TEST TARGETS: None), so focus solely on implementing the described functionality.

## Important Guidelines

1. **Read and analyze** all design documents and research findings
2. **Implement the changes** as described in the change specification
3. **Follow best practices** for code quality and maintainability
4. **Do NOT add or modify tests** - this change is marked as test-exempt
5. **Be thorough** - ensure all aspects of the change specification are implemented

## Common Use Cases for Test-Exempt Changes

- Configuration file updates
- Documentation-only changes
- Simple refactoring without behavior changes
- Build or deployment script updates
- Static resource updates

## Output Format

When making changes, structure your response as follows:

1. Brief summary of the changes being made
2. The actual file modifications
3. A final summary of what was implemented

Begin implementing the changes now.
"""

    return prompt
