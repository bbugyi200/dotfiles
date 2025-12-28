# Plan: Add "READY TO MAIL" Check to `gai loop`

## Overview

Add a 10s check to `gai loop` that appends " - (!: READY TO MAIL)" to "STATUS: Drafted" ChangeSpecs when they are ready to be mailed, and update "f"/"m" option visibility to only show when this suffix is present.

## Requirements Summary

1. **Add suffix**: Append " - (!: READY TO MAIL)" to STATUS line when:
   - STATUS is "Drafted"
   - No other " - (!: <msg>)" suffixes exist anywhere in the ChangeSpec (HISTORY, HOOKS, COMMENTS)
   - Either: no PARENT, OR PARENT status is "Submitted", "Mailed", OR PARENT has "READY TO MAIL" suffix (chained readiness)

2. **Remove suffix**: Strip " - (!: READY TO MAIL)" when status changes to "Mailed" (via "m" or "s" options)

3. **Option visibility**: Hide "f" and "m" options unless "(!: READY TO MAIL)" is in the STATUS line

## Files to Modify

### Core Implementation

1. **`home/lib/gai/status_state_machine.py`**
   - Modify `remove_workspace_suffix()` to also strip " - (!: READY TO MAIL)" suffix
   - This ensures status comparisons/validations treat "Drafted - (!: READY TO MAIL)" as "Drafted"

2. **`home/lib/gai/work/changespec.py`**
   - Add constant `READY_TO_MAIL_SUFFIX = " - (!: READY TO MAIL)"`
   - Add helper `has_ready_to_mail_suffix(status: str) -> bool`
   - Add helper `has_any_error_suffix(changespec: ChangeSpec) -> bool` to check HISTORY/HOOKS/COMMENTS for " - (!: " patterns

3. **`home/lib/gai/work/loop/core.py`**
   - Add new method `_check_ready_to_mail(changespec: ChangeSpec) -> list[str]` in `LoopWorkflow`
   - Call it in `_run_hooks_cycle()` after other checks
   - Logic:
     - Skip if status != "Drafted" (base status)
     - Skip if already has READY TO MAIL suffix
     - Skip if `has_any_error_suffix(changespec)` returns True
     - Check parent condition using new helper `is_parent_ready_for_mail(changespec)`:
       - No parent: True
       - Parent status is "Submitted" or "Mailed": True
       - Parent has READY TO MAIL suffix: True (chained readiness)
       - Otherwise: False
     - If all conditions met, update STATUS line to add suffix

4. **`home/lib/gai/work/hooks/operations.py`** (already modified in working tree)
   - Add function to update STATUS line with/without READY TO MAIL suffix

### Status Change Handling

5. **`home/lib/gai/work/mail_ops.py`**
   - Before calling `transition_changespec_status()` to "Mailed", strip the READY TO MAIL suffix if present

6. **`home/lib/gai/work/status.py`** (for "s" option)
   - When transitioning from "Drafted" to any other status, ensure suffix is stripped

### Option Visibility

7. **`home/lib/gai/work/workflow/navigation.py`**
   - Modify lines 101-111: Change condition from `status == "Drafted"` to check for READY TO MAIL in STATUS
   - Use `has_ready_to_mail_suffix(changespec.status)` for visibility check

### Vim Syntax Highlighting

8. **`home/dot_config/nvim/syntax/gaiproject.vim`**
   - Add pattern to highlight " - (!: READY TO MAIL)" suffix in STATUS line with appropriate color (green to indicate ready state)

### Tests

9. **`home/lib/gai/test/test_loop.py`**
   - Add tests for `_check_ready_to_mail()` method
   - Test cases: no parent, parent submitted, parent mailed, has error suffix, already has suffix

10. **`home/lib/gai/test/test_status_state_machine.py`**
    - Add tests for suffix stripping in status comparisons

## Implementation Steps

### Step 1: Add Constants and Helpers (changespec.py)
```python
READY_TO_MAIL_SUFFIX = " - (!: READY TO MAIL)"

def has_ready_to_mail_suffix(status: str) -> bool:
    """Check if status has the READY TO MAIL suffix."""
    return "(!: READY TO MAIL)" in status

def get_base_status(status: str) -> str:
    """Get base status without READY TO MAIL suffix."""
    if has_ready_to_mail_suffix(status):
        return status.replace(READY_TO_MAIL_SUFFIX, "").strip()
    return status

def has_any_error_suffix(changespec: ChangeSpec) -> bool:
    """Check if ChangeSpec has any error suffixes in HISTORY/HOOKS/COMMENTS."""
    # Check HISTORY entries
    if changespec.history:
        for entry in changespec.history:
            if entry.suffix_type == "error":
                return True
    # Check HOOKS status lines
    if changespec.hooks:
        for hook in changespec.hooks:
            if hook.status_lines:
                for sl in hook.status_lines:
                    if sl.suffix_type == "error":
                        return True
    # Check COMMENTS entries
    if changespec.comments:
        for comment in changespec.comments:
            if comment.suffix_type == "error":
                return True
    return False

def is_parent_ready_for_mail(changespec: ChangeSpec, all_changespecs: list[ChangeSpec]) -> bool:
    """Check if parent is ready (allows this changespec to be mailed).

    Returns True if:
    - No parent
    - Parent status is "Submitted" or "Mailed"
    - Parent has READY TO MAIL suffix (chained readiness)
    """
    if changespec.parent is None:
        return True
    for cs in all_changespecs:
        if cs.name == changespec.parent:
            base_status = get_base_status(cs.status)
            if base_status in ("Submitted", "Mailed"):
                return True
            if has_ready_to_mail_suffix(cs.status):
                return True
            return False
    # Parent not found - allow (same pattern as is_parent_submitted)
    return True
```

### Step 2: Update Status State Machine (status_state_machine.py)
- Modify `remove_workspace_suffix()` to also strip READY TO MAIL suffix pattern

### Step 3: Add STATUS Update Function (hooks/operations.py)
```python
def update_changespec_status_suffix(
    file_path: str,
    changespec_name: str,
    new_status_with_suffix: str,
) -> bool:
    """Update the STATUS line for a ChangeSpec."""
    # Similar pattern to other atomic update functions
```

### Step 4: Add 10s Check (loop/core.py)
- Add `_check_ready_to_mail()` method
- Add to `_run_hooks_cycle()` call sequence

### Step 5: Update Mail Operations (mail_ops.py)
- Strip suffix before status transition

### Step 6: Update Option Visibility (navigation.py)
- Change visibility condition for "f" and "m" options

### Step 7: Add Vim Syntax (gaiproject.vim)
- Add pattern for READY TO MAIL suffix highlighting

### Step 8: Add Tests
- Unit tests for new helpers
- Integration tests for the 10s check behavior

## Edge Cases to Handle

1. **Race condition**: ChangeSpec modified between check and update - use atomic file operations
2. **Parent not found**: Treat as "okay to proceed" (existing pattern in `is_parent_submitted()`)
3. **Multiple suffixes**: Only check for error suffixes, not acknowledged (~:) suffixes
4. **Status already has workspace suffix**: Handle both patterns in stripping
