A ProjectSpec is a gai format specification for a project plan consisting of multiple CLs (change lists). The format starts with a BUG field, followed by a collection of ChangeSpecs (see change_spec.md), each separated by a blank line.

The ProjectSpec file is created by the `gai create-project` workflow and saved to `~/.gai/projects/<filename>.md`.

## Format

A ProjectSpec starts with a BUG field at the top, followed by one or more ChangeSpecs, each separated by a blank line:

```
BUG: <BUG_ID>

NAME: <NAME1>
DESCRIPTION:
  <TITLE1>

  <BODY1>
PARENT: <PARENT1>
CL: <CL1>
STATUS: <STATUS1>

NAME: <NAME2>
DESCRIPTION:
  <TITLE2>

  <BODY2>
PARENT: <PARENT2>
CL: <CL2>
STATUS: <STATUS2>
```

## BUG Field

The BUG field is required at the very top of the ProjectSpec file, separated by a blank line from the first ChangeSpec:

- **BUG**: Bug ID to track this project. Supports multiple formats:
  - Plain ID: `BUG: 12345`
  - URL format: `BUG: http://b/12345` or `BUG: https://b/12345`

## ChangeSpec Fields

Each ChangeSpec within a ProjectSpec must contain the following fields:

1. **NAME**: Must start with the project filename (without .md extension) followed by an underscore and a descriptive suffix (words separated by underscores). Format: `<BASENAME>_<descriptive_suffix>` where the suffix thoughtfully describes the CL's intent (strive for shorter names)
2. **DESCRIPTION**:
   - First line (TITLE): A brief one-line description of the CL (2-space indented)
   - Followed by a blank line (still 2-space indented)
   - Body (BODY): Multi-line detailed description of what the CL does, including:
     - What changes are being made
     - Why the changes are needed
     - High-level approach or implementation details
   - All DESCRIPTION lines must be 2-space indented
   - **DO NOT include file modification lists** - that will be handled by a different workflow
3. **PARENT**: Either "None" (for the first CL or CLs with no dependencies) or the NAME of the parent CL that must be completed first
4. **CL**: Must be "None" when created by the workflow. Can be updated later when the CL is created. Supports multiple formats:
   - Plain ID: `CL: 12345`
   - Legacy format: `CL: cl/12345`
   - URL format: `CL: http://cl/12345` or `CL: https://cl/12345`
5. **STATUS**: Must be "Not Started" when created by the workflow (can be updated to "In Progress", "Pre-Mailed", "Mailed", or "Submitted" during tracking)

## Example

```
BUG: 12345

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

NAME: my-project_add_docs
DESCRIPTION:
  Add documentation for configuration system

  This CL adds user-facing documentation explaining how to configure
  the application using the config file. The documentation will cover
  the configuration file format, provide examples of common scenarios,
  and document all available configuration options.
PARENT: my-project_integrate_parser
CL: None
STATUS: Not Started
```

## Important Notes

- **BUG field**: Must be the first line of the ProjectSpec file, followed by a blank line
- **Blank lines between ChangeSpecs**: Each ChangeSpec must be separated by exactly one blank line
- **NAME field**: All ChangeSpecs in a project MUST start with `<basename>_` where basename is the project filename (without .md), followed by a descriptive suffix (words separated by underscores, strive for shorter names)
- **CL field**: Always set to "None" when created by the workflow (updated later when CL is created)
- **STATUS field**: Always set to "Not Started" when created by the workflow
- **PARENT field**: Used to establish dependencies between CLs in the project plan
- **Filename requirement**: The filename argument to `gai create-project` must NOT include the .md extension
- **No file modifications**: The DESCRIPTION should NOT include specific file modification lists - that will be handled by a different workflow
