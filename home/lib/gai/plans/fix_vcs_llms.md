# Fix VCS Provider Problems for Git Support

## Context

The gai codebase has a clean VCS provider abstraction (`home/lib/gai/src/vcs_provider/`) with an ABC, git
implementation, and hg implementation. However, several parts of the codebase bypass this abstraction or contain
hg-specific hardcoded values, making git support broken in practice. The analysis in
`home/lib/gai/docs/vcs_llms_problems_critique.md` identifies 5 valid problems. This plan fixes all of them across 3
phases, each suitable for one Claude Code session.

The user also wants a `gai_*` plugin system: shell executables that detect VCS type and dispatch accordingly, allowing
users to override them.

## Real Problems Being Fixed

| #   | Problem                                                    | Locations                                                                                       | Severity          |
| --- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ----------------- |
| 1   | Direct `bb_hg_update` subprocess calls bypass VCS provider | `base.py:455,530`, `axe.py:270`                                                                 | **Crash on git**  |
| 2   | Hardcoded `"p4head"` default revision                      | `operations.py:135`, `restore.py:174`, `_entry_points.py:150`, `proposal_rebase.py:330-331,430` | **Crash on git**  |
| 3   | Hardcoded hg-specific hook commands                        | `constants.py:9-12`                                                                             | **Broken on git** |
| 4   | Workspace system calls `bb_get_workspace` (hg-only)        | `running_field.py:546`                                                                          | **Crash on git**  |
| 5   | Axe scheduler workspace numbering tied to hg shares        | `running_field.py:470-495`                                                                      | Coupled with #4   |

---

## Phase 1: Fix Direct VCS Bypasses and Hardcoded `p4head`

**Goal:** Eliminate all code that bypasses the VCS provider (direct `bb_hg_update` calls) and replace hardcoded
`"p4head"` with VCS-aware default resolution.

### 1A. Add `get_default_parent_revision()` to VCS Provider

**File: `home/lib/gai/src/vcs_provider/_base.py`** (add to "Optional core methods" section ~line 96)

- Add method `get_default_parent_revision(self, cwd: str) -> str` that raises `NotImplementedError`

**File: `home/lib/gai/src/vcs_provider/_hg.py`**

- Implement: return `"p4head"`

**File: `home/lib/gai/src/vcs_provider/_git.py`** (after `sync_workspace` ~line 220)

- Implement: detect default branch via `git symbolic-ref refs/remotes/origin/HEAD`, fallback to `"main"`, return
  `f"origin/{default_branch}"` (reuse the logic already in `sync_workspace`)

### 1B. Replace `"p4head"` in `operations.py` and `restore.py`

**File: `home/lib/gai/src/ace/operations.py`** (line 131-141)

- Move `provider = get_vcs_provider(target_dir)` before the revision-selection logic
- Change line 135:
  `update_target = changespec.parent if changespec.parent else provider.get_default_parent_revision(target_dir)`

**File: `home/lib/gai/src/ace/restore.py`** (line 173-180)

- Move `provider = get_vcs_provider(workspace_dir)` before line 174
- Change line 174:
  `update_target = changespec.parent if changespec.parent else provider.get_default_parent_revision(workspace_dir)`

### 1C. Replace `"p4head"` in agent workflow entry points

**File: `home/lib/gai/src/vcs_provider/__init__.py`**

- Add constant `VCS_DEFAULT_REVISION = "__vcs_default__"` and export it

**File: `home/lib/gai/src/ace/tui/actions/agent_workflow/_entry_points.py`** (line 150)

- Change `update_target="p4head"` to `update_target=VCS_DEFAULT_REVISION`

**File: `home/lib/gai/src/axe_runner_utils.py`** (line 66-68)

- After getting provider at line 67, resolve the sentinel:
  `if update_target == VCS_DEFAULT_REVISION: update_target = provider.get_default_parent_revision(workspace_dir)`

### 1D. Replace `"p4head"` in proposal_rebase.py

**File: `home/lib/gai/src/ace/tui/actions/proposal_rebase.py`**

Use a sentinel constant for the "root" option:

- Define `_ROOT_PARENT_SENTINEL = "__root__"` at module level
- Line 331: Change `("p4head", "root")` to `(_ROOT_PARENT_SENTINEL, "root")`
- Line 333: Change `p4head` comment
- Lines 427-430: In `_run_rebase_workflow`, when `new_parent_name == _ROOT_PARENT_SENTINEL`:
  - Resolve to real VCS default: `actual_target = provider.get_default_parent_revision(workspace_dir)`
  - Pass `actual_target` to `provider.rebase()`
  - Set `parent_value = None` (clear PARENT field)

