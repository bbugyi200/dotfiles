# Fix Plan #3: All ChangeSpecs Showing (1/3) and No "p" Option

## Problem

After the second fix, all three ChangeSpecs are showing "(1/3)" instead of incrementing:
- First ChangeSpec (ilar): "(1/3)" with NO "p" option ✓ (correct)
- Second ChangeSpec (pat): "(1/3)" with NO "p" option ✗ (should be "2/3" with "p")
- Third ChangeSpec (yserve): "(1/3)" with NO "p" option ✗ (should be "3/3" with "p")

## Root Cause Analysis

### Key Observation from Output

The output shows that after selecting "n" (skip) on the first ChangeSpec (ilar), it IMMEDIATELY shows the second ChangeSpec (pat) **without** returning to the main loop (no workflow header between them). This means **all three ChangeSpecs are being shown in the SAME workflow instance**.

This can only happen if:
1. All three ChangeSpecs are in the SAME project file (not three separate files), OR
2. The workflow is somehow reading from multiple project files in one run

Given that the workflow is designed to process one project file at a time, the most likely scenario is that **all three ChangeSpecs are in ONE project file**.

### The Calculation Issue

With all three ChangeSpecs in one project file:
- `shown_before_this_workflow = 0` (set once at the start, never changes) ✓
- `current_changespec_index` should be: 0, 1, 2 for the three ChangeSpecs

So the calculation should be:
- First: `global_position = 0 + (0+1) = 1` → "(1/3)" ✓
- Second: `global_position = 0 + (1+1) = 2` → "(2/3)" with "p" option ✓
- Third: `global_position = 0 + (2+1) = 3` → "(3/3)" with "p" option ✓

But the output shows ALL three as "(1/3)", which means `current_changespec_index` is staying at 0!

### Why `current_changespec_index` Stays at 0

The issue is that `current_changespec_index` is updated in `select_next_changespec` (line 830-831):
```python
changespec_history = changespec_history + [selected_cs]
current_changespec_index = len(changespec_history) - 1
```

And then this updated state is returned (line 839-851):
```python
return {
    **state,
    "selected_changespec": selected_cs,
    ...
    "changespec_history": changespec_history,
    "current_changespec_index": current_changespec_index,
    ...
}
```

This state flows to `invoke_create_cl`, which reads `current_changespec_index` (line 928):
```python
current_changespec_index = state.get("current_changespec_index", -1)
```

So far so good. The issue is that we're reading it AFTER it's been set, so:
- First ChangeSpec: `select_next` sets index=0, `invoke_create_cl` reads index=0, calculates position=1 ✓
- Second ChangeSpec: `select_next` sets index=1, `invoke_create_cl` reads index=1, calculates position=2 ✓

This SHOULD work! But it doesn't.

### The Real Issue: State Reset in `check_continuation`

After `invoke_create_cl` returns, the workflow goes to `check_continuation`, which resets the index (line 1635-1637):
```python
"current_changespec_index": (
    -1 if not user_requested_prev else state["current_changespec_index"]
),
```

So the state is reset BEFORE looping back to `select_next`. This is correct.

But wait - let me trace through the state flow more carefully:

1. `select_next` returns: `{..., "current_changespec_index": 0, "changespec_history": [cs1]}`
2. `invoke_create_cl` receives this state, reads `current_changespec_index = 0`, calculates position = 1
3. `invoke_create_cl` returns the state (WITHOUT modifying `current_changespec_index`)
4. State flows through `handle_failure` or `handle_success` (unchanged)
5. State flows to `check_continuation`, which resets: `"current_changespec_index": -1`
6. Loop back to `select_next` with: `{..., "current_changespec_index": -1, "changespec_history": [cs1]}`
7. `select_next` adds cs2, sets `current_changespec_index = 1`
8. `invoke_create_cl` receives: `{..., "current_changespec_index": 1, "changespec_history": [cs1, cs2]}`
9. Should calculate position = 0 + (1+1) = 2 ✓

