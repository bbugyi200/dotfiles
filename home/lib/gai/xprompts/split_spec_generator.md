---
name: split_spec_generator
input: { workspace_name: word, diff_path: path, split_desc: { type: line, default: "multiple CLs" } }
---

# Generate Split Specification

You need to analyze the changes in a CL and generate a split specification that divides the work into {{ split_desc }}.

## Original Diff

@{{ diff_path }}

## Guidelines

Refer to the following files for guidance:

- @~/bb/docs/small_cls.md - Guidelines for determining how many CLs to create
- @~/bb/docs/cl_descriptions.md - Guidelines for writing good CL descriptions

## CRITICAL REQUIREMENTS

1. **All 'name' field values MUST be prefixed with `{{ workspace_name }}_`**
   - Example: `{{ workspace_name }}_add_logging`, `{{ workspace_name }}_refactor_utils`

2. Each entry should have:
   - `name`: The CL name (with `{{ workspace_name }}_` prefix)
   - `description`: A clear, concise description following the CL description guidelines
   - `parent`: (optional) The name of the parent CL if this builds on another split CL

3. **PRIORITIZE PARALLEL CLs**: Only use `parent` when there is a TRUE dependency
   - CL B should only be a child of CL A if B's changes cannot be applied without A's changes
   - If two CLs modify different files or independent parts of the codebase, they should be PARALLEL (no parent)
   - Parallel CLs can be reviewed and submitted independently, which is faster
   - When in doubt, prefer parallel CLs over creating unnecessary parent-child chains

#json:`[{ name: word, description: text, parent: { type: word, default: "" } }]`
