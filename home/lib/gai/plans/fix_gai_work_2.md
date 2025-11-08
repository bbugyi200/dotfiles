# Fix Plan #2: `gai work` Counter Still Showing (1/1) Instead of (1/3, 2/3, 3/3)

## Problem

After the first fix, the output still shows:
- First ChangeSpec (ilar): "Available options **(1/1)**:" - should be "(1/3)"
- Second ChangeSpec (pat): "Available options **(1/1)**:" - should be "(2/3)" with "p" option
- Third ChangeSpec (yserve): "Available options **(1/1)**:" - should be "(3/3)" with "p" option

The "p" (prev) option is still not showing.

## Root Cause Analysis

### Architecture Misunderstanding

The workflow architecture is:
1. Main loop in `main.py` iterates over **multiple project files** (ilar.md, pat.md, yserve.md)
2. For each project file, it calls `_process_project_file()` which creates a **new workflow instance**
3. Each workflow instance processes **one ChangeSpec** then returns
4. The outer loop tracks global state via `shown_changespec_names` set and passes `global_total_eligible`

### Why My First Fix Failed

I changed the code to use:
```python
current_changespec_index = state.get("current_changespec_index", -1)  # Always 0 for first CS in workflow
total_eligible = state.get("total_eligible_changespecs", 0)  # PER-FILE count!
current_index = current_changespec_index + 1  # Always 1
total_count = total_eligible  # Per-file total, not global!
```

The bug is that `total_eligible_changespecs` is calculated **per-file** in `select_next_changespec`:

```python
# In select_next_changespec (line 835):
total_eligible = _count_eligible_changespecs(
    changespecs,  # <-- Only changespecs from THIS file!
    attempted_changespecs,
    include_filters
)
```

So for each project file with 1 ChangeSpec:
- ilar.md: `total_eligible_changespecs = 1` (only counts ilar ChangeSpec)
- pat.md: `total_eligible_changespecs = 1` (only counts pat ChangeSpec)
- yserve.md: `total_eligible_changespecs = 1` (only counts yserve ChangeSpec)

This gives us `(1/1)` for each!

### The Correct Global State Variables

Looking at `main.py` and `_process_project_file`, there ARE global state variables available:

1. **`shown_before_this_workflow`**: Number of ChangeSpecs shown before this workflow started
   - Set in `_process_project_file` line 551: `shown_before_this_workflow = len(shown_changespec_names)`
   - First call: 0 (nothing shown yet)
   - Second call: 1 (ilar was shown)
   - Third call: 2 (ilar and pat were shown)

2. **`global_total_eligible`**: Total eligible ChangeSpecs across **all** project files
   - Calculated in main.py line 316: `global_total_eligible = self._count_total_eligible_across_all_files(...)`
   - Should be 3 (ilar, pat, yserve)

3. **`current_changespec_index`**: Position within the current workflow's history
   - For the first ChangeSpec in each workflow: 0
   - For subsequent ChangeSpecs within same workflow (if user goes back/forward): 1, 2, etc.

### The Correct Calculation

For global position across all project files:
```python
global_position = shown_before_this_workflow + (current_changespec_index + 1)
```

Examples:
- First workflow (ilar): shown_before=0, index=0, position = 0 + (0+1) = 1 ✓
- Second workflow (pat): shown_before=1, index=0, position = 1 + (0+1) = 2 ✓
- Third workflow (yserve): shown_before=2, index=0, position = 2 + (0+1) = 3 ✓

For the "prev" option, we can only go back if we're past position 1 globally:
```python
can_go_prev = global_position > 1
```

Examples:
- First workflow: position=1, can_prev = 1 > 1 = False ✓
- Second workflow: position=2, can_prev = 2 > 1 = True ✓
- Third workflow: position=3, can_prev = 3 > 1 = True ✓

## The Correct Fix

### File: `home/lib/gai/work_projects_workflow/workflow_nodes.py`

**Location**: Lines 926-936 in `invoke_create_cl` function

