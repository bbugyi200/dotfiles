# Gai Codebase Guidelines

## JSON Schemas

When modifying YAML file formats, update the corresponding JSON schema files:

- **Workflow schema**: `home/lib/gai/xprompts/workflow.schema.json` - update when changing workflow YAML structure
  (steps, control flow, config options, etc.)
- **Config schema**: `home/dot_config/gai/gai.schema.json` - update when changing gai.yml configuration options
