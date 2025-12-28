# Plan: Proposal Suffix Handling for GAI System

## Overview

Add three features:
1. **Add `- (!: NEW PROPOSAL)` suffix** to proposed HISTORY entries via `gai amend --propose`
2. **Add `- (~: <msg>)` "acknowledged" suffix** with parsing, display, and syntax highlighting (yellow/orange)
3. **Transform old proposals' suffixes** from `(!:)` to `(~:)` every 10s in `gai loop`

"Old proposal" = entry `(Na)` where N < latest regular entry number (e.g., if `(3)` exists, then `(2a)` is old but `(3a)` is current).

---

## Part 1: Add `(!: NEW PROPOSAL)` Suffix

### File: `home/lib/gai/history_utils.py`

**Modify `add_proposed_history_entry()` (line 249):**

```python
# Current:
entry_lines = [f"  ({entry_id}) {note}\n"]

# Change to:
entry_lines = [f"  ({entry_id}) {note} - (!: NEW PROPOSAL)\n"]
```

Note: `gai commit` uses `add_history_entry()` for `(1)` entries - no change needed there.

---

## Part 2: Support `(~: <msg>)` Acknowledged Suffix

### File: `home/lib/gai/work/changespec.py`

1. **Add constants and helper (after line 31):**
   ```python
   ACKNOWLEDGED_SUFFIX_MESSAGES = frozenset({"NEW PROPOSAL"})

   def is_acknowledged_suffix(suffix: str | None) -> bool:
       return suffix is not None and suffix in ACKNOWLEDGED_SUFFIX_MESSAGES
   ```

2. **Add fields to `HistoryEntry` dataclass (line 35):**
   ```python
   suffix: str | None = None  # e.g., "NEW PROPOSAL"
   suffix_type: str | None = None  # "error" for !:, "acknowledged" for ~:
   ```

3. **Update history parsing (line 545)** to extract suffix from note:
   - Pattern: `\s+-\s+\((!:|~:)?\s*([^)]+)\)$`
   - Store `suffix`, `suffix_type`, and `note` (without suffix)

4. **Update `_build_history_entry()` (line 203)** to include suffix fields

5. **Update hook status line parsing (line 479-481)** to handle `~:` prefix

### File: `home/lib/gai/work/display.py`

1. **Add import:** `is_acknowledged_suffix`

2. **Update HISTORY entry display** to show suffixes:
   - Error (`!:`): `style="bold white on #AF0000"` (red bg)
   - Acknowledged (`~:`): `style="bold #FFAF00"` (yellow/orange)

3. **Update hook/comment suffix display** for acknowledged type

### File: `home/lib/gai/work/hooks/operations.py`

1. **Add import:** `is_acknowledged_suffix`

2. **Update `_format_hooks_field()` (line 68-72):**
   ```python
   if is_error_suffix(sl.suffix):
       line_parts.append(f" - (!: {sl.suffix})")
   elif is_acknowledged_suffix(sl.suffix):
       line_parts.append(f" - (~: {sl.suffix})")
   else:
       line_parts.append(f" - ({sl.suffix})")
   ```

### File: `home/dot_config/nvim/syntax/gaiproject.vim`

1. **Add HISTORY suffix patterns (after line 141):**
   ```vim
   syn match GaiProjectHistorySuffixError " - (!:\s*[^)]\+)" contained
   syn match GaiProjectHistorySuffixAcknowledged " - (~:\s*[^)]\+)" contained
   highlight GaiProjectHistorySuffixError gui=bold guifg=#FFFFFF guibg=#AF0000
   highlight GaiProjectHistorySuffixAcknowledged gui=bold guifg=#FFAF00
   ```

2. **Update HISTORY entry patterns (lines 137, 140)** to include suffix groups

3. **Add hook suffix pattern (after line 179):**
   ```vim
   syn match GaiProjectHooksSuffixAcknowledged "(~:\s*[^)]\+)" contained
   highlight GaiProjectHooksSuffixAcknowledged gui=bold guifg=#FFAF00
   ```

4. **Update hook status line pattern (line 167)** to include acknowledged suffix

5. **Add comment suffix pattern (after line 207):**
   ```vim
   syn match GaiProjectCommentsSuffixAcknowledged "(~:\s*[^)]\+)" contained
   highlight GaiProjectCommentsSuffixAcknowledged gui=bold guifg=#FFAF00
   ```

6. **Update comment entry pattern (line 200)** to include acknowledged suffix

---

## Part 3: Transform Old Proposals in Loop

### File: `home/lib/gai/history_utils.py`

**Add new function:**
```python
def update_history_entry_suffix(
    project_file: str,
    cl_name: str,
    entry_id: str,
    new_suffix: str,
    new_suffix_type: str,
) -> bool:
    """Update the suffix of a HISTORY entry."""
    # Read file, find entry, replace (!: MSG) with (~: MSG), write back
```

### File: `home/lib/gai/work/loop/core.py`

1. **Add import:** `update_history_entry_suffix`

2. **Add method `_transform_old_proposal_suffixes()`:**
   - Get last regular history number
   - For each proposed entry where `entry.number < last_regular_num`:
     - If `entry.suffix_type == "error"`: transform to acknowledged
   - For each hook status line with old proposal entry ID:
     - If has error suffix: transform to acknowledged

3. **Call from `_run_hooks_cycle()` (after line 508):**
   ```python
   transform_updates = self._transform_old_proposal_suffixes(changespec)
   updates.extend(transform_updates)
   ```

---

## Files to Modify

| File | Changes |
|------|---------|
| `home/lib/gai/history_utils.py` | Add `(!: NEW PROPOSAL)` suffix; add `update_history_entry_suffix()` |
| `home/lib/gai/work/changespec.py` | Add `ACKNOWLEDGED_SUFFIX_MESSAGES`, `is_acknowledged_suffix()`, `HistoryEntry.suffix/suffix_type`, update parsing |
| `home/lib/gai/work/display.py` | Add acknowledged suffix styling (yellow/orange) |
| `home/lib/gai/work/hooks/operations.py` | Format `(~: MSG)` for acknowledged suffixes |
| `home/lib/gai/work/loop/core.py` | Add `_transform_old_proposal_suffixes()` method |
| `home/dot_config/nvim/syntax/gaiproject.vim` | Add `~:` syntax patterns with yellow/orange highlighting |

---

## Testing Checklist

- [ ] `gai amend --propose "test"` creates entry with `- (!: NEW PROPOSAL)` suffix
- [ ] `gai work` displays `(!:)` in red, `(~:)` in yellow/orange
- [ ] Vim shows correct syntax highlighting for both suffix types
- [ ] `gai loop` transforms old proposal suffixes after 10s when new regular entry exists
- [ ] Hook status lines for old proposals also get transformed
