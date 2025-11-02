"""Prompts for the create-project workflow agents."""

import os
from pathlib import Path

from .state import CreateProjectState


def build_planner_prompt(state: CreateProjectState) -> str:
    """Build the prompt for the project planner agent."""
    design_docs_dir = state["design_docs_dir"]
    clsurf_output_file = state.get("clsurf_output_file")

    # Get list of design doc files
    design_docs_dir_path = Path(design_docs_dir)
    md_files = sorted(design_docs_dir_path.glob("*.md"))
    design_doc_references = "\n".join([f"@{str(f)}" for f in md_files])

    prompt = f"""You are an expert project planning agent. Your goal is to analyze design documents and prior work to create a comprehensive project plan with proposed change lists (CLs).

# CONTEXT FILES:

## Design Documents
{design_doc_references}

## Prior Work Analysis
"""

    if clsurf_output_file and os.path.exists(clsurf_output_file):
        prompt += f"@{clsurf_output_file} - Previous CLs submitted by the author\n"
    else:
        prompt += "(No prior work information available)\n"

    prompt += """
# YOUR TASK:

1. **Thoroughly analyze all design documents** to understand:
   - All requirements and features that need to be implemented
   - Technical specifications and constraints
   - Dependencies and integration points
   - Success criteria and testing requirements

2. **Review the prior work** (if available) to understand:
   - What has already been implemented or attempted
   - What patterns and approaches have been used
   - What remains to be done
   - **IMPORTANT**: You should NOT propose CLs for work that has already been completed

3. **Create a comprehensive project plan** that:
   - Breaks down the project into small, focused CLs
   - Ensures every design requirement is satisfied
   - Includes test changes in almost every CL (ALL code needs test coverage)
   - Verifies that file paths are valid (files exist or don't exist as appropriate)
   - Uses the NEW syntax for file modifications

# CRITICAL REQUIREMENTS:

- **Think EXTREMELY HARD** about the plan to ensure completeness and correctness
- **Small CLs are essential** - each CL should be focused on a single, well-defined change
- **Almost all CLs should include test changes** since all code needs test coverage
- **Test code changes belong in the same CL** as the code they are testing
- **Do NOT propose CLs for work already completed** (as shown in prior work analysis)
- **Verify file paths** - use appropriate syntax:
  - `+ @path/to/file` for files that MUST exist
  - `+ NEW path/to/file` for files that MUST NOT exist yet

# OUTPUT FORMAT:

Your response MUST use this exact markdown bullet format:

```markdown
* <First line of CL description for CL #1>
+ <Description of what this CL will do>
+ @path/to/existing/file1.py
  - <Change 1 to this file>
  - <Change 2 to this file>
+ NEW path/to/new/test_file.py
  - <What will be in this new test file>
+ @path/to/existing/test_file2.py
  - <Test changes for the code changes in this CL>

* <First line of CL description for CL #2>
+ <Description of what this CL will do>
+ @path/to/existing/file2.py
  - <Change 1 to this file>
+ @path/to/existing/test_file3.py
  - <Test changes for the code changes in this CL>
```

# BULLET FORMAT RULES:

1. **Level 1 bullets (*)**: Represent a single CL's first line of description
2. **Level 2 bullets (+)**:
   - First 2+ bullet(s) under a * should describe what the CL will do
   - Remaining + bullets represent files to modify (using @ for existing, NEW for new files)
3. **Level 3 bullets (-)**: Describe the specific changes to be made to the file above them
4. **Deeper levels**: Use *, +, -, *, +, -, ... in that repeating order

# IMPORTANT REMINDERS:

- Do NOT include bullets for any CLs already completed (found in prior work)
- Focus ONLY on work that still needs to be done
- Ensure EVERY requirement from the design docs is covered
- Make CLs small and focused
- Include tests in almost every CL
- Verify all file paths are correct (exist or don't exist as appropriate)

Begin your project plan now:
"""

    return prompt
