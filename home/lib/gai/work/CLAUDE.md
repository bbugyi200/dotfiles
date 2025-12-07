# Work Subcommand Guidelines

## Directory Management for Workflows

**CRITICAL**: ALL workflow executions triggered by the 'r' (run) option in `gai work` MUST change to the correct working directory before running.

### Required Pattern

When running ANY workflow from the work subcommand:

1. **Calculate target directory**: `$GOOG_CLOUD_DIR/<project>/$GOOG_SRC_DIR_BASE`
2. **Save current directory**: `original_dir = os.getcwd()`
3. **Change to target directory**: `os.chdir(target_dir)` BEFORE calling `workflow.run()`
4. **Restore original directory**: `os.chdir(original_dir)` in the `finally` block

### Example

```python
# Get target directory
goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")
target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

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

## Option Sorting

**CRITICAL**: ALL options displayed in `gai work` MUST be sorted alphabetically (case-insensitive).

### Implementation

Options are stored in a dictionary and sorted when displayed:

```python
def make_sort_key(key: str) -> str:
    """Create a sort key for strict alphabetical ordering."""
    return key.lower()

# When displaying options:
for key in sorted(options.keys(), key=make_sort_key):
    console.print(f"  [cyan]{key}[/cyan] - {options[key]}")
```

### Why This Is Required

- Consistent ordering makes the interface predictable and easy to navigate
- Users can quickly find options when they're always in the same relative position
- Case-insensitive sorting ensures 'Q' and 'q' are treated equivalently for ordering purposes