This SHOULD work!

### Debugging the Issue

The only way all three ChangeSpecs would show "(1/3)" is if `current_changespec_index` is somehow staying at 0 OR being read incorrectly.

Let me check if there's a timing issue. In `invoke_create_cl`, we read `current_changespec_index` EARLY in the function (line 928), before the user prompt. But by that point, `select_next` has already run and set the index.

**AH! I found it!** The issue is that we're reading `current_changespec_index` at line 928, but this is INSIDE the `if not yolo:` block (line 918). Let me check the exact indentation...

Looking at workflow_nodes.py line 918-940:
```python
# Prompt for confirmation unless yolo mode is enabled
if not yolo:
    # Get project directory for tmux window option
    project_name = state["project_name"]
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR", "")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE", "")
    project_dir = os.path.join(goog_cloud_dir, project_name, goog_src_dir_base)
    project_file = state["project_file"]

    # Calculate global position across all project files
    shown_before = state.get("shown_before_this_workflow", 0)
    current_changespec_index = state.get("current_changespec_index", -1)
    global_total = state.get("global_total_eligible", 0)
    ...
```

This is ONLY executed if `not yolo`. If `yolo = True`, this code is skipped! But the user is NOT running in yolo mode (they're being prompted), so this should run.

Wait, but if the state reading is correct, why would it show the wrong value?

Let me think about this differently. Maybe the issue is that `changespec_history` is NOT being preserved across loop iterations?

Let me check if `check_continuation` preserves `changespec_history`. Line 1623-1638:
```python
result_state: WorkProjectState = {
    **state,
    "attempted_changespecs": attempted_changespecs,
    "attempted_changespec_statuses": attempted_changespec_statuses,
    "changespecs_processed": changespecs_processed,
    "should_continue": should_continue,
    "success": False,
    "failure_reason": None,
    "selected_changespec": None,
    "status_updated_to_in_progress": False,
    "status_updated_to_tdd_cl_created": False,
    "status_updated_to_fixing_tests": False,
    "current_changespec_index": (
        -1 if not user_requested_prev else state["current_changespec_index"]
    ),
}
```

It uses `**state` to copy everything, then overrides specific fields. So `changespec_history` SHOULD be preserved (it's not in the override list).

So `changespec_history` should accumulate: [cs1], then [cs1, cs2], then [cs1, cs2, cs3].

Hmm, I'm really stuck. Without seeing debug output, it's hard to know what's going wrong.

## Hypothesis

Based on the symptoms, my best guess is that **`current_changespec_index` is somehow staying at 0** instead of incrementing to 1, 2.

This could happen if:
1. `select_next_changespec` is not properly incrementing the index
2. The state is being reset somewhere between `select_next` and `invoke_create_cl`
3. There's a bug in how the state is being passed through the workflow nodes

## Fix Strategy

Since I can't pinpoint the exact issue without debug output, I'll propose a more robust solution: **Track the global position directly in the state** instead of calculating it from `shown_before_this_workflow` + `current_changespec_index`.

### Approach: Add `global_position_counter` to State

Instead of calculating the position dynamically, we'll maintain an explicit counter that increments each time a ChangeSpec is shown.

1. Add `global_position_counter` to the state (initialized to 0)
2. In `invoke_create_cl`, BEFORE showing the ChangeSpec, increment the counter
3. Use this counter directly for display

This eliminates the dependency on `current_changespec_index` and `shown_before_this_workflow`, making the logic simpler and more reliable.

## Implementation Plan

### 1. Update State Type Definition

**File**: `home/lib/gai/work_projects_workflow/state.py`

Add a new field to `WorkProjectState`:
```python
global_position_counter: int  # Current global position (1-based, increments as ChangeSpecs are shown)
```

### 2. Initialize the Counter in Main

**File**: `home/lib/gai/work_projects_workflow/main.py`

Around line 558-592 in `_process_project_file`, add to `initial_state`:
```python
initial_state: WorkProjectState = {
    ...
    "shown_before_this_workflow": shown_before_this_workflow,
    "global_total_eligible": global_total,
    "global_position_counter": shown_before_this_workflow,  # Start from where we left off
    "workflow_instance": self,
}
```

### 3. Increment and Use Counter in `invoke_create_cl`

**File**: `home/lib/gai/work_projects_workflow/workflow_nodes.py`

Around line 926-940, replace the current calculation with:
```python
# Increment the global position counter for this ChangeSpec
global_position_counter = state.get("global_position_counter", 0) + 1
state["global_position_counter"] = global_position_counter  # Update state

# Use the counter directly for display
current_index = global_position_counter
total_count = state.get("global_total_eligible", 0)

# Can go prev if we're past the first ChangeSpec globally
# Use the history length since that's more reliable than the counter
changespec_history = state.get("changespec_history", [])
can_go_prev = len(changespec_history) > 1  # Can go back if we have >1 ChangeSpecs in history
```

**IMPORTANT**: We need to increment the counter BEFORE checking if yolo is enabled, so it increments even in yolo mode.

### 4. Preserve Counter in `check_continuation`

**File**: `home/lib/gai/work_projects_workflow/workflow_nodes.py`

In `check_continuation`, around line 1623-1638, ensure `global_position_counter` is preserved:
```python
result_state: WorkProjectState = {
    **state,
    "attempted_changespecs": attempted_changespecs,
    ...
    # Preserve global_position_counter - it should NOT reset between ChangeSpecs
    "global_position_counter": state.get("global_position_counter", 0),
}
```

Actually, since we're using `**state`, it's already preserved. We just need to make sure we DON'T override it.

## Alternative Simpler Fix

Actually, there's an even simpler fix: Instead of using `current_changespec_index` which gets reset, use `len(changespec_history)` which continuously grows:

**File**: `home/lib/gai/work_projects_workflow/workflow_nodes.py`

Around line 926-940:
```python
# Calculate global position using the history length
# History grows continuously: [], [cs1], [cs1, cs2], [cs1, cs2, cs3]
shown_before = state.get("shown_before_this_workflow", 0)
changespec_history = state.get("changespec_history", [])
global_total = state.get("global_total_eligible", 0)

# The current ChangeSpec has already been added to history by select_next
# So len(history) gives us the 1-based position of the current ChangeSpec
global_position = shown_before + len(changespec_history)

# Use global counts for display
current_index = global_position
total_count = global_total

# Can go prev if we have more than one ChangeSpec in history
can_go_prev = len(changespec_history) > 1
```

This is simpler because:
- `changespec_history` is never reset (it keeps growing)
- When `select_next` adds a ChangeSpec to history, `len(history)` increases
- First ChangeSpec: history=[cs1], len=1, position = 0 + 1 = 1 ✓
- Second ChangeSpec: history=[cs1, cs2], len=2, position = 0 + 2 = 2 ✓
- Third ChangeSpec: history=[cs1, cs2, cs3], len=3, position = 0 + 3 = 3 ✓

## Recommended Fix

Use the simpler alternative (using `len(changespec_history)`). This is more reliable because:
1. `changespec_history` is never reset (unlike `current_changespec_index`)
2. It's already being maintained correctly by `select_next`
3. It accurately represents how many ChangeSpecs have been shown so far

## Testing

After implementing the fix:
1. Put all three ChangeSpecs in ONE project file to test
2. Run `gai work` and verify:
   - First ChangeSpec: "(1/3)" with NO "p" option
   - Second ChangeSpec: "(2/3)" with "p" option
   - Third ChangeSpec: "(3/3)" with "p" option
3. Test with three separate project files to ensure it still works
4. Run quality checks
