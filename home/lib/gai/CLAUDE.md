# Agent Prompt Guidelines

## File Size Limits and Package Structure

**CRITICAL**: When a Python file exceeds the 750-line limit, NEVER remove or compress docstrings to fit the limit. Instead, break the file up into a package with multiple modules.

### When to Break Up a File

1. **Single file exceeds 750 lines**: Convert to a package with logical groupings
2. **Test file exceeds 750 lines**: Group related tests into separate modules

### How to Structure a Package

```
work/
├── __init__.py          # Re-export public functions
├── changespec.py        # ChangeSpec data structures and parsing
├── operations.py        # Core operations (update, extract, etc.)
├── commit.py            # Commit-related operations (gai commit, etc.)
├── workflow.py          # Workflow-specific operations
└── test/
    ├── test_changespec.py
    ├── test_operations.py
    ├── test_commit.py
    └── test_workflow.py
```

### Best Practices

- Group related functions together logically
- Keep docstrings comprehensive and clear
- Update `__init__.py` to maintain backward compatibility
- Split test files along the same module boundaries

## File References in Prompts

**CRITICAL**: When building prompts for agents, ALWAYS use relative file paths with the '@' prefix instead of reading and embedding raw file content.

### ✅ CORRECT - Use '@' prefix for file references

```python
def build_prompt(state: MyState) -> str:
    artifacts_dir = state["artifacts_dir"]
    test_file = state["test_file"]

    prompt = f"""Your task description here.

# AVAILABLE CONTEXT FILES

* @{artifacts_dir}/test_output.txt - Test failure output
* @{artifacts_dir}/cl_desc.txt - CL description
* @{test_file} - Test file to modify

Review these files and complete the task."""

    return prompt
```

### ❌ INCORRECT - Do NOT embed raw file content

```python
def build_prompt(state: MyState) -> str:
    artifacts_dir = state["artifacts_dir"]

    # Don't do this!
    with open(f"{artifacts_dir}/test_output.txt") as f:
        test_output = f.read()

    with open(f"{artifacts_dir}/cl_desc.txt") as f:
        cl_desc = f.read()

    prompt = f"""Your task description here.

# AVAILABLE CONTEXT FILES

## Test Output
```
{test_output}
```

## CL Description
```
{cl_desc}
```
"""

    return prompt
```

## Exceptions

### 1. User Instructions

User-provided instructions should be embedded:

```python
user_instructions_content = ""
user_instructions_file = state.get("user_instructions_file")
if user_instructions_file and os.path.exists(user_instructions_file):
    try:
        with open(user_instructions_file) as f:
            user_instructions_content = f.read().strip()
    except Exception as e:
        print(f"Warning: Could not read user instructions file: {e}")

if user_instructions_content:
    prompt += f"""

# ADDITIONAL INSTRUCTIONS:
{user_instructions_content}"""
```

### 2. Small Test Output Files

Test output files with <500 lines should be embedded. Larger test output files should use '@' prefix:

```python
def _get_test_output_reference(test_output_file: str, artifacts_dir: str) -> str:
    """Get test output as embedded content or file reference based on size."""
    try:
        with open(test_output_file) as f:
            lines = f.readlines()

        if len(lines) < 500:
            # Small file - embed the content
            content = "".join(lines)
            return f"""
## Test Output
```
{content}
```"""
        else:
            # Large file - use @ reference
            relative_path = os.path.relpath(test_output_file, start=os.path.dirname(artifacts_dir))
            return f"* @{test_output_file} - Test output"
    except Exception as e:
        return f"* @{test_output_file} - Test output (error reading: {e})"

# In your prompt builder:
test_output_ref = _get_test_output_reference(test_output_file, artifacts_dir)
prompt = f"""Your task description here.

# AVAILABLE CONTEXT FILES

{test_output_ref}
"""
```

## ChangeSpec STATUS Synchronization

**CRITICAL**: When adding or modifying ChangeSpec STATUS values, you MUST update ALL of the following locations to keep them in sync:

1. **`status_state_machine.py`** - `VALID_STATUSES` list (the source of truth)
2. **`status_state_machine.py`** - `VALID_TRANSITIONS` dict (if adding new status)
3. **`work/changespec.py`** - `_get_status_color()` function (for CLI display colors)
4. **`home/dot_config/nvim/syntax/gaiproject.vim`** - syntax highlighting rules and highlight groups

### Checklist for Adding a New Status

- [ ] Add to `VALID_STATUSES` in `status_state_machine.py`
- [ ] Add transitions to/from the new status in `VALID_TRANSITIONS`
- [ ] Add color mapping in `_get_status_color()` in `work/changespec.py`
- [ ] Add `syn match` rule in `syntax/gaiproject.vim`
- [ ] Add `highlight` group in `syntax/gaiproject.vim`

### Color Conventions

- **Red (#FF5F5F)**: Error/failure states (e.g., "Failing Tests")
- **Blue (#87AFFF)**: In-progress states with "..." suffix
- **Gold (#FFD700)**: Waiting/needs-action states (e.g., "Needs Presubmit", "Needs QA")
- **Green (#87D700, #00AF00)**: Success/ready states (e.g., "Drafted", "Submitted")
- **Cyan-green (#00D787)**: Sent for review (e.g., "Mailed")
- **Orange (#FFAF00)**: Feedback received (e.g., "Changes Requested")
- **Gray (#808080)**: Terminal/inactive states (e.g., "Reverted")