**Replace:**
```python
# Calculate position within this workflow's ChangeSpec history
# current_changespec_index is 0-based (0 = first ChangeSpec, 1 = second, etc.)
current_changespec_index = state.get("current_changespec_index", -1)
total_eligible = state.get("total_eligible_changespecs", 0)

# Position is 1-based for display (1/3, 2/3, 3/3)
current_index = (
    current_changespec_index + 1 if current_changespec_index >= 0 else 0
)
total_count = total_eligible

# Can go prev if we have at least one ChangeSpec in history before the current one
can_go_prev = current_changespec_index > 0
```

**With:**
```python
# Calculate global position across all project files
shown_before = state.get("shown_before_this_workflow", 0)
current_changespec_index = state.get("current_changespec_index", -1)
global_total = state.get("global_total_eligible", 0)

# Global position is: ChangeSpecs shown before this workflow + current position in this workflow
# current_changespec_index is 0-based, so add 1 for 1-based display position
global_position = shown_before + (current_changespec_index + 1)

# Use global counts for display
current_index = global_position
total_count = global_total

# Can go prev if we're past the first ChangeSpec globally
can_go_prev = global_position > 1
```

## Why This Fix Is Correct

### Counter Display
- **First ChangeSpec (ilar)**: shown_before=0, index=0 → position = 0 + 1 = 1, total = 3 → **(1/3)** ✓
- **Second ChangeSpec (pat)**: shown_before=1, index=0 → position = 1 + 1 = 2, total = 3 → **(2/3)** ✓
- **Third ChangeSpec (yserve)**: shown_before=2, index=0 → position = 2 + 1 = 3, total = 3 → **(3/3)** ✓

### "p" (prev) Option
- **First ChangeSpec**: position=1, can_prev = (1 > 1) = False → NO "p" option ✓
- **Second ChangeSpec**: position=2, can_prev = (2 > 1) = True → "p" option shown ✓
- **Third ChangeSpec**: position=3, can_prev = (3 > 1) = True → "p" option shown ✓

## Potential Issue: Global Total Recalculation

There's a potential secondary issue in `main.py` line 316 where `global_total_eligible` is recalculated on each iteration:

```python
while True:
    for project_file in project_files:
        # Recalculated on each iteration!
        global_total_eligible = self._count_total_eligible_across_all_files(
            project_files, global_attempted_changespecs
        )
```

This means the total decreases as ChangeSpecs are attempted. However, looking at the code more carefully:

- `_count_total_eligible_across_all_files` excludes ChangeSpecs in `attempted_changespecs`
- After showing a ChangeSpec, it's added to `attempted_changespecs`
- So the total would decrease: 3 → 2 → 1

This could cause:
- First: (1/3) ✓
- Second: (2/2) ✗ (should be 2/3)
- Third: (3/1) ✗ (should be 3/3)

### Solution for Global Total Issue

We need to calculate `global_total_eligible` ONCE at the start, not recalculate it:

**File**: `home/lib/gai/work_projects_workflow/main.py`

**Location**: Around line 301-318

**Change from:**
```python
try:
    # Loop until all ChangeSpecs in all project files are in unworkable states
    while True:
        workable_found = False
        iteration_start_count = total_processed

        # Count total eligible ChangeSpecs across all project files
        global_total_eligible = self._count_total_eligible_across_all_files(
            project_files, global_attempted_changespecs
        )
```

**To:**
```python
# Calculate the initial total eligible count ONCE at the start
# This represents the total number of ChangeSpecs we'll show to the user
global_total_eligible = self._count_total_eligible_across_all_files(
    project_files, global_attempted_changespecs
)

try:
    # Loop until all ChangeSpecs in all project files are in unworkable states
    while True:
        workable_found = False
        iteration_start_count = total_processed

        # Don't recalculate - use the initial total for consistent counter display
```

## Summary of Changes

1. **workflow_nodes.py (line 926-936)**: Use global position calculation instead of per-workflow
2. **main.py (line ~301-318)**: Calculate `global_total_eligible` once, not on each iteration

## Testing Plan

After implementing these changes:

1. Run `gai work` on a setup with 3 ChangeSpecs across 3 project files
2. Verify the counter shows:
   - First ChangeSpec: "(1/3)" with NO "p" option
   - Second ChangeSpec: "(2/3)" with "p" option
   - Third ChangeSpec: "(3/3)" with "p" option
3. Test that the "p" option works correctly to navigate backwards
4. Run quality checks (make fix, make lint, make test, chezmoi apply)
