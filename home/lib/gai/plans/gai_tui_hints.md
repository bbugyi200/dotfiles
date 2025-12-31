# TUI Hints Migration

## Request

Migrate the hints used for the "h" (edit hints) and "v" (view) options from the Rich-based terminal interface to the TUI used by `gai ace`. The goal was to eliminate the separate Rich console interface in favor of native Textual TUI modals.

## User Preferences (Clarified via Questions)

1. **UX Pattern**: Modal dialogs (like the existing StatusModal)
2. **Selection Style**: Keep numbered input pattern (user types "1 2 3@" to select hints)
3. **Add Hooks UX**: Text input in TUI modal for adding new hooks (everything stays in TUI)

## Previous Implementation

- `action_view_files()` and `action_edit_hooks()` in `app.py` used `self.suspend()` to pause the TUI
- Handlers cleared the console, called `display_changespec()` with Rich formatting to show hints
- Used `input()` for user selection
- External programs (editor, bat/less) ran in the suspended terminal

## Plan

### Phase 1: Create Data Types
- `HintItem`: Represents a single hint (number, display text, file path, category)
- `ViewFilesResult`: Result from view files modal (files, open_in_editor flag, user input)
- `EditHooksResult`: Result from edit hooks modal (action type, hints to rerun/delete, test targets, hook command)

### Phase 2: Create Hint Extraction Module
- Extract hint generation logic from `display.py::display_changespec()` into reusable functions
- Move utility functions (`_is_rerun_input`, `_build_editor_args`) to shared location

### Phase 3: Create TUI Modals
- `ViewFilesModal`: Shows hints, accepts numbered input, returns selected files
- `EditHooksModal`: Shows hook hints, accepts rerun/delete/add commands

### Phase 4: Update App Actions
- Modify `action_view_files()` and `action_edit_hooks()` to push modals
- Still use `self.suspend()` for external programs (editor, bat/less)

## File Changes

### New Files

| File | Description |
|------|-------------|
| `ace/hint_types.py` | Data types: `HintItem`, `ViewFilesResult`, `EditHooksResult` |
| `ace/hints.py` | Hint extraction and parsing utilities |
| `ace/tui/modals/view_files_modal.py` | Modal for viewing files with hint selection |
| `ace/tui/modals/edit_hooks_modal.py` | Modal for editing hooks |
| `test/test_hints.py` | 27 tests for hint functions |

### Modified Files

| File | Changes |
|------|---------|
| `ace/tui/app.py` | Updated imports; rewrote `action_view_files()` and `action_edit_hooks()` to use modals; added helper methods `_open_files_in_editor()`, `_view_files_with_pager()`, `_apply_hook_changes()`, `_handle_rerun_delete_hooks()`, `_add_test_target_hooks()`, `_add_custom_hook()` |
| `ace/tui/modals/__init__.py` | Added exports for `EditHooksModal`, `ViewFilesModal` |
| `ace/tui/styles.tcss` | Added CSS for new modals (container, hints display, input, buttons) |

## Key Functions in `ace/hints.py`

```python
def extract_view_hints(changespec) -> tuple[list[HintItem], dict[int, str]]:
    """Extract all file hints for view files modal."""

def extract_edit_hooks_hints(changespec) -> tuple[list[HintItem], dict[int, str], dict[int, int]]:
    """Extract hook hints for hooks_latest_only mode."""

def is_rerun_input(user_input: str) -> bool:
    """Check if input is a rerun/delete command (e.g., '1 2@ 3')."""

def parse_view_input(user_input, hint_mappings) -> tuple[list[str], bool, list[int]]:
    """Parse user input for view files modal."""

def parse_edit_hooks_input(user_input, hint_mappings) -> tuple[list[int], list[int], list[int]]:
    """Parse user input for rerun/delete hooks."""

def parse_test_targets(test_input: str) -> list[str]:
    """Parse test target input (e.g., '//foo:bar //baz:qux')."""

def build_editor_args(editor, user_input, changespec_name, files) -> list[str]:
    """Build editor command with nvim-specific enhancements."""
```

## Architecture Notes

1. **Circular Import Resolution**: `hint_types.py` was moved to the `ace/` level (not inside `tui/modals/`) to avoid circular imports between `hints.py` and the modals.

2. **Still Uses suspend()**: External programs (bat/less viewer, $EDITOR) still require `self.suspend()` because they need the terminal. The modals handle hint selection only.

3. **Rich Text in Modals**: Textual's `Static` widget can render `rich.text.Text` objects, so the hint styling is preserved in the modals.

## Testing

- 27 new tests added in `test/test_hints.py`
- All 856 existing tests continue to pass
- Coverage maintained at 59.36%
