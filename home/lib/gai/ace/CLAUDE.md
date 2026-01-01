# Ace Subcommand Guidelines

## Directory Management for Workflows

**CRITICAL**: All workflow executions via the 'r' option MUST change to the correct working directory before running.

### Required Pattern

1. Get target directory: `get_workspace_directory(project_basename)`
2. Save current directory: `original_dir = os.getcwd()`
3. Change to target: `os.chdir(target_dir)` before `workflow.run()`
4. Restore in `finally` block: `os.chdir(original_dir)`

### Why This Is Required

Workflows need to run in the correct repository directory. The `update_to_changespec()` function only changes directory for subprocess calls, not for the Python process.

### Current Implementations

- `workflow.py::_handle_run_workflow` - For new-ez-feature and new-failing-tests
- `workflow_ops.py::run_tdd_feature_workflow` - For new-tdd-feature

New workflows triggered via 'r' option MUST implement this pattern.

## ChangeSpec Suffix Syntax Highlighting

**CRITICAL**: When updating styling for ChangeSpec suffix types (e.g., `killed_process`, `running_agent`, `error`), you MUST update ALL of these files:

1. `home/dot_config/nvim/syntax/gaiproject.vim` - Vim syntax highlighting (2 places: COMMITS and HOOKS sections)
2. `home/lib/gai/ace/display.py` - CLI Rich styling (3 places: commits, hooks, comments)
3. `home/lib/gai/ace/query/highlighting.py` - Query token styles in `QUERY_TOKEN_STYLES` dict
4. `home/lib/gai/ace/tui/widgets/changespec_detail.py` - TUI widget Rich styling (3 places: commits, hooks, comments)
