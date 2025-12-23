# Work Subcommand Guidelines

## Directory Management for Workflows

**CRITICAL**: ALL workflow executions triggered by the 'r' (run) option in `gai work` MUST change to the correct working directory before running.

### Required Pattern

When running ANY workflow from the work subcommand:

1. **Calculate target directory**: Use `get_workspace_directory(project_basename)` from `running_field`
2. **Save current directory**: `original_dir = os.getcwd()`
3. **Change to target directory**: `os.chdir(target_dir)` BEFORE calling `workflow.run()`
4. **Restore original directory**: `os.chdir(original_dir)` in the `finally` block

### Example

```python
from running_field import get_workspace_directory

# Get target directory
target_dir = get_workspace_directory(project_basename)

# Save current directory to restore later
original_dir = os.getcwd()

try:
    # Change to target directory before running workflow
    os.chdir(target_dir)

    # Run the workflow
    workflow = SomeWorkflow(...)
    workflow_succeeded = workflow.run()

    # ... rest of workflow handling ...

finally:
    # Restore original directory
    os.chdir(original_dir)

    # ... rest of cleanup ...
```

### Why This Is Required

- Workflows need to run in the correct repository directory to access files
- The `update_to_changespec()` function only changes directory for subprocess calls, not for the Python process
- Without this, workflows run in whatever directory the user was in when they ran `gai work`

### Current Implementations

This pattern is currently implemented in:

1. **`workflow.py::_handle_run_workflow`** - For new-ez-feature and new-failing-tests workflows
2. **`workflow_ops.py::run_tdd_feature_workflow`** - For new-tdd-feature workflow

If you add a new workflow that can be triggered via the 'r' option, you MUST implement this same pattern.
