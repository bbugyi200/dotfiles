---
prompt: |
  Can you help me change the way we handle file changes created by gai agents?
  + Currently, we offer the a/c/n/x prompt and leave the file changes in-place in whatever workspace directory they were
  created in.
  + I want to start saving a diff of the changes (we already do this when the "a" option is used to construct the HISTORY
  entry) and then clearing (using the `hg update --clean .` command) the workspace directory of all of the agent's file
  changes.
  + The "a" (amend) option should be changed to "a" (accept).
  + The new "a" (accept) option should use create a "proposed" HISTORY entry, which are entries at the bottom that use the
  last HISTORY entry index with a lowercase letter (starting at "a"--pick the lowest available next letter) appended to it
  for their index.
  + The new "a" (accept) message should accept one or more proposal indexes each corresponding with a proposed HISTORY
  entry. We will try to apply these proposed entries in the order they are provided using the `hg import --no-commit
  <difffile`command to re-apply the changes saved in the diff. If this command fails for any of the proposed entries, we
  should stop processing further proposed entries, run `hg update --clean .`, if we ran `hg import --no-commit <difffile>`
  sucessfully for any proposed entries before the failure, and then produce a good error message for the user.
  + We can remove the "x" (purge) option altogether since all unaccepted changes will be cleaned.
  + The current behavior of `gai amend` should be preserved. The new behavior should be available via `gai amend
  --propose`.
  + All HOOKS entries (hook commands) should be run for proposed entries (by `gai monitor`) when their HISTORY entries are
  added. What's different about these hook commands is that `gai monitor` should use `hg import --no-commit <difffile>` to
  apply the proposed changes after navigating to the workspace directory and checking out the CL (using the `bb_hg_update`
  command). This should all happen before the hook commands are run.
  + When a user accepts proposed entries, we should first update the HISTORY entires. The accepted entries should have
  their indexes changed to the next numbers available in the order that they were specified and applied and the rejected
  (not specified) proposal indexes will keep the same form, but will have the letters updated to use the lowest possible
  letters (ex: if the user specified "2d 2a", then "(2d)" becomes "3", "(2a)" becomes "4", "(2b)" becomes "(2a)", and
  "(2c)" becomes "(2b)").
---

# Proposed HISTORY Entries Implementation Plan

## Summary

Add a `--propose` mode to `gai amend` that creates "proposed" HISTORY entries instead of amending commits directly. Proposed entries save diffs, clean the workspace, and allow users to later accept/apply multiple proposals in a specific order via a new `gai accept` command.

## Key Concepts

### Proposed Entry Format
- Regular entries: `(1)`, `(2)`, `(3)`
- Proposed entries: `(2a)`, `(2b)`, `(2c)` - appended to the last regular entry number

### Behavior Overview
- `gai amend --propose`: Creates proposed entry, saves diff, cleans workspace
- `gai accept [NAME] <proposals>`: Applies proposals in order, converts to regular entries
- Hooks run for proposed entries by applying diff before execution

---

## Files to Modify

### 1. `home/lib/gai/work/changespec.py`
- Update `HistoryEntry` dataclass to support proposal suffix (e.g., `proposal_letter: str | None`)
- Update `_parse_changespec_from_lines()` to parse `(Na)` format
- Add helper to detect if entry is proposed

### 2. `home/lib/gai/history_utils.py`
- Update `get_next_history_number()` to skip proposed entries
- Add `get_next_proposal_letter(lines, cl_name, base_number)` function
- Add `add_proposed_history_entry()` function
- Add `renumber_history_entries()` for accepting/renumbering
- Add `get_proposal_diff_path(cl_name, entry_number, letter)` for retrieving diffs

### 3. `home/lib/gai/amend_workflow.py`
- Add `--propose` flag to `AmendWorkflow.__init__()` and argparse
- In propose mode:
  - Save diff to `~/.gai/diffs/`
  - Add proposed HISTORY entry (e.g., `(2a)`)
  - Run `hg update --clean .` to clean workspace
  - Skip `bb_hg_amend` call
- Keep existing behavior without `--propose`

### 4. `home/lib/gai/shared_utils.py`
- Update `prompt_for_change_action()`:
  - Add `propose_mode: bool = False` parameter
  - In propose mode: remove "x" option, change "a" to create proposed entry
  - "n" means "leave it, don't apply now"
- Update `execute_change_action()`:
  - Handle propose mode by calling `gai amend --propose` instead of `gai amend`

