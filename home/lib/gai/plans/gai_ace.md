# Plan: Convert `gai ace` to Textual TUI

## Requirements
- **Replace CLI**: TUI becomes the only interface for `gai ace`
- **Default query**: `'"(!: "'` (filters out error suffixes)
- **Layout**: List + detail (left sidebar with ChangeSpecs list, right panel with detail)
- **Single keystroke**: All options require only one keystroke
- **Argument prompts**: Options needing arguments show modal dialogs

## File Structure

Create new TUI module at `/Users/bbugyi/.local/share/chezmoi/home/lib/gai/ace/tui/`:

```
ace/tui/
    __init__.py
    app.py                  # Main Textual App class
    widgets/
        __init__.py
        changespec_list.py      # Left sidebar list widget
        changespec_detail.py    # Right panel detail widget
        keybinding_footer.py    # Footer showing available keys
    modals/
        __init__.py
        status_modal.py         # Status selection modal
        query_edit_modal.py     # Query edit input modal
        workflow_select_modal.py # Workflow selection (for r1, r2, etc.)
    styles.tcss             # Textual CSS styling
```

## Key Components

### 1. Main App (`app.py`)
- Textual `App` subclass with reactive properties for `changespecs`, `current_idx`, `query_string`
- Key bindings for all single-key actions: n, p, q, s, r, R, m, f, d, v, h, a, y, /
- Auto-refresh timer using `set_interval()`
- Layout: `Header` + `Horizontal(ChangeSpecList, ChangeSpecDetail)` + `KeybindingFooter`

### 2. ChangeSpecList Widget (`changespec_list.py`)
- Extends `OptionList` for scrollable, selectable list
- Shows each ChangeSpec with name, status indicator, error markers
- Highlights currently selected item
- Responds to n/p keys and mouse clicks

### 3. ChangeSpecDetail Widget (`changespec_detail.py`)
- Adapts `display_changespec()` from `display.py` to render Rich `Text` in a Textual `Static` widget
- Shows full ChangeSpec info: NAME, DESCRIPTION, STATUS, HISTORY, HOOKS, etc.
- Preserves existing color scheme from `display.py`

### 4. KeybindingFooter Widget (`keybinding_footer.py`)
- Dynamic footer showing available actions based on current context
- Adapts logic from `build_navigation_options()` in `navigation.py`
- Shows/hides options based on ChangeSpec state (e.g., hide 'm' if not ready to mail)

### 5. Modal Dialogs
- **StatusModal**: Selection list for status change (s key)
- **QueryEditModal**: Input field for editing query (/ key)
- **WorkflowSelectModal**: Selection for multiple workflows (r key when multiple available)

## Integration Strategy

### Preserve Existing Handlers
All action handlers in `actions.py` and `handlers/` stay unchanged. The TUI only replaces the I/O layer:

```python
# Example: status change
def action_change_status(self) -> None:
    cs = self.changespecs[self.current_idx]
    def on_dismiss(new_status: str | None) -> None:
        if new_status:
            # Call existing handler
            self.changespecs, self.current_idx = handle_status_change(...)
            self._refresh_display()
    self.push_screen(StatusModal(cs.status), on_dismiss)
```

### External Process Handling
For actions that spawn external processes (d, m, R, workflows):
- Use Textual's `app.suspend()` before spawning
- Resume after process completes
- Use `run_worker()` for background tasks with progress

## Files to Modify

1. **`/Users/bbugyi/.local/share/chezmoi/home/lib/gai/main/parser.py`** (lines 21-44)
   - Make `query` argument optional with default `'"(!: "'`

2. **`/Users/bbugyi/.local/share/chezmoi/home/lib/gai/main/entry.py`** (lines 64-75)
   - Replace `AceWorkflow.run()` with `AceApp.run()`

3. **`/Users/bbugyi/.local/share/chezmoi/home/lib/gai/ace/__init__.py`**
   - Export `AceApp` instead of/alongside `AceWorkflow`

## Implementation Phases

### Phase 1: Core Structure
1. Create `ace/tui/` directory and `__init__.py`
2. Create `app.py` with basic Textual App skeleton
3. Create `styles.tcss` with initial CSS
4. Implement `ChangeSpecList` widget
5. Implement `ChangeSpecDetail` widget (adapt `display.py`)
6. Implement `KeybindingFooter` widget

### Phase 2: Navigation & Display
1. Wire up n/p/q key bindings
2. Implement reactive updates when `current_idx` changes
3. Add auto-refresh timer
4. Test basic navigation flow

### Phase 3: Simple Actions
1. Implement y (refresh) - direct handler call
2. Implement d (diff) - suspend for external process
3. Implement f (findreviewers) - direct handler call

### Phase 4: Modal Dialogs
1. Implement `StatusModal` for s key
2. Implement `QueryEditModal` for / key
3. Implement `WorkflowSelectModal` for r key

### Phase 5: Complex Actions
1. Implement h (edit hooks)
2. Implement v (view files)
3. Implement a (accept proposal) - parse a1, a2, etc.
4. Implement m (mail) and R (run query)

### Phase 6: Entry Point & Testing
1. Update parser.py for default query
2. Update entry.py to use TUI
3. Add tests for TUI components
4. Run `make fix && make lint && make test`

## Dependencies
Add to project: `textual>=0.45.0`
