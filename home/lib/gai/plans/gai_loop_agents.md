---
prompt: | 
  Can you help me add `gai loop` checks that run the `crs` and `fix-hook` workflows?
  + These checks should be run every 10s (with hook checks).
  + These should run on any ChangeSpec where the "r" (run crs) or "r" (run fix-hook) options would be available in `gai
  work`.
  + When running one of these workflows, we need to properly claim/release a workspace directory just for that workflow
  (NO other checks or workflows can run in that workspace while the workflow is running).
  + When these workflows complete they should automatically create a proposed HISTORY entry, as if the user had selected
  "a" (accept) for the proposed entry (No prompt should show obviously since this will be run in the background).
  + We should make sure that we don't block `gai loop` while running these workflows. We should parallelize them in the
  same way that we parallelize other checks that run commands (ex: hook commands).
---

# Plan: Add `crs` and `fix-hook` Workflow Checks to `gai loop`

## Summary
Add background execution of `crs` and `fix-hook` workflows to `gai loop` that run every 10s with hook checks. Workflows run in parallel, auto-accept proposals on completion, and each gets its own workspace.

## Files to Create

### 1. `home/lib/gai/work/loop/workflows_runner.py`
New module for workflow background execution (analogous to `hooks_runner.py`):
- `start_stale_workflows(changespec, log)` - Start eligible CRS/fix-hook workflows in background
- `check_and_complete_workflows(changespec, log)` - Check completion and auto-accept proposals
- `_start_crs_workflow(changespec, comment_entry, log)` - Start CRS as background process
- `_start_fix_hook_workflow(changespec, hook, log)` - Start fix-hook as background process
- `auto_accept_proposal(changespec, proposal_id, workspace_dir, log)` - Accept without prompts

### 2. `home/lib/gai/loop_crs_runner.py`
Standalone executable script for background CRS execution:
- Takes: changespec_name, project_file, comments_file, reviewer_type, workspace_dir, output_file
- Runs CrsWorkflow, creates proposal automatically
- Writes completion marker: `===WORKFLOW_COMPLETE=== PROPOSAL_ID: <id> EXIT_CODE: <code>`

### 3. `home/lib/gai/loop_fix_hook_runner.py`
Standalone executable script for background fix-hook execution:
- Takes: changespec_name, project_file, hook_command, hook_output_path, workspace_dir, output_file
- Runs GeminiCommandWrapper agent
- Writes completion marker with proposal ID and exit code

## Files to Modify

### 1. `home/lib/gai/work/loop/core.py`
Add `_check_workflows()` method and integrate into `_run_hooks_cycle()`:

```python
def _run_hooks_cycle(self) -> int:
    for changespec in all_changespecs:
        # ... existing hook checks ...

        # NEW: Check and run CRS/fix-hook workflows
        workflow_updates = self._check_workflows(changespec)
        updates.extend(workflow_updates)

def _check_workflows(self, changespec: ChangeSpec) -> list[str]:
    """Check workflow completion and start stale workflows."""
    updates = []
    # Phase 1: Check completion of running workflows and auto-accept
    completion_updates = check_and_complete_workflows(changespec, self._log)
    updates.extend(completion_updates)
    # Phase 2: Start stale workflows
    start_updates, _ = start_stale_workflows(changespec, self._log)
    updates.extend(start_updates)
    return updates
```

### 2. `home/lib/gai/work/loop/core.py` - `_check_author_comments()`
When adding [author] COMMENTS entry, remove any [reviewer] entry:

```python
# After creating author entry, add:
if changespec.comments:
    reviewer_entries = [e for e in changespec.comments if e.reviewer == "reviewer"]
    for entry in reviewer_entries:
        remove_comment_entry(project_file, name, "reviewer", comments)
        updates.append("Removed [reviewer] entry (author comments take precedence)")
```

## Key Design Decisions

### Background Execution Pattern
- Use `subprocess.Popen(start_new_session=True)` like hooks_runner.py
- Output files at `~/.gai/workflows/<name>_<type>_<timestamp>.txt`
- Completion marker: `===WORKFLOW_COMPLETE=== PROPOSAL_ID: <id> EXIT_CODE: <code>`

### Workspace Management
- Use 100-199 range via `get_first_available_loop_workspace()`
- Workflow claim names: `loop(crs)-reviewer`, `loop(fix-hook)-<timestamp>`
- Each workflow gets its own workspace (allow multiple simultaneous workflows)

### Workflow Suffix Tracking
- **CRS**: Set timestamp suffix on comment entry `[reviewer] path - (241227_123456)`
- **fix-hook**: Set timestamp suffix on hook status line `(1) [...] FAILED - (241227_123456)`
- On completion: Set proposal ID suffix, then auto-accept updates HISTORY

### Eligibility Checks
- **CRS eligible**: Comments has [reviewer] or [author] entry with `suffix is None`
- **fix-hook eligible**: Hook has FAILED status with status line `suffix is None`
- Multiple failing hooks: Start ALL eligible hooks in parallel

### Auto-Accept Logic
Extract from `execute_change_action("accept", ...)` in `change_actions.py`:
1. Parse proposal ID to get base_num and letter
2. Find proposal entry in HISTORY
3. Apply diff via `apply_diff_to_workspace()`
4. Amend commit via `bb_hg_amend`
5. Renumber HISTORY entries via `_renumber_history_entries()`
6. Release old workflow workspace

## Implementation Sequence

1. Create `workflows_runner.py` with stub functions
2. Create `loop_crs_runner.py` standalone script
3. Create `loop_fix_hook_runner.py` standalone script
4. Implement `start_stale_workflows()` to start background workflows
5. Implement `check_and_complete_workflows()` for completion detection
6. Implement `auto_accept_proposal()` to accept without prompts
7. Integrate into `core.py` - add `_check_workflows()` to `_run_hooks_cycle()`
8. Modify `_check_author_comments()` to remove [reviewer] when adding [author]
9. Run `make fix && make lint && make test`
10. Run `chezmoi apply` to deploy changes
