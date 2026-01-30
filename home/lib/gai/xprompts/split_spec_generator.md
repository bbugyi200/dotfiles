---
name: split_spec_generator
input:
  - name: workspace_name
    type: word
  - name: diff_path
    type: path
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

2. Output ONLY valid YAML - no explanation, no markdown code fences, just raw YAML

3. Each entry should have:
   - `name`: The CL name (with {{ workspace_name }}\_ prefix)
   - `description`: A clear, concise description following the CL description guidelines
   - `parent`: (optional) The name of the parent CL if this builds on another split CL

4. **PRIORITIZE PARALLEL CLs**: Only use `parent` when there is a TRUE dependency
   - CL B should only be a child of CL A if B's changes cannot be applied without A's changes
   - If two CLs modify different files or independent parts of the codebase, they should be PARALLEL (no parent)
   - Parallel CLs can be reviewed and submitted independently, which is faster
   - When in doubt, prefer parallel CLs over creating unnecessary parent-child chains

## Expected Output Format

IMPORTANT: Use TWO blank lines between each entry for readability.

```yaml
# Parallel CLs (no parent - can be reviewed/submitted independently)
- name: {{ workspace_name }}_first_change
  description: |
    Brief summary of first change.


- name: {{ workspace_name }}_second_change
  description: |
    Brief summary of second change (independent of first).


# Child CL (only when truly dependent on parent)
- name: {{ workspace_name }}_dependent_change
  description: |
    This change requires first_change to be applied first.
  parent: {{ workspace_name }}_first_change
```

Generate the split specification now. Output ONLY the YAML content.
