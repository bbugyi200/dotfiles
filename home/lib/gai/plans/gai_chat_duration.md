# Plan: Add Duration Suffix to HISTORY CHAT Lines

## Summary
Add a " (XhYmZs)" suffix to `| CHAT:` lines in HISTORY entries to show how long the associated agent took to run. Duration is calculated from the timestamp embedded in the chat filename to when the HISTORY entry is created.

**Example transformation:**
```
      | CHAT: ~/.gai/chats/mybranch-fix_tests-251227_143052.md
```
Becomes:
```
      | CHAT: ~/.gai/chats/mybranch-fix_tests-251227_143052.md (1m23s)
```

Duration format shortens when possible: `(1h2m3s)` → `(2m30s)` → `(45s)`

---

## Files to Modify

### 1. `/Users/bbugyi/.local/share/chezmoi/home/lib/gai/history_utils.py`

**Add two helper functions:**

```python
def _extract_timestamp_from_chat_path(chat_path: str) -> str | None:
    """Extract timestamp from chat file path (last 13 chars before .md)."""
    # Returns timestamp like "251227_143052" or None if extraction fails

def _format_chat_line_with_duration(chat_path: str) -> str:
    """Format CHAT line with duration suffix, gracefully falling back if extraction fails."""
    # Uses existing format_duration() and calculate_duration_from_timestamps()
    # from search/hooks/core.py
```

**Modify two functions:**

1. `add_history_entry()` (line ~413):
   - Change: `entry_lines.append(f"      | CHAT: {chat_path}\n")`
   - To: `entry_lines.append(_format_chat_line_with_duration(chat_path))`

2. `add_proposed_history_entry()` (line ~252):
   - Same change as above

### 2. `/Users/bbugyi/.local/share/chezmoi/home/lib/gai/test/test_history.py`

**Add tests for:**
- `_extract_timestamp_from_chat_path()` - valid paths, paths with agent names, invalid paths, short filenames
- `_format_chat_line_with_duration()` - valid output, fallback behavior
- Integration test for `add_history_entry()` with duration suffix

---

## Implementation Details

### Timestamp Extraction Logic
Chat filenames follow: `<branch>-<workflow>[-<agent>]-<timestamp>.md`
- Timestamp is always last 13 chars before `.md` (format: `YYmmdd_HHMMSS`)
- Validate: 6 digits + underscore + 6 digits

### Duration Calculation
- Start time: extracted from chat filename timestamp
- End time: current time (via `generate_timestamp()`)
- Use existing `calculate_duration_from_timestamps()` from `search/hooks/core.py`
- Format with existing `format_duration()` - already handles shortening (omits hours/minutes when 0)

### Error Handling
- If timestamp extraction fails → return line without duration suffix
- If duration calculation fails or returns negative → return line without duration suffix
- No exceptions raised; graceful degradation

---

## Existing Utilities to Reuse

| Function | Location | Purpose |
|----------|----------|---------|
| `format_duration(seconds)` | `search/hooks/core.py:18` | Formats to "XhYmZs"/"YmZs"/"Zs" |
| `calculate_duration_from_timestamps(start, end)` | `search/hooks/core.py:138` | Returns duration in seconds |
| `generate_timestamp()` | `gai_utils.py:14` | Current timestamp (already imported) |
