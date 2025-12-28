# Plan: Add Summarize-Hook Workflow for Proposed Entry Failures

## Overview

Add a new 10-second check to `gai loop` that detects FAILED hooks with proposed HISTORY entry IDs (e.g., "1a", "2b") and runs an async summarize workflow to add a failure summary suffix instead of triggering fix-hook.

## Key Design Decisions

1. **No workspace needed** - summarize-hook only reads the hook output file, no file changes required
2. **Simpler than fix-hook** - no `bb_hg_update`, no workspace claiming
3. **Async execution** - runs in background like fix-hook (per user preference)
4. **Immediate detection** - triggers as soon as eligible hook is detected (per user preference)

## Files to Modify

### 1. `home/lib/gai/work/hooks/operations.py`

**Add new function** `get_failing_hooks_for_summarize()`:
```python
def get_failing_hooks_for_summarize(hooks: list[HookEntry]) -> list[HookEntry]:
    """Get failing hooks eligible for summarize-hook (proposal entries, no suffix)."""
```
- Check `sl.status == "FAILED"`
- Check `_is_proposal_entry(sl.history_entry_num)` (import from `.core`)
- Check `sl.suffix is None`

**Modify** `get_failing_hooks_for_fix()` (line 443-449):
- Add condition to EXCLUDE proposal entries: `not _is_proposal_entry(sl.history_entry_num)`

### 2. `home/lib/gai/work/hooks/__init__.py`

Export `get_failing_hooks_for_summarize`.

### 3. `home/lib/gai/work/loop/workflows_runner.py`

**Add functions:**

- `_summarize_hook_workflow_eligible(changespec)` - returns eligible hooks
- `_start_summarize_hook_workflow(changespec, hook, log)` - starts background process
  - Sets timestamp suffix on hook
  - Starts `loop_summarize_hook_runner.py` as background process
  - No workspace claiming needed
- `_get_running_summarize_hook_workflows(changespec)` - finds hooks with timestamp suffix on proposal entries

**Modify:**

- `start_stale_workflows()` (line 381) - add loop for summarize-hook after fix-hook
- `check_and_complete_workflows()` (line 568) - add completion check for summarize-hook
  - On completion: suffix already updated by runner script
  - On failure: set fallback suffix "Hook Command Failed"

### 4. `home/lib/gai/loop_summarize_hook_runner.py` (NEW)

Simplified runner script (no workspace needed):
```python
#!/usr/bin/env python3
"""Standalone summarize-hook workflow runner."""

# Args: changespec_name, project_file, hook_command, hook_output_path, output_file

# 1. Call get_file_summary() on hook_output_path
# 2. Re-read project file to get current hooks
# 3. Call set_hook_suffix() with the summary
# 4. Write WORKFLOW_COMPLETE marker
```

### 5. `home/lib/gai/test/test_summarize_hook.py` (NEW)

Tests for:
- `get_failing_hooks_for_summarize()` - proposal entries eligible
- `get_failing_hooks_for_summarize()` - regular entries NOT eligible
- `get_failing_hooks_for_summarize()` - hooks with suffix NOT eligible
- `get_failing_hooks_for_fix()` - proposal entries excluded

## Implementation Steps

1. Add `get_failing_hooks_for_summarize()` in `operations.py`
2. Modify `get_failing_hooks_for_fix()` to exclude proposal entries
3. Export new function in `__init__.py`
4. Create `loop_summarize_hook_runner.py` script
5. Add summarize-hook workflow functions to `workflows_runner.py`
6. Update `start_stale_workflows()` to start summarize-hook workflows
7. Update `check_and_complete_workflows()` to handle summarize-hook completion
8. Add tests in `test_summarize_hook.py`
9. Run `make fix`, `make lint`, `make test`
