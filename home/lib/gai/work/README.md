# Work Package

Interactive workflow for navigating and managing ChangeSpecs across project files.

## Architecture

### Module Organization

```
work/
├── changespec.py     # ChangeSpec data model, parsing, and display
├── filters.py        # Filter validation and application
├── status.py         # Status selection and prompting
├── operations.py     # ChangeSpec operations (extract, update, validate)
├── workflow.py       # Main WorkWorkflow class with navigation loop
└── main.py          # Public API (re-exports WorkWorkflow)
```

### Separation of Concerns

**changespec.py** - Data layer
- `ChangeSpec` dataclass
- Parsing from markdown files
- Finding all changespecs across projects
- Rich display formatting

**filters.py** - Filter layer
- `validate_filters()` - Validate status and project filters
- `filter_changespecs()` - Apply filters with OR logic

**status.py** - Status management
- `get_available_statuses()` - Get valid status transitions
- `prompt_status_change()` - Interactive status selection UI

**operations.py** - ChangeSpec operations
- `should_show_run_option()` - Check if run action is available
- `extract_changespec_text()` - Extract full changespec from file
- `update_to_changespec()` - Update working directory (bb_hg_update)

**workflow.py** - Orchestration layer
- `WorkWorkflow` - Main workflow class
- Interactive navigation loop
- Action handlers: next, prev, status change, run, diff, tmux
- State management and UI coordination

## WorkWorkflow

### Initialization

```python
workflow = WorkWorkflow(
    status_filters=["Not Started", "In Progress"],  # OR logic
    project_filters=["myproject"]                     # OR logic
)
```

### Navigation Flow

1. Load and filter changespecs
2. Display current changespec with rich formatting
3. Compute default action based on position and direction
4. Show available actions (n/p/s/r/d/t/q)
5. Execute selected action
6. Reload changespecs if modified
7. Repeat

### Action Handlers

- **n (next)** - Move to next changespec, track forward direction
- **p (prev)** - Move to previous changespec, track backward direction
- **s (status)** - Prompt for new status, update file, reload
- **r (run)** - Run new-ez-feature workflow, manage status transitions
- **d (diff)** - Update to changespec, run branch_diff
- **t (tmux)** - Create new tmux window at changespec
- **q (quit)** - Exit workflow

### Smart Defaults

Default action adapts to context:
- **Last changespec** → default to quit
- **Forward navigation** → default to next
- **Backward navigation** → default to prev
- **First after backward** → reset to forward

### State Management

After modifying changespecs:
1. Reload from files (`find_all_changespecs()`)
2. Reapply filters (`filter_changespecs()`)
3. Reposition to same changespec by name
4. Preserve navigation context

## Key Design Decisions

### Why Separate Modules?

Original `main.py` was 730 lines. Refactoring benefits:
- **Testability** - Pure functions easy to unit test
- **Reusability** - Operations/filters usable outside workflow
- **Maintainability** - Clear boundaries, single responsibility
- **Readability** - Each module < 200 lines, focused purpose

### Why Action Handler Methods?

Action handlers (`_handle_*`) stay as methods because they:
- Need workflow state (console, filters, current position)
- Coordinate multiple operations atomically
- Manage UI feedback and error handling
- Return updated state (changespecs, index)

Pure operations extracted to `operations.py` for reuse.

### Why Reload After Modifications?

Changespecs stored in markdown files. After status changes or workflow runs:
- File content is source of truth
- Other processes may modify files
- Filters may change which changespecs are visible
- Ensures UI always reflects current state

## Usage Example

```python
from gai.work import WorkWorkflow

# Filter by status and project
workflow = WorkWorkflow(
    status_filters=["Not Started", "In Progress"],
    project_filters=["myproject", "otherproject"]
)

# Run interactive navigation
success = workflow.run()
```

## Dependencies

- **rich** - Terminal UI (Console, Panel, Text)
- **workflow_base** - BaseWorkflow interface
- **status_state_machine** - Status validation and transitions
- **new_ez_feature_workflow** - EZ feature creation workflow

## Environment Variables

- `GOOG_CLOUD_DIR` - Base directory for projects
- `GOOG_SRC_DIR_BASE` - Source directory within projects
- `TMUX` - Detected for tmux window creation
