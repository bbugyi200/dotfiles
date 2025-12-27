---
prompt: |
  ultrathink: Do a deep dive into the home/lib/gai codebase with the goal of reducing code duplication by factoring out shared functionality.
---

# Refactoring Plan: Reduce Code Duplication in home/lib/gai

## Summary

Create a new `gai_utils.py` module to consolidate duplicated utility functions across the codebase. The refactoring is organized into phases by priority and risk.

---

## Phase 1: Create gai_utils.py with Core Utilities

### Step 1.1: Create new module with timestamp and directory functions

**Create:** `home/lib/gai/gai_utils.py`

```python
"""Core utility functions shared across gai modules."""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from work.changespec import ChangeSpec


def generate_timestamp() -> str:
    """Generate a timestamp in YYmmdd_HHMMSS format (Eastern timezone)."""
    eastern = ZoneInfo("America/New_York")
    return datetime.now(eastern).strftime("%y%m%d_%H%M%S")


def get_gai_directory(subdir: str) -> str:
    """Get the path to a subdirectory under ~/.gai/."""
    return os.path.expanduser(f"~/.gai/{subdir}")


def ensure_gai_directory(subdir: str) -> str:
    """Ensure a ~/.gai subdirectory exists and return its path."""
    dir_path = get_gai_directory(subdir)
    Path(dir_path).mkdir(parents=True, exist_ok=True)
    return dir_path


def make_safe_filename(name: str) -> str:
    """Convert a string to a safe filename (alphanumeric + underscore only)."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def strip_reverted_suffix(name: str) -> str:
    """Remove the __<N> suffix from a reverted ChangeSpec name."""
    match = re.match(r"^(.+)__\\d+$", name)
    return match.group(1) if match else name


def shorten_path(path: str) -> str:
    """Shorten a file path by replacing home directory with ~."""
    return path.replace(str(Path.home()), "~")


def get_workspace_directory_for_changespec(changespec: "ChangeSpec") -> str | None:
    """Get the workspace directory for a ChangeSpec."""
    from running_field import get_workspace_directory as get_workspace_dir

    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]
    try:
        return get_workspace_dir(project_basename)
    except RuntimeError:
        return None
```

---

## Phase 2: Migrate Timestamp Generation (5 instances)

### Files to Modify:

| File | Current Function | Action |
|------|------------------|--------|
| `work/hooks/core.py:14-17` | `generate_timestamp()` | Import from gai_utils, remove local |
| `history_utils.py:23-26` | `generate_timestamp()` | Import from gai_utils, remove local |
| `chat_history.py:35-39` | `_generate_timestamp()` | Import from gai_utils, remove local |
| `work/split_workflow/utils.py` | `generate_timestamp()` | Import from gai_utils, remove local |
| `work/comments/core.py` | `generate_comments_timestamp()` | Import from gai_utils, remove local |

### Step 2.1: Update work/hooks/core.py
- Add: `from gai_utils import generate_timestamp`
- Remove: lines 14-17 (local `generate_timestamp()`)

### Step 2.2: Update history_utils.py
- Add: `from gai_utils import generate_timestamp`
- Remove: lines 23-26 (local `generate_timestamp()`)

### Step 2.3: Update chat_history.py
- Add: `from gai_utils import generate_timestamp`
- Remove: lines 35-39 (local `_generate_timestamp()`)
- Update all callers from `_generate_timestamp()` to `generate_timestamp()`

### Step 2.4: Update work/split_workflow/utils.py
- Add: `from gai_utils import generate_timestamp`
- Remove: local `generate_timestamp()`

### Step 2.5: Update work/comments/core.py
- Add: `from gai_utils import generate_timestamp`
- Remove: local `generate_comments_timestamp()`
- Update callers to use `generate_timestamp()`

---

## Phase 3: Migrate Directory Management (9+ instances)

### Files to Modify:

| File | Functions | Action |
|------|-----------|--------|
| `history_utils.py:12-20` | `_get_diffs_directory()`, `_ensure_diffs_directory()` | Replace with `get_gai_directory("diffs")`, `ensure_gai_directory("diffs")` |
| `chat_history.py:16-24` | `_get_chats_directory()`, `_ensure_chats_directory()` | Replace with gai_utils calls |
| `work/hooks/operations.py` | `_get_hooks_directory()`, `_ensure_hooks_directory()` | Replace with gai_utils calls |
| `work/comments/core.py` | Directory functions | Replace with gai_utils calls |
| `work/loop/workflows_runner.py` | `_get_workflows_directory()`, `_ensure_workflows_directory()` | Replace with gai_utils calls |
| `work/split_workflow/utils.py` | `get_splits_directory()` | Replace with gai_utils calls |

