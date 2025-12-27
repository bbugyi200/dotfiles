# Agent Prompt Guidelines

## File Size Limits

**CRITICAL**: When a Python file exceeds 750 lines, break it into a package with multiple modules. NEVER compress docstrings to fit the limit.

Group related functions logically, update `__init__.py` for backward compatibility, and split test files along the same module boundaries.

## File References in Prompts

**CRITICAL**: When building prompts for agents, use relative file paths with the `@` prefix instead of embedding raw file content.

```python
prompt = f"""Your task description.

# AVAILABLE CONTEXT FILES
* @{artifacts_dir}/test_output.txt - Test failure output
* @{test_file} - Test file to modify"""
```

### Exceptions

1. **User instructions**: Embed directly in the prompt
2. **Small test output files** (<500 lines): Embed content; larger files use `@` prefix

## ChangeSpec STATUS Synchronization

**CRITICAL**: When adding/modifying STATUS values, update ALL of these locations:

1. `status_state_machine.py` - `VALID_STATUSES` list (source of truth)
2. `status_state_machine.py` - `VALID_TRANSITIONS` dict
3. `work/changespec.py` - `_get_status_color()` function
4. `home/dot_config/nvim/syntax/gaiproject.vim` - syntax highlighting

### Color Conventions

- **Red (#FF5F5F)**: Error/failure states
- **Blue (#87AFFF)**: In-progress states (with "..." suffix)
- **Gold (#FFD700)**: Waiting/needs-action states
- **Green (#87D700, #00AF00)**: Success/ready states
- **Cyan-green (#00D787)**: Sent for review
- **Orange (#FFAF00)**: Feedback received
- **Gray (#808080)**: Terminal/inactive states
