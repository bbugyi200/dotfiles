# Fix Plan #4: Deep Analysis of ChangeSpec Counter and Navigation Issues

## Summary of Previous Attempts

### Fix #6 (used `shown_before + current_changespec_index + 1`)
- Changed from per-workflow counting to global counting
- Moved `global_total_eligible` calculation outside the loop
- **Result**: Still failed - all ChangeSpecs showed (1/3)

### Fix #7 (used `shown_before + len(changespec_history)`)
- Changed from using `current_changespec_index` to `len(changespec_history)`
- Reasoning: history grows continuously, while index gets reset
- **Result**: Still having issues (user requesting Fix #4)

## Root Cause Analysis: The REAL Problem

After extremely careful analysis, I've identified **TWO CRITICAL BUGS** that interact with each other:

### Bug #1: Using `len(changespec_history)` Breaks "prev" Navigation

When using `len(changespec_history)` for position calculation:

**Forward navigation works fine:**
- cs1: history=[cs1], len=1, position = 0 + 1 = 1 ✓
- cs2: history=[cs1, cs2], len=2, position = 0 + 2 = 2 ✓
- cs3: history=[cs1, cs2, cs3], len=3, position = 0 + 3 = 3 ✓

**But backward navigation breaks:**
- Show cs1: history=[cs1], position = 1 ✓
- Show cs2: history=[cs1, cs2], position = 2 ✓
- Press "p" to go back to cs1
- `select_next` decrements index: `current_changespec_index = 0`
- `select_next` retrieves cs1 from history (does NOT add to history)
- **invoke_create_cl runs with: history=[cs1, cs2] (unchanged!)**
- **Position = 0 + len([cs1, cs2]) = 2** ← WRONG! Should be 1!

The history doesn't shrink when going back, so len(history) gives the wrong position.

### Bug #2: `shown_changespec_names` Only Tracks the LAST ChangeSpec

When a workflow processes multiple ChangeSpecs in one run (all in same file), only the final ChangeSpec is tracked:

```python
# In _process_project_file, after workflow returns:
selected_changespec = final_state.get("selected_changespec", {})
shown_changespec_name = selected_changespec.get("NAME") if selected_changespec else None

# Only ONE ChangeSpec is added!
if shown_changespec_name:
    shown_changespec_names.add(shown_changespec_name)
```

**Example with one file containing cs1, cs2, cs3:**
1. Workflow starts: `shown_before_this_workflow = len(shown_changespec_names) = 0`
2. Workflow loops internally, showing cs1, cs2, cs3
3. Workflow returns with `selected_changespec = cs3` (the last one shown)
4. Only cs3 is added to `shown_changespec_names` → {cs3}

**For the next file:**
- `shown_before_this_workflow = len({cs3}) = 1` ← WRONG! Should be 3!

This causes incorrect counters when you have multiple project files.

### Bug #3: History Preservation Across Workflow Boundaries

The `changespec_history` is local to each workflow instance. When a new workflow starts (for a different project file), history resets to `[]`. This means:
- You can't use "p" to go back to ChangeSpecs from previous files
- The position calculation restarts for each file

This is actually by design, but it interacts poorly with `shown_before_this_workflow` being incorrectly calculated (Bug #2).

## The Complete Solution

We need to fix MULTIPLE issues to make this work properly:

### Fix #1: Use `current_changespec_index + 1` (Not `len(history)`)

**In `workflow_nodes.py` around line 926-941:**

```python
# Calculate global position across all project files
shown_before = state.get("shown_before_this_workflow", 0)
current_changespec_index = state.get("current_changespec_index", -1)
global_total = state.get("global_total_eligible", 0)

# CRITICAL: Use current_changespec_index, not len(changespec_history)
# current_changespec_index is ALWAYS set correctly by select_next:
# - When adding new ChangeSpec: set to len(history) - 1
# - When going back: decremented by 1
# - This gives the correct position whether navigating forward or backward
if current_changespec_index < 0:
    # Should never happen (select_next always sets it), but safety check
    current_index = shown_before + 1
else:
    # Normal case: use index (0-based) + 1 for 1-based position
    current_index = shown_before + (current_changespec_index + 1)

total_count = global_total

# Can go prev if we have at least one ChangeSpec in history before current
# (i.e., we're not at index 0 of history)
changespec_history = state.get("changespec_history", [])
can_go_prev = current_changespec_index > 0
```

**Why this works:**
- `select_next` ALWAYS sets `current_changespec_index` correctly before `invoke_create_cl` runs
- When adding new ChangeSpec: `current_changespec_index = len(changespec_history) - 1`
- When going back: `current_changespec_index` is decremented
- The index accurately reflects which position in the history we're viewing

### Fix #2: Track ALL Shown ChangeSpecs, Not Just the Last One

**In `main.py`, replace the single-ChangeSpec tracking (around line 608-620):**

**BEFORE:**
```python
# Get the name of the ChangeSpec that was shown
selected_changespec = final_state.get("selected_changespec", {})
shown_changespec_name = (
    selected_changespec.get("NAME") if selected_changespec else None
)

# Return True if at least one ChangeSpec was successfully processed
return (
    changespecs_processed > 0,
    attempted_changespecs,
    attempted_changespec_statuses,
    shown_changespec_name,
)
```

**AFTER:**
```python
# Get ALL ChangeSpecs that were shown in this workflow
# (workflow may have looped through multiple ChangeSpecs)
changespec_history = final_state.get("changespec_history", [])
shown_changespec_names_from_workflow = [
    cs.get("NAME") for cs in changespec_history if cs.get("NAME")
]

# Return True if at least one ChangeSpec was successfully processed
return (
    changespecs_processed > 0,
    attempted_changespecs,
    attempted_changespec_statuses,
    shown_changespec_names_from_workflow,  # Changed to list of names
)
```

**And update the caller (around line 363-375):**

**BEFORE:**
```python
(
    success,
    global_attempted_changespecs,
    global_attempted_changespec_statuses,
    shown_changespec_name,
) = self._process_project_file(
    project_file_str,
    global_attempted_changespecs,
    global_attempted_changespec_statuses,
    shown_changespec_names,
    global_total_eligible,
)

# Track which ChangeSpecs have been shown
if shown_changespec_name:
    shown_changespec_names.add(shown_changespec_name)
```

**AFTER:**
```python
(
    success,
    global_attempted_changespecs,
    global_attempted_changespec_statuses,
    shown_changespec_names_from_workflow,
) = self._process_project_file(
    project_file_str,
    global_attempted_changespecs,
    global_attempted_changespec_statuses,
    shown_changespec_names,
    global_total_eligible,
)

# Track ALL ChangeSpecs that were shown in this workflow
for cs_name in shown_changespec_names_from_workflow:
    shown_changespec_names.add(cs_name)
```

**Also update the method signature (around line 500):**

**BEFORE:**
```python
def _process_project_file(
    self,
    project_file: str,
    attempted_changespecs: list[str],
    attempted_changespec_statuses: dict[str, str],
    shown_changespec_names: set[str],
    global_total: int,
) -> tuple[bool, list[str], dict[str, str], str | None]:
```

**AFTER:**
```python
def _process_project_file(
    self,
    project_file: str,
    attempted_changespecs: list[str],
    attempted_changespec_statuses: dict[str, str],
    shown_changespec_names: set[str],
    global_total: int,
) -> tuple[bool, list[str], dict[str, str], list[str]]:
    """
    ...
    Returns:
        Tuple of (success, attempted_changespecs, attempted_changespec_statuses, shown_changespec_names)
        where shown_changespec_names is a LIST of names shown in this workflow
    """
```

### Fix #3: Ensure can_go_prev Logic is Consistent

The `can_go_prev` logic should check if we can navigate backward in the history:

```python
# Can go prev if we have at least one ChangeSpec in history before current position
can_go_prev = current_changespec_index > 0
```

This is correct: if index is 0, we're at the first ChangeSpec in history (can't go back). If index > 0, we can decrement to go back.

## Testing Scenarios

After implementing these fixes, test the following scenarios:

### Scenario 1: One File, Three ChangeSpecs

**Setup:** `project1.md` contains cs1, cs2, cs3

**Expected behavior:**
1. cs1 shows: **(1/3)** with NO "p" option ✓
2. Skip cs1 (press "n")
3. cs2 shows: **(2/3)** with "p" option ✓
4. Skip cs2 (press "n")
5. cs3 shows: **(3/3)** with "p" option ✓
6. Press "p" to go back
7. cs2 shows: **(2/3)** with "p" option ✓
8. Press "p" to go back
9. cs1 shows: **(1/3)** with NO "p" option ✓

### Scenario 2: Three Files, One ChangeSpec Each

**Setup:**
- `project1.md` contains cs1
- `project2.md` contains cs2
- `project3.md` contains cs3

**Expected behavior:**
1. cs1 shows: **(1/3)** with NO "p" option ✓
2. Skip cs1
3. cs2 shows: **(2/3)** with NO "p" option (can't go back across files) ✓
4. Skip cs2
5. cs3 shows: **(3/3)** with NO "p" option (can't go back across files) ✓

### Scenario 3: Two Files with Multiple ChangeSpecs

**Setup:**
- `project1.md` contains cs1, cs2
- `project2.md` contains cs3, cs4

**Expected behavior:**
1. cs1 shows: **(1/4)** with NO "p" option ✓
2. Skip cs1
3. cs2 shows: **(2/4)** with "p" option ✓
4. Skip cs2
5. cs3 shows: **(3/4)** with NO "p" option (new file, history reset) ✓
6. Skip cs3
7. cs4 shows: **(4/4)** with "p" option ✓
8. Press "p"
9. cs3 shows: **(3/4)** with NO "p" option (at start of this file's history) ✓

### Scenario 4: Mixed Navigation

**Setup:** `project1.md` contains cs1, cs2, cs3

**Expected behavior:**
1. cs1 shows: **(1/3)** ✓
2. Skip
3. cs2 shows: **(2/3)** ✓
4. Press "p"
5. cs1 shows: **(1/3)** ✓
6. Skip
7. cs2 shows: **(2/3)** ✓
8. Skip
9. cs3 shows: **(3/3)** ✓

## Why Previous Fixes Failed

### Why Fix #6 Failed (Using `current_changespec_index + 1`)

Fix #6 was actually CORRECT in using `current_changespec_index + 1`, but it likely failed because:
1. There was still a bug elsewhere (maybe in `select_next` not setting the index properly)
2. The `shown_changespec_names` bug (Bug #2) was causing issues with multiple files
3. Testing might have been done in a scenario that exposed these other bugs

### Why Fix #7 Failed (Using `len(changespec_history)`)

Fix #7 broke backward navigation with "p". While forward navigation worked, pressing "p" would show the wrong counter because the history length doesn't decrease when going back.

## Key Insights

1. **`current_changespec_index` is the source of truth** - It's maintained by `select_next` and accurately reflects the current position in history, whether navigating forward or backward.

2. **`len(changespec_history)` is NOT a reliable position indicator** - It only works for forward navigation; it breaks when going backward.

3. **Workflows can show multiple ChangeSpecs** - When a file has multiple ChangeSpecs, the workflow loops internally and shows all of them. We must track ALL of them, not just the last one.

4. **History is per-workflow** - Each workflow instance has its own history. This means "p" navigation is limited to ChangeSpecs within the current file.

## Implementation Order

1. **First**: Fix the `invoke_create_cl` logic to use `current_changespec_index + 1`
2. **Second**: Fix the `shown_changespec_names` tracking to include all ChangeSpecs from history
3. **Third**: Test all scenarios to verify the fixes work

## Potential Edge Cases to Watch For

1. **What if user quits ("q") in the middle?** - History should still be preserved up to that point
2. **What if a ChangeSpec fails?** - Should still count toward the position
3. **What if filters are applied?** - Global total might not match actual ChangeSpecs shown
4. **What if user skips all ChangeSpecs in a file?** - Next file should still have correct `shown_before` count

## Confidence Level

**HIGH** - This plan addresses the fundamental issues:
- Bug #1 (using len(history)) is definitively broken for backward navigation
- Bug #2 (tracking only last ChangeSpec) is clearly wrong for multi-ChangeSpec workflows
- The solution (using current_changespec_index + tracking all shown ChangeSpecs) is mathematically sound

The previous fixes failed because they only addressed part of the problem. This plan fixes BOTH bugs simultaneously.