### Implementation Pattern:

For each file:
1. Add import: `from gai_utils import get_gai_directory, ensure_gai_directory`
2. Replace local `_get_X_directory()` with: `get_gai_directory("X")`
3. Replace local `_ensure_X_directory()` with: `ensure_gai_directory("X")`
4. Remove the local function definitions

---

## Phase 4: Migrate Other Utilities

### Step 4.1: Safe Filename (4 instances)

**Files:**
- `history_utils.py:62` - Replace inline regex with `make_safe_filename()`
- `work/comments/core.py` - Replace inline regex
- `work/hooks/operations.py:56` - Replace inline regex
- `work/loop/workflows_runner.py:67` - Replace inline regex

### Step 4.2: Reverted Suffix Stripping (2 instances)

**Files:**
- `work/hooks/operations.py:24-29` - Import from gai_utils, remove local
- `work/restore.py:34-47` - Import from gai_utils, remove local

### Step 4.3: Path Shortening (2 instances)

**Files:**
- `loop_crs_runner.py:31-33` - Import from gai_utils, remove local
- `work/workflows/crs.py:32-36` - Import from gai_utils, remove local

### Step 4.4: Workspace Directory Getter (3 instances)

**Files:**
- `work/cl_status.py:45-60` - Import from gai_utils, remove local
- `work/restore.py:50-65` - Import from gai_utils, remove local
- `work/revert.py:113-126` - Import from gai_utils, remove local

---

## Phase 5: Fix Shell Command Wrapper

**File:** `change_actions.py`
- The file has a private `_run_shell_command()` that duplicates `shared_utils.run_shell_command()`
- Replace usage with import from `shared_utils`
- Remove local `_run_shell_command()` function

---

## Phase 6: Add Tests

**Create:** `home/lib/gai/test/test_gai_utils.py`

Test coverage for:
- `generate_timestamp()` - Returns correct format
- `get_gai_directory()` - Returns correct path
- `ensure_gai_directory()` - Creates directory
- `make_safe_filename()` - Sanitizes correctly
- `strip_reverted_suffix()` - Handles both cases
- `shorten_path()` - Replaces home directory

---

## Verification

After each phase:
1. Run `make fix`
2. Run `make lint`
3. Run `make test`

---

## Files Summary

### New Files:
- `home/lib/gai/gai_utils.py` - Core shared utilities
- `home/lib/gai/loop_runner_utils.py` - Loop runner shared utilities
- `home/lib/gai/test/test_gai_utils.py` - Tests for gai_utils
- `home/lib/gai/test/test_loop_runner_utils.py` - Tests for loop_runner_utils

### Modified Files:
- `home/lib/gai/work/hooks/core.py` - Remove generate_timestamp()
- `home/lib/gai/history_utils.py` - Remove generate_timestamp(), directory helpers
- `home/lib/gai/chat_history.py` - Remove _generate_timestamp(), directory helpers
- `home/lib/gai/work/split_workflow/utils.py` - Remove generate_timestamp(), directory helpers
- `home/lib/gai/work/comments/core.py` - Remove timestamp, directory helpers
- `home/lib/gai/work/hooks/operations.py` - Remove directory helpers, _strip_reverted_suffix()
- `home/lib/gai/work/loop/workflows_runner.py` - Remove directory helpers
- `home/lib/gai/work/restore.py` - Remove _strip_reverted_suffix(), _get_workspace_directory()
- `home/lib/gai/work/revert.py` - Remove _get_workspace_directory()
- `home/lib/gai/work/cl_status.py` - Remove _get_workspace_directory()
- `home/lib/gai/loop_crs_runner.py` - Refactor to use shared utilities
- `home/lib/gai/loop_fix_hook_runner.py` - Refactor to use shared utilities
- `home/lib/gai/change_actions.py` - Remove _run_shell_command()

---

## Phase 7: Consolidate Loop Runners

The two loop runner scripts (`loop_crs_runner.py` ~224 lines, `loop_fix_hook_runner.py` ~223 lines) share significant structure:

