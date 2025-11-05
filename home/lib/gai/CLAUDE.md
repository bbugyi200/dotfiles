# Agent Prompt Guidelines

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
