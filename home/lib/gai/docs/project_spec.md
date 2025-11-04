A ProjectSpec is a gai format specification for a project plan consisting of multiple CLs (change lists). The format is a collection of ChangeSpecs (see change_spec.md), each separated by a blank line.

The ProjectSpec file is created by the `gai create-project` workflow and saved to `~/.gai/projects/<filename>.md`.

## Format

A ProjectSpec consists of one or more ChangeSpecs, each separated by a blank line:

```
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

## ChangeSpec Fields

Each ChangeSpec within a ProjectSpec must contain the following fields:

1. **NAME**: Must be identical to the project filename (without .md extension) for all ChangeSpecs in the project
2. **DESCRIPTION**:
   - First line (TITLE): A brief one-line description of the CL (2-space indented)
   - Followed by a blank line (still 2-space indented)
   - Body (BODY): Multi-line detailed description of what the CL does, including:
     - What changes are being made
     - Why the changes are needed
     - File modifications in a clear format
   - All DESCRIPTION lines must be 2-space indented
3. **PARENT**: Either "None" (for the first CL or CLs with no dependencies) or the NAME of the parent CL that must be completed first
4. **CL**: Must be "None" when created by the workflow (can be updated to a CL-ID later when the CL is created)
5. **STATUS**: Must be "Not Started" when created by the workflow (can be updated to "In Progress", "Pre-Mailed", "Mailed", or "Submitted" during tracking)

## Example

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

NAME: my-project
DESCRIPTION:
  Add documentation for configuration system

  This CL adds user-facing documentation explaining how to configure
  the application using the config file.

  File modifications:
  - @docs/configuration.md
    * Document configuration file format
    * Add examples of common configuration scenarios
    * Document all available configuration options
PARENT: integrate-config-parser
CL: None
STATUS: Not Started
```

## Important Notes

- **Blank lines between ChangeSpecs**: Each ChangeSpec must be separated by exactly one blank line
- **NAME field**: All ChangeSpecs in a project MUST have the same NAME (the project filename without .md)
- **CL field**: Always set to "None" when created by the workflow (updated later when CL is created)
- **STATUS field**: Always set to "Not Started" when created by the workflow
- **PARENT field**: Used to establish dependencies between CLs in the project plan
- **Filename requirement**: The filename argument to `gai create-project` must NOT include the .md extension
- **File modification syntax**:
  - Use `- @path/to/file` for files that must exist
  - Use `- NEW path/to/file` for files that must not exist yet