### Shared Patterns:
- Duplicate `_add_proposed_history_entry()` wrapper (identical)
- Common finalization in `finally` block: update suffix, release workspace, write completion marker
- Common proposal creation: check for changes, save chat history, save diff, create history entry, clean workspace

### Step 7.1: Create loop_runner_utils.py

**Create:** `home/lib/gai/loop_runner_utils.py`

```python
"""Shared utilities for loop runner scripts."""

import subprocess
from typing import Callable

from chat_history import save_chat_history
from history_utils import add_proposed_history_entry, clean_workspace, save_diff
from running_field import release_workspace
from work.changespec import ChangeSpec, parse_project_file


def check_for_local_changes() -> bool:
    """Check if there are uncommitted local changes."""
    result = subprocess.run(
        ["branch_local_changes"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def create_proposal_from_changes(
    project_file: str,
    cl_name: str,
    workspace_dir: str,
    workflow_note: str,
    prompt: str,
    response: str,
    workflow: str,
) -> tuple[str | None, int]:
    """Create a proposal from uncommitted changes.

    Returns:
        Tuple of (proposal_id, exit_code)
    """
    if not check_for_local_changes():
        print("No changes detected")
        return None, 1

    print("Changes detected, creating proposal...")

    # Save chat history
    chat_path = save_chat_history(
        prompt=prompt,
        response=response,
        workflow=workflow,
    )

    # Save the diff
    diff_path = save_diff(cl_name, target_dir=workspace_dir)
    if not diff_path:
        print("Failed to save diff")
        return None, 1

    # Create proposed HISTORY entry
    success, entry_id = add_proposed_history_entry(
        project_file=project_file,
        cl_name=cl_name,
        note=workflow_note,
        diff_path=diff_path,
        chat_path=chat_path,
    )

    if success and entry_id:
        print(f"Created proposal ({entry_id}): {workflow_note}")
        clean_workspace(workspace_dir)
        return entry_id, 0

    print("Failed to create proposal entry")
    return None, 1


def finalize_loop_runner(
    project_file: str,
    changespec_name: str,
    workspace_num: int,
    workflow_name: str,
    proposal_id: str | None,
    exit_code: int,
    update_suffix_fn: Callable[[ChangeSpec, str, str | None, int], None],
) -> None:
    """Common finalization logic for loop runners.

    Args:
        project_file: Path to the project file
        changespec_name: Name of the ChangeSpec
        workspace_num: Workspace number to release
        workflow_name: Name of the workflow
        proposal_id: Proposal ID if successful, None otherwise
        exit_code: Exit code (0 for success)
        update_suffix_fn: Callback to update the suffix (hook or comment)
    """
    # Update suffix based on result
    try:
        changespecs = parse_project_file(project_file)
        for cs in changespecs:
            if cs.name == changespec_name:
                update_suffix_fn(cs, project_file, proposal_id, exit_code)
                break
    except Exception as e:
        print(f"Warning: Failed to update suffix: {e}")

    # Release workspace
    try:
        release_workspace(
            project_file,
            workspace_num,
            workflow_name,
            changespec_name,
        )
        print(f"Released workspace #{workspace_num}")
    except Exception as e:
        print(f"Warning: Failed to release workspace: {e}")

    # Write completion marker
    print()
    print(f"===WORKFLOW_COMPLETE=== PROPOSAL_ID: {proposal_id} EXIT_CODE: {exit_code}")
```

### Step 7.2: Refactor loop_crs_runner.py

- Import utilities from `loop_runner_utils`
- Remove duplicate `_add_proposed_history_entry()`
- Remove duplicate `_shorten_path()` (use `gai_utils.shorten_path()`)
- Use `create_proposal_from_changes()` instead of inline logic
- Use `finalize_loop_runner()` in finally block
- **Expected reduction**: ~224 lines → ~100 lines

### Step 7.3: Refactor loop_fix_hook_runner.py

- Import utilities from `loop_runner_utils`
- Remove duplicate `_add_proposed_history_entry()`
- Use `create_proposal_from_changes()` instead of inline logic
- Use `finalize_loop_runner()` in finally block
- **Expected reduction**: ~223 lines → ~100 lines

---

## Workflow main() Boilerplate (Not Refactored)

The workflow main() functions are minimal (4 lines each):
```python
def main() -> NoReturn:
    workflow = XWorkflow()
    success = workflow.run()
    sys.exit(0 if success else 1)
```

This is too simple to benefit from extraction - creating a helper would add complexity without real savings.

---