### 1E. Replace direct `bb_hg_update` calls in TUI

**File: `home/lib/gai/src/ace/tui/actions/base.py`**

Location 1 (~line 452-469, `run_commands()` in `_open_tmux_for_workspace`):

- Replace `subprocess.run(["bb_hg_update", ...])` block with:
  ```python
  from vcs_provider import get_vcs_provider
  provider = get_vcs_provider(workspace_dir)
  success, error = provider.checkout(changespec.name, workspace_dir)
  if not success:
      return (False, f"checkout failed: {error}")
  ```

Location 2 (~line 527-544, `run_checkout()` in `_checkout_to_workspace`):

- Same replacement pattern

**File: `home/lib/gai/src/ace/tui/actions/axe.py`** (~line 268-286):

- Same replacement pattern using `provider.checkout(cl_name, workspace_dir)`

### 1F. Tests

- **Update** `test/test_ace_operations.py`: `test_update_to_changespec_uses_p4head_default` -> mock
  `provider.get_default_parent_revision()`
- **Update** `test/test_restore.py`: `test_restore_changespec_without_parent_uses_p4head` -> verify
  `get_default_parent_revision()` called
- **Update** `test/test_changespec_update.py`: update assertions from `"p4head"` to mock-based
- **Update** `test/test_axe_runner_utils.py`: tests passing `"p4head"` should use `VCS_DEFAULT_REVISION` and verify
  resolution
- **Add** tests for `get_default_parent_revision()` in `test/test_vcs_provider_git_integration.py` or new unit test file

### 1G. Verification

```bash
cd ~/.local/share/chezmoi
make lint-python-lite
make test-python-gai
# Grep to confirm no remaining p4head in code (excluding docs/tests/comments):
grep -rn '"p4head"' home/lib/gai/src/ --include='*.py'
# Grep to confirm no remaining direct bb_hg_update calls outside vcs_provider:
grep -rn 'bb_hg_update' home/lib/gai/src/ --include='*.py' | grep -v vcs_provider
```

---

## Phase 2: Configurable Default Hooks + gai\_\* Plugin Scripts

**Goal:** Replace hardcoded `bb_hg_presubmit`/`bb_hg_lint` with VCS-agnostic `gai_presubmit`/`gai_lint` plugin scripts,
and make hooks configurable.

### 2A. Create `gai_presubmit` plugin script

**New file: `home/bin/executable_gai_presubmit`**

- Detect VCS type (check `.hg` or `.git` in cwd or parents)
- hg: `exec bb_hg_presubmit "$@"`
- git: no-op (exit 0) with informational message, or run a configurable command

### 2B. Create `gai_lint` plugin script

**New file: `home/bin/executable_gai_lint`**

- Same VCS detection pattern
- hg: `exec bb_hg_lint "$@"`
- git: no-op (exit 0) with informational message

### 2C. Make hooks configurable

**File: `home/lib/gai/src/ace/constants.py`**

- Rename `REQUIRED_CHANGESPEC_HOOKS` to `_DEFAULT_REQUIRED_HOOKS` with `gai_*` names:
  ```python
  _DEFAULT_REQUIRED_HOOKS = ("!$gai_presubmit", "$gai_lint")
  ```
- Add `get_required_changespec_hooks() -> tuple[str, ...]` function that checks `gai.yml` config for
  `vcs_provider.default_hooks` override, falling back to `_DEFAULT_REQUIRED_HOOKS`
- Keep `REQUIRED_CHANGESPEC_HOOKS = _DEFAULT_REQUIRED_HOOKS` for backward compat

### 2D. Update callers

**File: `home/lib/gai/src/workflow_utils.py`** (line 106-109)

- Change `from ace.constants import REQUIRED_CHANGESPEC_HOOKS` to import and call `get_required_changespec_hooks()`

### 2E. Update config schema

**File: `home/dot_config/gai/gai.schema.json`**

- Add `default_hooks` array property to `vcs_provider` section

### 2F. Tests

- **Add** `test/test_ace_constants.py`: test default hooks, config override, empty config
- **Update** `test/test_workflow_utils.py`: expect `gai_presubmit`/`gai_lint` instead of `bb_hg_*`
- **Update** `test/test_changespec_operations.py`: update all `bb_hg_presubmit`/`bb_hg_lint` references

### 2G. Verification

```bash
cd ~/.local/share/chezmoi
make lint-python-lite
make test-python-gai
# Verify no remaining bb_hg_presubmit/bb_hg_lint in Python source (non-test, non-doc):
grep -rn 'bb_hg_presubmit\|bb_hg_lint' home/lib/gai/src/ --include='*.py' | grep -v test | grep -v doc
```

