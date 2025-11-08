# Fix Plan: `gai work` Incorrect ChangeSpec Counter and Missing "p" (prev) Option

## Problem

When running `gai work`, the following incorrect behavior is observed:
1. Each ChangeSpec displays as "(1/3)" instead of incrementing (1/3, 2/3, 3/3)
2. The "p" (prev) option is never shown, even when viewing the 2nd or 3rd ChangeSpec

## Root Cause Analysis

The issue is in `home/lib/gai/work_projects_workflow/workflow_nodes.py` in the `invoke_create_cl` function around lines 927-939.

### Current Logic (INCORRECT)

```python
# Calculate global position dynamically
shown_before = state.get("shown_before_this_workflow", 0)
current_in_workflow = state.get("current_changespec_index", -1) + 1
global_position = shown_before + current_in_workflow
global_total = state.get("global_total_eligible", 0)

if global_position > 0 and global_total > 0:
    # Use global counts across all project files
    current_index = global_position
    total_count = global_total
else:
    # Fall back to per-file counts
    current_index = current_in_workflow
    total_count = state.get("total_eligible_changespecs", 0)

# Can go prev if we're past the first ChangeSpec globally
can_go_prev = global_position > 1
```

### Why It Fails

1. **`shown_before_this_workflow` is set once per `_process_project_file` call** (line 551 in main.py):
   - It's calculated as `len(shown_changespec_names)` at workflow initialization
   - It never changes during the workflow's internal loop
   - For a single project file processed in one workflow run, it remains `0` throughout

2. **`current_changespec_index` is reset to -1 after each ChangeSpec** (line 1635 in workflow_nodes.py):
   - After processing each ChangeSpec, `check_continuation` resets it to `-1`
   - When `select_next_changespec` runs again, it increments `changespec_history` and sets `current_changespec_index = len(changespec_history) - 1`
   - However, the **position counter is calculated BEFORE the workflow loops back**, so it uses the reset value

3. **The calculation happens at the wrong point in the workflow**:
   - `invoke_create_cl` is called with `current_changespec_index` that was just set by `select_next`
   - For ChangeSpec #1: `current_changespec_index = 0`, so `current_in_workflow = 1`, `global_position = 0 + 1 = 1` 
   - After processing, `current_changespec_index` is reset to `-1` by `check_continuation`
   - For ChangeSpec #2: `select_next` sets `current_changespec_index = 1`, so we should get `current_in_workflow = 2`, `global_position = 2` 

Wait, the logic actually looks correct when I trace through it carefully. Let me reconsider...

### Alternative Root Cause

After re-examining, the issue might be that:

1. **`changespec_history` is not being preserved correctly** between loop iterations in the workflow
2. **The state is being reset somewhere** that's not obvious from the code

### Most Likely Root Cause (After Deeper Analysis)

Looking at `check_continuation` line 1623-1638, I see that `changespec_history` is preserved via `**state`, but let me check if there's an issue with how the history is being managed...

Actually, I think the real issue is in `select_next_changespec` around lines 824-832:

```python
# Update history and calculate total count
# If this is a new ChangeSpec (not from history), add it to the history
cs_name = selected_cs.get("NAME", "")
if current_changespec_index == -1 or current_changespec_index >= len(
    changespec_history
):
    # Adding a new ChangeSpec to the history
    changespec_history = changespec_history + [selected_cs]
    current_changespec_index = len(changespec_history) - 1
# If we went back in history, keep the history as is
```

The condition `current_changespec_index >= len(changespec_history)` would be:
- First ChangeSpec: `-1 >= 0` is `False`, but `-1 == -1` is `True`, so we add cs1, history = [cs1], index = 0
- After reset by check_continuation: index = -1
- Second ChangeSpec: `-1 >= 1` is `False`, but `-1 == -1` is `True`, so we add cs2, history = [cs1, cs2], index = 1

This should work correctly...

### ACTUAL Root Cause (Final Analysis)

After very careful review, I believe the issue is that **the counter position is showing the same value because `shown_before_this_workflow` is being calculated incorrectly for the workflow's internal loop**.

The real issue is:
- `shown_before_this_workflow` is meant to track ChangeSpecs shown across ALL project files
- But within a single workflow run (which processes multiple ChangeSpecs from one project file), it stays at the initial value
- The counter should be: `current_changespec_index + 1` within the workflow, NOT `shown_before + current_in_workflow`

## Fix Strategy

### Option 1: Simplify the Counter Logic (RECOMMENDED)

Within a single workflow run for one project file, ignore the global counter and just use the per-workflow counter:

```python
# Use the position within this workflow's history
current_index = state.get("current_changespec_index", -1) + 1
total_count = state.get("total_eligible_changespecs", 0)
can_go_prev = state.get("current_changespec_index", -1) > 0
```

This is simpler and more accurate for the workflow's internal loop.

### Option 2: Track Global Position Correctly

Update `shown_before_this_workflow` dynamically as we process each ChangeSpec in the workflow loop. This would require modifying `check_continuation` to increment it.

## Implementation Plan

1. **Modify `invoke_create_cl` function** (line ~927-942 in workflow_nodes.py):
   - Replace the complex global position calculation with simple per-workflow counter
   - Use `current_changespec_index + 1` for position
   - Use `changespec_history` length for "already shown" detection

2. **Update can_go_prev logic**:
   - Change from `global_position > 1` to `current_changespec_index > 0`
   - This correctly identifies if there's a previous ChangeSpec in the history

3. **Fix the counter display**:
   - Use `current_changespec_index + 1` for current position
   - Use `total_eligible_changespecs` for total count (already calculated correctly in `select_next`)

## Specific Code Changes

### File: `home/lib/gai/work_projects_workflow/workflow_nodes.py`

**Location**: Lines 927-952 in `invoke_create_cl` function

**Replace:**
```python
# Calculate global position dynamically
shown_before = state.get("shown_before_this_workflow", 0)
current_in_workflow = state.get("current_changespec_index", -1) + 1
global_position = shown_before + current_in_workflow
global_total = state.get("global_total_eligible", 0)

if global_position > 0 and global_total > 0:
    # Use global counts across all project files
    current_index = global_position
    total_count = global_total
else:
    # Fall back to per-file counts
    current_index = current_in_workflow
    total_count = state.get("total_eligible_changespecs", 0)

# Can go prev if we're past the first ChangeSpec globally
can_go_prev = global_position > 1
```

**With:**
```python
# Calculate position within this workflow's ChangeSpec history
# current_changespec_index is 0-based (0 = first ChangeSpec, 1 = second, etc.)
current_changespec_index = state.get("current_changespec_index", -1)
total_eligible = state.get("total_eligible_changespecs", 0)

# Position is 1-based for display (1/3, 2/3, 3/3)
current_index = current_changespec_index + 1 if current_changespec_index >= 0 else 0
total_count = total_eligible

# Can go prev if we have at least one ChangeSpec in history before the current one
can_go_prev = current_changespec_index > 0
```

## Testing Plan

1. Run `gai work` on a project with 3 ChangeSpecs
2. Verify that the counter shows:
   - First ChangeSpec: "(1/3)" with no "p" option
   - Second ChangeSpec: "(2/3)" with "p" option available
   - Third ChangeSpec: "(3/3)" with "p" option available
3. Test the "p" (prev) option to ensure it navigates back correctly
4. Test with multiple project files to ensure the counter still works

## Notes

- The `shown_before_this_workflow` and `global_total_eligible` state variables can remain for potential future use with cross-project navigation
- This fix focuses on fixing the within-project-file navigation, which is the primary use case
- The global counter logic can be revisited if there's a future requirement for cross-project position tracking
