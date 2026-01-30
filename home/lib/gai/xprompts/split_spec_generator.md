---
name: split_spec_generator
input:
  - name: workspace_name
    type: word
  - name: diff_path
    type: path
output:
  type: yaml_schema
  validator: split_spec
---

# Generate Split Specification

You need to analyze the changes in a CL and generate a YAML split specification that divides the work into multiple
smaller, focused CLs.

## Original Diff

@{{ diff_path }}

## Guidelines

Refer to the following files for guidance:

- @~/bb/docs/small_cls.md - Guidelines for determining how many CLs to create
- @~/bb/docs/cl_descriptions.md - Guidelines for writing good CL descriptions

## CRITICAL REQUIREMENTS

1. **All 'name' field values MUST be prefixed with `{{ workspace_name }}_`**
   - Example: `{{ workspace_name }}_add_logging`, `{{ workspace_name }}_refactor_utils`

2. **PRIORITIZE PARALLEL CLs**: Only use `parent` when there is a TRUE dependency
   - CL B should only be a child of CL A if B's changes cannot be applied without A's changes
   - If two CLs modify different files or independent parts of the codebase, they should be PARALLEL (no parent)
   - Parallel CLs can be reviewed and submitted independently, which is faster
   - When in doubt, prefer parallel CLs over creating unnecessary parent-child chains

Generate the split specification now.
