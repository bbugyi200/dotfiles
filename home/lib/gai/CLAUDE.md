# Gai Codebase Guidelines

## Backward Compatibility

This codebase has a single user who can update all files simultaneously. Breaking changes are acceptable without:

- Backward-compatibility shims
- Deprecation warnings
- Migration paths

When making changes, update ChangeSpecs and project spec files in the same commit as the code changes they depend on.

## JSON Schemas

When modifying YAML file formats, update the corresponding JSON schema files:

- **Workflow schema**: `home/lib/gai/xprompts/workflow.schema.json` - update when changing workflow YAML structure
  (steps, control flow, config options, etc.)
- **Config schema**: `home/dot_config/gai/gai.schema.json` - update when changing gai.yml configuration options
