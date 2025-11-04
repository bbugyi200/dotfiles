"""Prompts for the create-project workflow agents."""

import os
from pathlib import Path

from .state import CreateProjectState


def build_planner_prompt(state: CreateProjectState) -> str:
    """Build the prompt for the project planner agent."""
    design_docs_dir = state["design_docs_dir"]
    clsurf_output_file = state.get("clsurf_output_file")
    project_name = state["project_name"]

    # Get list of design doc files
    design_docs_dir_path = Path(design_docs_dir)
    md_files = sorted(design_docs_dir_path.glob("*.md"))
    design_doc_references = "\n".join([f"@{str(f)}" for f in md_files])

    prompt = f"""You are an expert project planning agent. Your goal is to analyze design documents and prior work to create a comprehensive project plan with proposed change lists (CLs).

# PROJECT NAME:

The project name for this plan is: **{project_name}**

**CRITICAL**: You MUST use "{project_name}" as the NAME field in EVERY ChangeSpec you generate. Do not use any other name.

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
  - `- @path/to/file` for files that MUST exist
  - `- NEW path/to/file` for files that MUST NOT exist yet

# OUTPUT FORMAT:

Your response MUST use the ChangeSpec format. Each ChangeSpec represents a single CL (change list) and must follow this exact format:

```
NAME: <NAME>
DESCRIPTION:
  <TITLE>

  <BODY>
PARENT: <PARENT>
CL: <CL>
STATUS: <STATUS>
```

**CRITICAL**: Separate each ChangeSpec with a blank line.

# CHANGESPEC FORMAT RULES:

1. **NAME**: MUST be exactly "{project_name}" for all ChangeSpecs in this project
2. **DESCRIPTION**:
   - First line (TITLE): A brief one-line description of the CL (2-space indented)
   - Followed by a blank line (still 2-space indented)
   - Body (BODY): Multi-line detailed description of what the CL does, including:
     - What changes are being made
     - Why the changes are needed
     - File modifications in a clear format
   - All DESCRIPTION lines must be 2-space indented
3. **PARENT**: Either "None" (for the first CL or CLs with no dependencies) or the NAME of the parent CL that must be completed first
4. **CL**: Must always be "None" (this will be updated to a CL-ID later when the CL is created)
5. **STATUS**: Must always be "Not Started" (other statuses are used for tracking progress after creation)

# EXAMPLE OUTPUT:

(NOTE: This is a generic example. In your actual output, replace "my-project" with "{project_name}")

```
NAME: my-project
DESCRIPTION:
  Add configuration file parser for user settings

  This CL implements a YAML-based configuration parser that reads
  user settings from ~/.myapp/config.yaml. Changes include:

  File modifications:
  - NEW home/lib/myapp/config.py
    * Add ConfigParser class with load() and validate() methods
    * Add type definitions for configuration schema
  - NEW home/lib/myapp/test/test_config.py
    * Add tests for ConfigParser.load() with valid YAML
    * Add tests for ConfigParser.validate() with invalid configs
    * Add tests for missing config file handling
PARENT: None
CL: None
STATUS: Not Started

NAME: my-project
DESCRIPTION:
  Integrate config parser into main application

  This CL integrates the configuration parser from the previous CL
  into the main application initialization flow.

  File modifications:
  - @home/lib/myapp/main.py
    * Import ConfigParser and load config at startup
    * Add error handling for invalid configurations
  - @home/lib/myapp/test/test_main.py
    * Add tests for main() with valid config
    * Add tests for main() with invalid config
PARENT: add-config-parser
CL: None
STATUS: Not Started
```

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