### 5. `home/lib/gai/accept_workflow.py` (NEW FILE)
- New `AcceptWorkflow` class:
  - Takes `cl_name: str | None` (defaults to `branch_name` output)
  - Takes `proposals: list[str]` (e.g., `["2d", "2a"]`)
- `run()` method:
  1. Parse proposals into `(base_number, letter)` tuples
  2. Validate all proposals exist in HISTORY
  3. For each proposal in order:
     - Get diff path from HISTORY entry
     - Run `hg import --no-commit <difffile>`
     - If fails: run `hg update --clean .`, report error, stop
  4. Update HISTORY:
     - Accepted proposals become next regular numbers
     - Remaining proposals renumber to lowest letters
  5. Run `hg amend` with combined message
- Add to `main.py` as `gai accept` subcommand

### 6. `home/lib/gai/work/loop.py`
- Update `_start_stale_hooks()`:
  - After `bb_hg_update`, check if hook's history entry is a proposal
  - If proposal: apply diff with `hg import --no-commit <difffile>`
  - Continue with hook execution
- Each hook command already gets its own workspace claim

### 7. `home/lib/gai/work/hooks.py`
- Add `apply_proposal_diff(workspace_dir, diff_path)` helper function
- Update `start_hook_background()` or add wrapper for proposed entries

### 8. `home/lib/gai/main.py`
- Add `accept` subcommand with:
  - Optional positional `cl_name` argument
  - Required positional `proposals` arguments (nargs="+")
- Wire up to `AcceptWorkflow`

---

## Implementation Steps

### Phase 1: Data Model Changes
1. Update `HistoryEntry` in `changespec.py` with `proposal_letter` field
2. Update history entry parsing regex to handle `(Na)` format
3. Add `is_proposed` property to `HistoryEntry`

### Phase 2: History Utilities
4. Add `get_next_proposal_letter()` function
5. Add `add_proposed_history_entry()` function
6. Add `renumber_history_entries()` function
7. Add `apply_diff_to_workspace()` helper

### Phase 3: Amend Workflow with --propose
8. Add `--propose` flag to `AmendWorkflow`
9. Implement propose mode logic (save diff, add entry, clean workspace)
10. Update `shared_utils.py` prompt for propose mode

### Phase 4: Accept Workflow
11. Create `accept_workflow.py` with `AcceptWorkflow` class
12. Implement proposal parsing and validation
13. Implement sequential diff application with rollback
14. Implement HISTORY renumbering logic
15. Add `gai accept` subcommand to `main.py`

### Phase 5: Hook Execution for Proposals
16. Update `loop.py` to detect proposed history entries
17. Apply proposal diffs before running hooks
18. Ensure proper workspace cleanup after hooks

### Phase 6: Testing
19. Add tests for proposal letter generation
20. Add tests for `add_proposed_history_entry()`
21. Add tests for `renumber_history_entries()`
22. Add tests for `AcceptWorkflow`

---

## Technical Details

### Proposal Letter Assignment
```python
def get_next_proposal_letter(lines: list[str], cl_name: str, base_number: int) -> str:
    """Get next available proposal letter (a-z) for a base number."""
    # Find all existing letters for this base number
    # Return lowest unused letter
```

### HISTORY Entry Regex Update
```python
# Current: r"^\s*\((\d+)\)\s+"
# New:     r"^\s*\((\d+)([a-z])?\)\s+"
```

### Diff Application
```python
def apply_diff_to_workspace(workspace_dir: str, diff_path: str) -> bool:
    """Apply a saved diff to the workspace."""
    result = subprocess.run(
        ["hg", "import", "--no-commit", os.path.expanduser(diff_path)],
        cwd=workspace_dir,
        capture_output=True,
    )
    return result.returncode == 0
```

### HISTORY Renumbering Example
Before accepting `2a`:
```
HISTORY:
  (1) Initial commit
  (2) Second commit
  (2a) Proposed change 1
  (2b) Proposed change 2
  (2c) Proposed change 3
```

After `gai accept 2a`:
```
HISTORY:
  (1) Initial commit
  (2) Second commit
  (3) Proposed change 1  <- was (2a), now regular entry
  (3a) Proposed change 2  <- was (2b), renumbered
  (3b) Proposed change 3  <- was (2c), renumbered
```

After `gai accept 3b 3a` (accepting in reverse order):
```
HISTORY:
  (1) Initial commit
  (2) Second commit
  (3) Proposed change 1
  (4) Proposed change 3  <- was (3b), applied first
  (5) Proposed change 2  <- was (3a), applied second
```
