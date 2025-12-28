# Plan: Improve critique_comments Script

## Summary
Rename `--gai`/`#gai` to `--me`/`#me` and add `#no` tag support to filter out comment threads.

## Files to Modify

### 1. `home/bin/executable_critique_comments`

**Changes:**
- Rename `gai_mode` variable to `me_mode`
- Rename `--gai` option to `--me`
- Replace `#gai` with `#me` in all jq filters
- Update comments to say "me mode" instead of "GAI mode"
- Add `#no` filter: When `--me` is specified and the last reply (`.reply[-1].content`) contains `#no`, exclude that comment from output

**Updated jq filter logic (me mode):**
```jq
.comment as $comments |
if ($comments | any(.content | test("#me"))) then
  $comments
  | sort_by(.depot_path, .line_number)[]
  | select(.resolved != true)
  | select((.reply | length == 0) or (.reply[-1].content | test("#no") | not))
  | .content |= (gsub("#me "; "") | gsub(" #me"; "") | gsub("#me"; ""))
else
  empty
end
```

### 2. `home/lib/gai/search/loop/checks_runner.py`

**Changes:**
- Line 225: Update docstring from `--gai` to `--me`
- Line 242: Change `critique_comments --gai` to `critique_comments --me`
- Line 487: Update docstring from `--gai` to `--me`
- Line 503: Update log message from `--gai` to `--me`

## Implementation Order
1. Update `executable_critique_comments` with all changes
2. Update `checks_runner.py` with all changes
3. Run `make fix && make lint && make test`
4. Run `chezmoi apply`
