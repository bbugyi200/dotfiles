---
prompt: |
  Can you help me change the way that `gai` handles Critique comments (code review comments)?
  + Currently we use the "Changes Requested" gai ChangeSpec STATUS field value to indicate that there are unresolved
  Critique comments.
  + I would like to start tracking this by adding a new optional COMMENTS field to the ChangeSpec. When `gai loop` finds
  comments (by running the `critique_comments` check), it should add a new entry to the COMMENTS field (and add the
  COMMENTS field if it doesn't yet exist).
  + The COMMENTS field should have the following form:
    ```
    COMMENTS:
      [reviewer] ~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json
    ```
    where `~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json` should contain the output of the `critique_comments`
    command and `<name>` is the name of the ChangeSpec.
  + The `gai loop` Command also has a check that changes the status from "Changes Requested" back to "Mailed" if the
  `critique_comments` check finds no comments. This check should be updated to clear the `[reviewer]` COMMENTS entry and
  remove the COMMENTS field if there are no more entries when `critique_comments` finds no comments.
  + We should update the `gai run crs` workflow to take this `~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json` as an
  argument and default to creating it with `critique_comments` if not provided.
  + The "r" (run crs) `gai work` option will need to be updated to use this new argument when invoking the `crs` workflow.
  + We should clean up by removing support for the "Changes Requested" STATUS field value completely.
  + When the `crs` workflow starts running, we should add a "- (YYmmdd_HHMMSS)" suffix to the ChangeSpec name in the
  COMMENTS entry to indicate that the workflow is running. The "r" (run crs) option should ONLY be visible when a
  `[reviewer]` COMMENTS entry exists that does NOT have this suffix.
  + If the `crs` workflow completes successfully, we should update the suffix to use the proposal ID of the HISTORY entry
  that was added. Otherwise, if the workflow failed for some reason (ex: system restart, no file changes made), we should
  update the suffix to "- (!)". We should also start checking for any of these suffices that are >2h old and change them
  to "- (ZOMBIE)". See how this suffix is handled for the fix-hook agent; we should handle it the same way here.
  + Make sure that the amend/entry note created by the `crs` workflow references the
  `~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json` file. If this file doesn't exist, it should be created, by copying
  the file we gave the the `crs` agent containing the comments.
---

# Plan: Replace "Changes Requested" Status with COMMENTS Field

## Overview

Replace the "Changes Requested" STATUS approach with a new COMMENTS field that tracks Critique code review comments with file references and suffix-based workflow status tracking.

## New COMMENTS Field Format

```
COMMENTS:
  [reviewer] ~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json
  [reviewer] ~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json - (YYmmdd_HHMMSS)
  [reviewer] ~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json - (2a)
  [reviewer] ~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json - (!)
  [reviewer] ~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json - (ZOMBIE)
```

Suffix meanings:
- No suffix: CRS workflow available to run
- `(YYmmdd_HHMMSS)`: CRS workflow running (timestamp when started)
- `(2a)`: CRS completed, linked to proposal ID
- `(!)`: CRS failed
- `(ZOMBIE)`: CRS stale (>2h old timestamp suffix)

---

## Implementation Steps

### Phase 1: Data Structures (`work/changespec.py`)

1. **Add CommentEntry dataclass** (after HookEntry):
   ```python
   @dataclass
   class CommentEntry:
       reviewer: str          # e.g., "johndoe"
       file_path: str         # ~/.gai/comments/<name>-reviewer-YYmmdd_HHMMSS.json
       suffix: str | None     # YYmmdd_HHMMSS, "!", proposal_id, "ZOMBIE"
   ```

2. **Update ChangeSpec dataclass** - add field:
   ```python
   comments: list[CommentEntry] | None = None
   ```

3. **Update `_parse_changespec_from_lines()`** - add COMMENTS parsing:
   - Detect `COMMENTS:` header
   - Parse entries: `[reviewer] path` or `[reviewer] path - (suffix)`
   - Pattern: `^\s{2}\[([^\]]+)\]\s+(\S+)(?:\s+-\s+\(([^)]+)\))?$`

4. **Update `display_changespec()`** - add COMMENTS display between HOOKS and panel end

### Phase 2: Comments Operations Module

Create `work/comments/` package (follow `work/hooks/` pattern):

1. **`work/comments/__init__.py`** - re-export public functions

2. **`work/comments/core.py`**:
   - `CRS_STALE_THRESHOLD_SECONDS = 7200` (2 hours)
   - `generate_comments_timestamp()` - YYmmdd_HHMMSS format
   - `get_comments_directory()` - returns `~/.gai/comments/`
   - `get_comments_file_path(name, reviewer, timestamp)` - full path
   - `is_comments_suffix_stale(suffix)` - check if timestamp >2h
   - `is_timestamp_suffix(suffix)` - check if valid timestamp format
   - `comment_needs_crs(entry)` - returns True if no suffix

3. **`work/comments/operations.py`**:
   - `save_critique_comments(changespec, timestamp)` - run critique_comments, save to file
   - `_format_comments_field(comments)` - format as lines
   - `update_changespec_comments_field(project_file, changespec_name, comments)` - atomic update
   - `add_comment_entry(project_file, changespec_name, entry)` - add single entry
   - `remove_comment_entry(project_file, changespec_name, reviewer)` - remove by reviewer
   - `set_comment_suffix(project_file, changespec_name, reviewer, suffix, comments)`
   - `clear_comment_suffix(project_file, changespec_name, reviewer, comments)`

### Phase 3: Loop Integration (`work/loop/core.py`)

1. **Add `_check_comments()` method**:
   - Run `critique_comments` command
   - If output exists and no `[reviewer]` entry: create file, add entry
   - If no output and `[reviewer]` entry exists (without suffix): remove entry
   - Remove COMMENTS field if empty

2. **Add `_check_comment_zombies()` method**:
   - Check all comment entries with timestamp suffix
   - Mark as `- (ZOMBIE)` if >2h old
   - Add throttling similar to hook zombie checks

3. **Update `_run_check_cycle()`**:
   - Call `_check_comments()` for "Mailed" status
   - Call `_check_comment_zombies()`

4. **Remove** status transitions for "Changes Requested":
   - Remove Mailed → Changes Requested transition
   - Remove Changes Requested → Mailed transition

### Phase 4: CRS Workflow Updates

1. **Update `work/workflows/crs.py::run_crs_workflow()`**:
   - Add `comments_file: str | None = None` parameter
   - Set timestamp suffix when starting
   - Update suffix to proposal ID on success
   - Update suffix to "!" on failure
   - Pass comments_file to CrsWorkflow

2. **Update `crs_workflow.py::CrsWorkflow.__init__()`**:
   - Add `comments_file: str | None = None` parameter
   - Store as instance variable

3. **Update `crs_workflow.py::_create_critique_comments_artifact()`**:
   - If `self.comments_file` provided: copy from that path
   - Otherwise: run critique_comments as before

4. **Update history entry creation**:
   - Add `| COMMENTS: <path>` line to proposed entry
   - Copy comments file if doesn't exist at path

### Phase 5: Work "r" Option Updates

1. **Update `work/operations.py::get_available_workflows()`**:
   - Remove: `if changespec.status == "Changes Requested": workflows.append("crs")`
   - Add: check for comment entry without suffix → add "crs"

2. **Update `work/handlers/workflow_handlers.py::handle_run_crs_workflow()`**:
   - Find comment entry without suffix
   - Pass `comments_file` path to `run_crs_workflow()`
   - Set timestamp suffix before running
   - Update suffix based on outcome

### Phase 6: Remove "Changes Requested" Status

1. **`status_state_machine.py`**:
   - Remove from `VALID_STATUSES`
   - Remove from `VALID_TRANSITIONS`

2. **`work/cl_status.py`**:
   - Update `SYNCABLE_STATUSES = ["Mailed"]`
   - Keep `has_pending_comments()` for internal use by loop

3. **`work/changespec.py`**:
   - Remove from `_get_status_color()`

4. **`dot_config/nvim/syntax/gaiproject.vim`**:
   - Remove `GaiProjectStatusChangesRequested` match and highlight

### Phase 7: Vim Syntax Highlighting

Add to `dot_config/nvim/syntax/gaiproject.vim`:

```vim
" COMMENTS field
syn match GaiProjectCommentsKey "^COMMENTS:" contained
syn match GaiProjectCommentsEntry "^\s\s\[[^\]]\+\].*$" contains=GaiProjectCommentsReviewer,GaiProjectCommentsSuffix
syn match GaiProjectCommentsReviewer "\[[^\]]\+\]" contained
syn match GaiProjectCommentsSuffixZombie "- (ZOMBIE)" contained
syn match GaiProjectCommentsSuffixFailed "- (!)" contained
syn match GaiProjectCommentsSuffixTimestamp "- (\d\{6\}_\d\{6\})" contained

highlight GaiProjectCommentsKey gui=bold guifg=#87D7FF
highlight GaiProjectCommentsReviewer gui=bold guifg=#D7AF5F
highlight GaiProjectCommentsSuffixZombie gui=bold guifg=#AF0000
highlight GaiProjectCommentsSuffixFailed gui=bold guifg=#AF0000
highlight GaiProjectCommentsSuffixTimestamp gui=bold guifg=#D75F87
```

### Phase 8: Tests

1. **Create `test/test_comments.py`**:
   - Test CommentEntry parsing
   - Test add/remove/update operations
   - Test suffix handling and stale detection
   - Test integration with loop

2. **Update existing tests**:
   - `test_status_state_machine.py` - remove "Changes Requested"
   - `test_loop.py` - update for COMMENTS handling
   - `test_operations.py` - update get_available_workflows tests

---

## Critical Files

| File | Changes |
|------|---------|
| `work/changespec.py` | Add CommentEntry, update ChangeSpec, parsing, display |
| `work/comments/core.py` | NEW - timestamps, stale detection, utilities |
| `work/comments/operations.py` | NEW - file operations, field updates |
| `work/loop/core.py` | Add comment checking, remove status transitions |
| `work/workflows/crs.py` | Accept comments_file, manage suffix lifecycle |
| `crs_workflow.py` | Accept comments_file, optionally copy |
| `work/operations.py` | Update get_available_workflows() |
| `work/handlers/workflow_handlers.py` | Pass comments_file, manage suffix |
| `status_state_machine.py` | Remove "Changes Requested" |
| `work/cl_status.py` | Update SYNCABLE_STATUSES |
| `dot_config/nvim/syntax/gaiproject.vim` | Add COMMENTS syntax, remove Changes Requested |

---

## Implementation Order

1. Phase 1 (Data structures) - foundation
2. Phase 2 (Comments module) - core operations
3. Phase 7 (Vim syntax) - visual verification
4. Phase 3 (Loop integration) - automated detection
5. Phase 4 (CRS workflow) - workflow updates
6. Phase 5 (Work "r" option) - UI integration
7. Phase 6 (Remove status) - breaking change last
8. Phase 8 (Tests) - throughout