---

## Phase 3: VCS-Aware Workspace System

**Goal:** Replace `bb_get_workspace` with `gai_get_workspace` that supports both hg workspace shares and git worktrees.

### 3A. Create `gai_get_workspace` plugin script

**New file: `home/bin/executable_gai_get_workspace`**

- Usage: `gai_get_workspace <project> <N>`
- VCS detection (env var `GAI_VCS_PROVIDER`, or auto-detect from primary workspace)
- hg path: delegate to `bb_get_workspace "$@"`
- git path:
  - Workspace root: `$GAI_WORKSPACE_ROOT` or `$HOME/workspace`
  - Primary (N=1): return `$root/$project`
  - Worktree (N>1): create `git worktree add --detach $root/${project}_${N}` from primary if needed, return path

### 3B. Update `running_field.py`

**File: `home/lib/gai/src/running_field.py`** (line 527-558)

- Change `["bb_get_workspace", project, str(workspace_num)]` to `["gai_get_workspace", project, str(workspace_num)]`
- Update docstrings and error messages

The axe workspace numbering (100-199) in `get_first_available_axe_workspace()` is already VCS-agnostic -- it just finds
unclaimed numbers. The `gai_get_workspace` script handles creating the actual workspace (worktree for git, share for hg)
for any number.

### 3C. Add config support for workspace root

**File: `home/lib/gai/src/vcs_provider/config.py`**

- Add `get_workspace_root() -> str | None` helper

**File: `home/dot_config/gai/gai.schema.json`**

- Add `workspace_root` string property to `vcs_provider` section

### 3D. Tests

- **Update** `test/test_running_field_operations.py`: change `"bb_get_workspace"` to `"gai_get_workspace"` in all
  assertions
- **Add** integration test for git worktree creation/resolution

### 3E. Verification

```bash
cd ~/.local/share/chezmoi
make lint-python-lite
make test-python-gai
# Verify no remaining bb_get_workspace in Python source:
grep -rn 'bb_get_workspace' home/lib/gai/src/ --include='*.py'
# Manual test:
GAI_WORKSPACE_ROOT=/tmp/test_ws gai_get_workspace myproject 1
```

---

## Critical Files Summary

| File                                                  | Phase | Change                                               |
| ----------------------------------------------------- | ----- | ---------------------------------------------------- |
| `src/vcs_provider/_base.py`                           | 1     | Add `get_default_parent_revision()`                  |
| `src/vcs_provider/_git.py`                            | 1     | Implement `get_default_parent_revision()`            |
| `src/vcs_provider/_hg.py`                             | 1     | Implement `get_default_parent_revision()`            |
| `src/vcs_provider/__init__.py`                        | 1     | Add `VCS_DEFAULT_REVISION` constant                  |
| `src/ace/operations.py`                               | 1     | Replace `"p4head"` with provider call                |
| `src/ace/restore.py`                                  | 1     | Replace `"p4head"` with provider call                |
| `src/ace/tui/actions/base.py`                         | 1     | Replace 2x `bb_hg_update` with `provider.checkout()` |
| `src/ace/tui/actions/axe.py`                          | 1     | Replace 1x `bb_hg_update` with `provider.checkout()` |
| `src/ace/tui/actions/agent_workflow/_entry_points.py` | 1     | Replace `"p4head"` with `VCS_DEFAULT_REVISION`       |
| `src/axe_runner_utils.py`                             | 1     | Resolve `VCS_DEFAULT_REVISION` sentinel              |
| `src/ace/tui/actions/proposal_rebase.py`              | 1     | Replace `"p4head"` with root sentinel                |
| `src/ace/constants.py`                                | 2     | Configurable hooks with `gai_*` defaults             |
| `src/workflow_utils.py`                               | 2     | Use `get_required_changespec_hooks()`                |
| `home/bin/executable_gai_presubmit`                   | 2     | New plugin script                                    |
| `home/bin/executable_gai_lint`                        | 2     | New plugin script                                    |
| `src/running_field.py`                                | 3     | Replace `bb_get_workspace` with `gai_get_workspace`  |
| `home/bin/executable_gai_get_workspace`               | 3     | New plugin script                                    |

## What This Does NOT Fix (and why)

- **`run_bb_hg_clean` naming**: Already delegates to `provider.stash_and_clean()` internally -- cosmetic name issue, not
  a real bug
- **`critique_comments` for git**: Already gracefully skipped for git repos (`checks_runner.py:208-213`)
- **CL URL parsing**: Already handles both `http://cl/<num>` and GitHub PR URLs
- **`findreviewers` crash**: Never called from git code path
