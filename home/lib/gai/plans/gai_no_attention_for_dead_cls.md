# Plan: Acknowledge Terminal Status Attention Markers

Add a new 10-second check to `gai loop` that transforms `(!: <msg>)` suffixes to `(~: <msg>)` for ChangeSpecs with terminal statuses ("Reverted" or "Submitted").

## Summary

For ChangeSpecs with STATUS = "Reverted" or "Submitted", no further action is needed. This check automatically acknowledges all attention markers across HISTORY, HOOKS, and COMMENTS entries.

---

## Implementation Steps

### Step 1: Add `suffix_type` to dataclasses

**File:** `home/lib/gai/work/changespec.py`

Add `suffix_type: str | None = None` field to:
- `HookStatusLine` dataclass (line ~108)
- `CommentEntry` dataclass (line ~208)

Values: `"error"` for `(!:)`, `"acknowledged"` for `(~:)`, `None` for plain suffix.

### Step 2: Update parsing to capture `suffix_type`

**File:** `home/lib/gai/work/changespec.py`

In `_parse_changespec_from_lines()`:
- For HOOKS parsing (~line 502-531): Capture `suffix_type` when stripping `!:` or `~:` prefix
- For COMMENTS parsing (~line 555-582): Same treatment

```python
if suffix_val.startswith("!:"):
    suffix_val = suffix_val[2:].strip()
    suffix_type_val = "error"
elif suffix_val.startswith("~:"):
    suffix_val = suffix_val[2:].strip()
    suffix_type_val = "acknowledged"
else:
    suffix_type_val = None
```

### Step 3: Update formatting to use `suffix_type`

**File:** `home/lib/gai/work/hooks/operations.py` (~line 69-75)

```python
if sl.suffix:
    if sl.suffix_type == "error" or (sl.suffix_type is None and is_error_suffix(sl.suffix)):
        line_parts.append(f" - (!: {sl.suffix})")
    elif sl.suffix_type == "acknowledged" or (sl.suffix_type is None and is_acknowledged_suffix(sl.suffix)):
        line_parts.append(f" - (~: {sl.suffix})")
    else:
        line_parts.append(f" - ({sl.suffix})")
```

**File:** `home/lib/gai/work/comments/operations.py` (~line 62-70)

Similar logic for comment suffix formatting.

### Step 4: Create update functions

**File:** `home/lib/gai/work/hooks/operations.py`

Add `update_hook_status_line_suffix_type()` function to transform a specific hook status line's suffix_type from "error" to "acknowledged".

**File:** `home/lib/gai/work/comments/operations.py`

Add `update_comment_suffix_type()` function to transform a specific comment entry's suffix_type from "error" to "acknowledged".

### Step 5: Add new method to LoopWorkflow

**File:** `home/lib/gai/work/loop/core.py`

Add `_acknowledge_terminal_status_markers()` method:

```python
def _acknowledge_terminal_status_markers(self, changespec: ChangeSpec) -> list[str]:
    """Transform error suffixes to acknowledged for terminal status ChangeSpecs."""
    updates: list[str] = []

    if changespec.status not in ("Reverted", "Submitted"):
        return updates

    # Process HISTORY entries with suffix_type == "error"
    # Use existing update_history_entry_suffix(..., "acknowledged")

    # Process HOOKS entries with suffix_type == "error"
    # Use new update_hook_status_line_suffix_type()

    # Process COMMENTS entries with suffix_type == "error"
    # Use new update_comment_suffix_type()

    return updates
```

### Step 6: Integrate into `_run_hooks_cycle()`

**File:** `home/lib/gai/work/loop/core.py` (~line 567)

Add after `_transform_old_proposal_suffixes()` call:

```python
# Acknowledge terminal status attention markers (!: -> ~:)
acknowledge_updates = self._acknowledge_terminal_status_markers(changespec)
updates.extend(acknowledge_updates)
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `home/lib/gai/work/changespec.py` | Add `suffix_type` to `HookStatusLine` and `CommentEntry`; update parsing |
| `home/lib/gai/work/hooks/operations.py` | Add `update_hook_status_line_suffix_type()`; update `_format_hooks_field()` |
| `home/lib/gai/work/comments/operations.py` | Add `update_comment_suffix_type()`; update `_format_comments_field()` |
| `home/lib/gai/work/loop/core.py` | Add `_acknowledge_terminal_status_markers()`; call from `_run_hooks_cycle()` |
| `home/lib/gai/test/test_loop.py` | Add tests for new functionality |

---

## Test Coverage

1. Test `_acknowledge_terminal_status_markers` transforms HISTORY error suffixes for terminal status
2. Test `_acknowledge_terminal_status_markers` transforms HOOKS error suffixes for terminal status
3. Test `_acknowledge_terminal_status_markers` transforms COMMENTS error suffixes for terminal status
4. Test skips non-terminal statuses (Drafted, Mailed)
5. Test skips already-acknowledged suffixes
6. Test parsing preserves `suffix_type` for HOOKS and COMMENTS
7. Test formatting respects `suffix_type`
