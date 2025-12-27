---
prompt: |
  Great! Can you now have `gai loop` run a periodic (every 5m) check for #gai comments by running the `critique_comments
  --gai <cl_name>` command?
  + When comments are returned for a ChangeSpec, we should add a new `[author]`
  `~/.gai/comments/<name>-author-YYmmdd_HHMMSS.json"` entry to the COMMENTS field.
  + When this field is present, we should make the "r" (run crs) option visible. If selected, we should run the crs
  workflow the same we would a `[reviewer]` COMMENTS entry.
  + This should be run on ALL "Drafted" or "Mailed" ChangeSpec as long as they have no `[reviewer]` or `[author]` COMMENTS
  yet.
  + We should also add a periodic check that removes this comments entry if that command returns no output. This is
  similar to what we do for the `[reviewer]` COMMENTS entry.
---

# Plan: Add #gai Comment Detection to gai loop

## Summary

Add periodic detection of `#gai` author comments to the loop workflow, enabling CRS workflow for self-addressed comments.

## Requirements

1. **Periodic check (5 min)**: Run `critique_comments --gai <cl_name>` for eligible ChangeSpecs
2. **Eligibility**: Status is "Drafted" or "Mailed", AND no `[reviewer]` entry exists
3. **When comments found**: Save to `~/.gai/comments/<name>-author-<timestamp>.json`, add `[author]` entry
4. **CRS availability**: Make "r" option visible when `[author]` entry has no suffix
5. **CRS execution**: Reuse same CRS workflow, parameterized with "author" type
6. **Cleanup**: Remove `[author]` entry when `critique_comments --gai` returns no output

---

## Implementation Steps

### 1. Add `_check_author_comments()` to loop/core.py

**File**: `home/lib/gai/work/loop/core.py`

Add new method after `_check_comments()` (~line 243):

```python
def _check_author_comments(self, changespec: ChangeSpec) -> list[str]:
    """Check for #gai author comments and manage [author] COMMENTS entries."""
```

**Logic**:
- Skip if status not in ("Drafted", "Mailed")
- Skip if any `[reviewer]` entry exists
- Run `subprocess.run(["critique_comments", "--gai", changespec.name], ...)`
- If output exists and no `[author]` entry: create file, add entry
- If no output and `[author]` entry with no suffix: remove entry

### 2. Integrate into loop cycle

**File**: `home/lib/gai/work/loop/core.py`

Modify `_run_check_cycle()` (~line 565-566):

```python
# After existing comment checks
author_comment_updates = self._check_author_comments(changespec)
updates.extend(author_comment_updates)
```

### 3. Update `get_available_workflows()` for [author] entries

**File**: `home/lib/gai/work/operations.py` (lines 104-109)

Change:
```python
if entry.reviewer == "reviewer" and entry.suffix is None:
```
To:
```python
if entry.reviewer in ("reviewer", "author") and entry.suffix is None:
```

### 4. Update `handle_run_crs_workflow()` handler

**File**: `home/lib/gai/work/handlers/workflow_handlers.py` (lines 186-195)

- Find entry matching `reviewer in ("reviewer", "author")` with `suffix=None`
- Pass `comment_reviewer` type to `run_crs_workflow()`

### 5. Parameterize `run_crs_workflow()` with comment type

**File**: `home/lib/gai/work/workflows/crs.py`

- Add parameter: `comment_reviewer: str = "reviewer"`
- Replace all hardcoded `"reviewer"` in `set_comment_suffix()` calls (lines 102, 122, 148, 163, 183, 194) with `comment_reviewer`

### 6. Add tests

**File**: `home/lib/gai/work/loop/test/test_loop.py` (new tests)

Test cases:
- `_check_author_comments()` skips non-Drafted/Mailed status
- `_check_author_comments()` skips when `[reviewer]` entry exists
- Creates `[author]` entry when `#gai` comments found
- Removes `[author]` entry when no comments and no suffix

---

## Files to Modify

| File | Changes |
|------|---------|
| `home/lib/gai/work/loop/core.py` | Add `_check_author_comments()`, integrate into cycle |
| `home/lib/gai/work/operations.py` | Update `get_available_workflows()` for `[author]` |
| `home/lib/gai/work/handlers/workflow_handlers.py` | Pass `comment_reviewer` to CRS |
| `home/lib/gai/work/workflows/crs.py` | Parameterize with `comment_reviewer` |
| `home/lib/gai/work/loop/test/test_loop.py` | Add tests for author comments |

---

## Notes

- The existing `_check_comment_zombies()` already works generically for all comment entries
- No changes needed to `CommentEntry` dataclass - "author" is just a different `reviewer` value
- The `critique_comments --gai` command was already added in the previous task
