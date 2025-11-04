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

The project basename for this plan is: **{project_name}**

**CRITICAL**: Every ChangeSpec NAME field MUST follow this format:
- Start with "{project_name}_" (the basename followed by an underscore)
- Followed by a 1-3 word descriptive suffix (words separated by underscores)
- The suffix should thoughtfully describe the specific CL's intent

Examples of valid NAMEs for this project:
- {project_name}_add_config_parser
- {project_name}_integrate_parser
- {project_name}_add_tests
- {project_name}_refactor_validation

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
- **Almost all CLs should include test coverage** since all code needs testing
- **Test code changes belong in the same CL** as the code they are testing
- **Do NOT propose CLs for work already completed** (as shown in prior work analysis)
- **Do NOT include file modification lists** in the DESCRIPTION - a different workflow will handle the specific file changes

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

1. **NAME**: MUST start with "{project_name}_" followed by a 1-3 word descriptive suffix (words separated by underscores)
2. **DESCRIPTION**:
   - First line (TITLE): A brief one-line description of the CL (2-space indented)
   - Followed by a blank line (still 2-space indented)
   - Body (BODY): Multi-line detailed description of what the CL does, including:
     - What changes are being made
     - Why the changes are needed
     - High-level approach or implementation details
   - All DESCRIPTION lines must be 2-space indented
   - **DO NOT include file modification lists** - that will be handled by a different workflow
3. **PARENT**: Either "None" (default - maximize parallelization!) or the NAME of a parent CL when there's a **real content dependency**
   - **CRITICAL**: Only set PARENT when CL B literally needs code/files/changes from CL A to exist first
   - **Default to "None"** to allow parallel development whenever possible
   - Examples of real dependencies:
     - CL B calls a function that CL A creates
     - CL B modifies a file that CL A creates
     - CL B extends a class that CL A introduces
   - Examples of what's NOT a dependency (keep PARENT=None):
     - Different features that don't interact
     - Changes to different files/modules
     - Tests for independent features
     - Documentation that doesn't reference new code
4. **CL**: Must always be "None" (this will be updated to a CL-ID later when the CL is created)
5. **STATUS**: Must always be "Not Started" (other statuses are used for tracking progress after creation)

# EXAMPLE OUTPUT:

(NOTE: This is a generic example. In your actual output, replace "my-project" with "{project_name}")

```
NAME: my-project_add_config_parser
DESCRIPTION:
  Add configuration file parser for user settings

  This CL implements a YAML-based configuration parser that reads
  user settings from ~/.myapp/config.yaml. The parser will include
  a ConfigParser class with load() and validate() methods, along
  with type definitions for the configuration schema. Tests will
  cover valid YAML parsing, invalid config validation, and missing
  file handling.
PARENT: None
CL: None
STATUS: Not Started

NAME: my-project_integrate_parser
DESCRIPTION:
  Integrate config parser into main application

  This CL integrates the configuration parser from the previous CL
  into the main application initialization flow. The main application
  will import ConfigParser and load the config at startup, with proper
  error handling for invalid configurations. Tests will verify both
  valid and invalid config scenarios.
PARENT: my-project_add_config_parser
CL: None
STATUS: Not Started

NAME: my-project_add_logging
DESCRIPTION:
  Add logging infrastructure for debugging

  This CL implements a logging system using Python's logging module.
  It will create a LogManager class that configures log levels, formats,
  and output destinations. This is completely independent of the config
  parser and can be developed in parallel. Tests will verify log output
  formatting and level filtering.
PARENT: None
CL: None
STATUS: Not Started
```

**Note**: In this example, `my-project_add_logging` has `PARENT: None` because it's independent
of the config parser work. It can be developed in parallel with the other CLs.

# IMPORTANT REMINDERS:

- **MAXIMIZE PARALLELIZATION**: Default to `PARENT: None` unless there's a real content dependency
- Do NOT include bullets for any CLs already completed (found in prior work)
- Focus ONLY on work that still needs to be done
- Ensure EVERY requirement from the design docs is covered
- Make CLs small and focused
- Include tests in almost every CL
- Do NOT list specific file modifications in the DESCRIPTION - describe what will be done, not which files will be changed
- **Think critically about dependencies**: Only set PARENT when CL B literally cannot work without CL A's changes

Begin your project plan now:
"""

    return prompt
