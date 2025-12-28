---
prompt: |
  ultrathink: Can you help me make the following changes?
  + Start using "- (!: <msg>)" where <msg> is some arbitrary message (ideally a useful description of what the user needs to act on) instead of the "- (!)" suffix.
  + Stop using the proposal ID for CommentEntry. Instead, switch this to "- (!: Unresolved Critique Comments)".
  + Make sure to add good syntax highlighting for the new "- (!: <msg>)" syntax with a red background. Make sure the <msg> and the entire suffix (except for the dash) is VERY visible and stands out to the user.
  + Start using "- (!: ZOMBIE)" instead of the "- (ZOMBIE)" suffix.
  + HookStatusLine should also support "- (!: ZOMBIE)"! Start checking for zombies from `gai loop`!
  + Try to switch every existing "- (!)" use case over to "- (!: <msg>)" when you can think of a good <msg>; otherwise, use "- (!: ATTENTION)".
---

# Plan: Refactor ChangeSpec Suffix System to "(!: <msg>)" Format

## Summary

Refactor the suffix system from "- (!)" and "- (ZOMBIE)" to "- (!: <msg>)" format with red background highlighting for maximum visibility.

## Key Design Decisions

1. **Storage**: Store just the message (e.g., "ZOMBIE"), add "!: " prefix when formatting/displaying
2. **Timestamps**: Keep unchanged - only error suffixes get the "!: " prefix
3. **Backward compatibility**: Not needed - only parse new format
4. **Error suffix detection**: Create helper to identify error suffixes that need "!: " prefix

## Error Suffix Messages

| Context | Old Suffix | New Message |
|---------|------------|-------------|
| HookStatusLine - hook failed | `!` | `Hook Command Failed` |
| HookStatusLine - stale fix-hook | `ZOMBIE` | `ZOMBIE` |
| CommentEntry - CRS failed/rejected | `!` or `2a` | `Unresolved Critique Comments` |
| CommentEntry - stale CRS | `ZOMBIE` | `ZOMBIE` |

## Files to Modify

### 1. Core Helper (`work/changespec.py`)

Add at module level (after imports):
```python
ERROR_SUFFIX_MESSAGES = frozenset({
    "ZOMBIE",
    "Hook Command Failed",
    "Unresolved Critique Comments",
})

def is_error_suffix(suffix: str | None) -> bool:
    """Check if suffix requires '!: ' prefix."""
    return suffix is not None and suffix in ERROR_SUFFIX_MESSAGES
```

Update dataclass docstrings:
- `HookStatusLine` (lines 57-74): Update suffix documentation
- `CommentEntry` (lines 151-168): Remove proposal ID mention

Update parsing (lines 432-452):
- After `suffix_val = new_status_match.group(6)`, strip "!: " prefix:
  ```python
  if suffix_val and suffix_val.startswith("!:"):
      suffix_val = suffix_val[2:].strip()
  ```

Update parsing (lines 487-499):
- After `suffix_val = comment_match.group(3)`, strip "!: " prefix

### 2. Hook Formatting (`work/hooks/operations.py`)

Update `_format_hooks_field()` (lines 67-68):
```python
if sl.suffix:
    if is_error_suffix(sl.suffix):
        line_parts.append(f" - (!: {sl.suffix})")
    else:
        line_parts.append(f" - ({sl.suffix})")
```

Import `is_error_suffix` from `changespec`.

### 3. Comment Formatting (`work/comments/operations.py`)

Update `_format_comments_field()` (lines 62-67):
```python
if comment.suffix:
    if is_error_suffix(comment.suffix):
        lines.append(f"  [{comment.reviewer}] {comment.file_path} - (!: {comment.suffix})\n")
    else:
        lines.append(f"  [{comment.reviewer}] {comment.file_path} - ({comment.suffix})\n")
```

Import `is_error_suffix` from `changespec`.

### 4. Display Styling (`work/display.py`)

Update hook suffix display (lines 329-336):
```python
if sl.suffix:
    text.append(" - ")
    if is_error_suffix(sl.suffix):
        # Red background with white text for maximum visibility
        text.append(f"(!: {sl.suffix})", style="bold white on #AF0000")
    elif _is_suffix_timestamp(sl.suffix):
        text.append(f"({sl.suffix})", style="bold #D75F87")
    else:
        text.append(f"({sl.suffix})")
```

Update comment suffix display (lines 360-368):
```python
if comment.suffix:
    text.append(" - ")
    if is_error_suffix(comment.suffix):
        text.append(f"(!: {comment.suffix})", style="bold white on #AF0000")
    elif _is_suffix_timestamp(comment.suffix):
        text.append(f"({comment.suffix})", style="bold #D75F87")
    else:
        text.append(f"({comment.suffix})")
```

Import `is_error_suffix` from `changespec`.

### 5. CRS Workflow (`work/workflows/crs.py`)

Update suffix values:
- Line 189: Change `proposal_id` to `"Unresolved Critique Comments"`
- Line 209: Change `"!"` to `"Unresolved Critique Comments"`
- Lines 217-231: On success, clear suffix (remove proposal_id logic)

### 6. Comments Core (`work/comments/core.py`)

Update `is_timestamp_suffix()` (lines 32-57):
- Change `suffix in ("!", "ZOMBIE")` to `is_error_suffix(suffix)`

Import `is_error_suffix` from `changespec`.

### 7. Zombie Detection (`work/loop/comments_handler.py`)

No changes needed - already sets "ZOMBIE" (just the message).

### 8. Hook Zombie Detection (`work/loop/core.py`)

Already sets "ZOMBIE" as suffix at line 340. No changes needed.

### 9. Tests

**`test/test_comments.py`**:
- Update test cases with new format `(!: ZOMBIE)`, `(!: Unresolved Critique Comments)`
- Add tests for `is_error_suffix()` function
- Remove proposal ID tests

**`test/test_hooks.py`**:
- Update test cases with new format `(!: ZOMBIE)`, `(!: Hook Command Failed)`
- Add tests for hook suffix formatting

## Implementation Order

1. Add `is_error_suffix()` helper and `ERROR_SUFFIX_MESSAGES` to `changespec.py`
2. Update parsing in `changespec.py` to strip "!: " prefix
3. Update formatting in `hooks/operations.py` and `comments/operations.py`
4. Update display styling in `display.py` (red background)
5. Update `is_timestamp_suffix()` in `comments/core.py`
6. Update CRS workflow to use new messages and remove proposal ID logic
7. Update tests
8. Run `make fix && make lint && make test`
