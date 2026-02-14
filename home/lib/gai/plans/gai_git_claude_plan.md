# Roadmap: Generalize gai for Claude Code + Git

## Context

gai is currently tightly coupled to two Google-internal systems:

- **Gemini CLI** (`/google/bin/releases/gemini-cli/tools/gemini`) as its LLM backend
- **Mercurial/Sapling (hg)** via `bb_hg_*` wrapper scripts as its VCS backend

The goal is to make gai support **pluggable backends** for both dimensions, so it works with Claude Code + git in
addition to Gemini + hg. Both old and new backends should coexist via configuration.

### Key coupling points today

**LLM (Gemini):** `gemini_wrapper/wrapper.py` contains `GeminiCommandWrapper` class + `invoke_agent()` function. 7
modules import `invoke_agent()` directly. Hardcoded CLI path, model sizes ("big"/"little"), and Gemini-specific env
vars.

**VCS (hg):** ~15 `bb_hg_*` shell scripts, plus direct `hg` subprocess calls scattered across `commit_workflow/`,
`amend_workflow.py`, `rewind_workflow.py`, `ace/operations.py`, `commit_utils/workspace.py`, `mail_ops.py`, and more. No
abstraction layer exists.

---

## Phase 1: LLM Provider Abstraction Layer

**Goal:** Extract an abstract interface from the existing Gemini code so that LLM provider is pluggable.

### Phase 1.1: Define Abstract Interface & Refactor GeminiProvider

**Goal:** Create the `LLMProvider` abstraction and refactor existing Gemini code to implement it, without changing any
consumer call sites.

- Create `src/llm_provider/` package: `base.py` (LLMProvider ABC with `invoke()` method), `types.py` (ModelTier type +
  LoggingContext dataclass), `__init__.py`
- Extract prompt pre-processing pipeline (xprompt, command substitution, file refs, jinja2, prettier, HTML comments)
  from `GeminiCommandWrapper.invoke()` into `src/llm_provider/preprocessing.py` — these are already delegated to
  separate modules, so this is lifting the sequential call chain into a standalone function
- Extract post-processing (artifact logging, chat history, audio notification) into `src/llm_provider/postprocessing.py`
- Create `src/llm_provider/gemini.py` — `GeminiProvider(LLMProvider)` with only Gemini-specific logic (CLI command,
  subprocess streaming, env vars)
- Keep `invoke_agent()` working exactly as before internally using `GeminiProvider`
- Add unit tests

### Phase 1.2: Provider Registry & Configuration

**Goal:** Create a registry/factory so the active provider is selected via configuration.

- Create `src/llm_provider/registry.py` — maps provider names to LLMProvider subclasses
- Register `GeminiProvider` as `"gemini"` (default)
- Add `llm_provider` section to `gai.yml` config + update `gai.schema.json`
- Update `invoke_agent()` to use registry lookup instead of hardcoding GeminiProvider
- Add tests

### Phase 1.3: Migrate Consumers & Generalize Model Tiers

**Goal:** Replace all direct `invoke_agent()` imports with the new abstraction and retire `"big"`/`"little"`
terminology.

- Update all 7 consumer imports from `from gemini_wrapper import invoke_agent` to
  `from llm_provider import invoke_agent`
- Replace `model_size: Literal["little", "big"]` with `model_tier: ModelTier` across consumers
- Move `invoke_agent()` canonical location to `llm_provider/__init__.py`, keep backward-compat re-export in
  `gemini_wrapper`
- Update CLI `--model-size` → `--model-tier` (keep old as deprecated alias)
- Update `ace/tui/app.py` model size override logic
- Deprecate/remove `GeminiCommandWrapper` class
- Update existing tests, ensure `make test-python-gai` and `make lint-python-lite` pass

---

## Phase 2: Claude Code Provider Implementation

**Goal:** Implement the Claude Code backend against the Phase 1 abstraction.

- Implement `ClaudeCodeProvider` class (subprocess to `claude` CLI, stdin/stdout protocol)
- Map model tiers to Claude models (large→opus, small→haiku or sonnet)
- Handle Claude Code-specific flags, environment variables, and output format
- Add provider selection to `gai.yml` config + update `gai.schema.json`
- Update CLI `--model-size` arg to work with the new tier system
- Ensure prompt pre-processing (xprompt expansion, file references, Jinja2) remains provider-agnostic

---

## Phase 3: VCS Operation Inventory & Abstraction Layer

**Goal:** Catalog every VCS operation gai performs, then define an abstract VCS interface.

- Audit all `bb_hg_*` script usages and direct `hg` subprocess calls across the codebase
- Group operations into categories: diff, commit/amend, checkout/update, reword, clean, archive, log/history, status,
  mail/upload
- Define a `VCSProvider` abstract base class with methods for each operation category
- Refactor existing hg code into an `HgProvider` implementation
- Create a VCS provider registry/factory (auto-detect from `.hg` vs `.git`)

**Key files to audit:**

- `src/commit_utils/workspace.py` (diff, clean, import)
- `src/commit_workflow/` (commit creation, CL formatting)
- `src/amend_workflow.py` (amend operations)
- `src/rewind_workflow.py` (revert operations)
- `src/ace/operations.py` (bb_hg_update)
- `src/ace/mail_ops.py` (bb_hg_reword, upload)
- Shell scripts: `home/bin/executable_bb_hg_*`

### Phase 3.1: Complete VCS Operation Audit

**Goal:** Finalize the catalog of every VCS touchpoint with classification.

- Produce a reference table of every VCS call site: file, command, conceptual category, and tier (Core / Google-internal
  / Composite)
- Core = has git equivalent (`hg diff`, `hg update`, `hg addremove`, `hg import`, `hg commit`, `hg amend`, `hg rebase`)
- Google-internal = no git equivalent (`hg evolve`, `hg upload tree`, `hg cls-*`, `hg fix`, `hg lint`, `hg presubmit`)
- Composite = shell scripts chaining multiple ops (`bb_hg_clean`, `bb_hg_amend`, `bb_hg_sync`, etc.)
- Also catalog VCS-coupled shell helpers: `branch_name`, `branch_number`, `get_all_cl_names`, `cl_desc`,
  `branch_local_changes`

### Phase 3.2: Define VCSProvider Interface & Data Types

**Goal:** Create the abstract `VCSProvider` ABC and supporting types in a new `src/vcs_provider/` package, without
touching existing consumers.

- New files: `_base.py` (ABC), `_types.py` (`CommandResult` dataclass), `_registry.py` (factory w/ auto-detect),
  `_errors.py`, `__init__.py`
- Follow the `BaseWorkflow(ABC)` pattern from `src/workflow_base.py`
- Group methods by category: core ops (diff, checkout, apply_patch, clean, add_remove, commit, amend, reword, rebase,
  rename_branch), composite ops (stash_and_clean, amend_and_upload, sync, archive, prune, unamend), info queries
  (get_branch_name, get_description, has_local_changes), and Google-internal ops (upload, evolve, fix, lint, presubmit —
  with default `NotImplementedError`)
- All methods take explicit `cwd` parameter, return `CommandResult(success, error, stdout, stderr)` — matching existing
  `(bool, str)` conventions in `gai_utils.py`

### Phase 3.3: Implement HgProvider

**Goal:** Implement `HgProvider(VCSProvider)` by extracting existing subprocess logic into provider methods. No call
sites change yet.

- New file: `src/vcs_provider/_hg.py`
- Mechanical extraction: lift subprocess calls from `commit_utils/workspace.py`, `ace/operations.py`,
  `ace/handlers/show_diff.py`, `commit_workflow/workflow.py`, `commit_workflow/branch_info.py`
- Wrap `bb_hg_*` script invocations for composite ops
- Register with auto-detect: check for `.hg/` directory
- Unit tests: `test/test_vcs_provider_hg.py` — mock subprocess, verify correct commands

### Phase 3.4: Migrate Call Sites to VCSProvider

**Goal:** Replace all direct `hg`/`bb_hg_*` calls in Python with `VCSProvider` method calls.

- Migrate in tiers:
  1. Low-level utils: `commit_utils/workspace.py`, `commit_workflow/branch_info.py`
  2. Core ops: `ace/operations.py`, `ace/handlers/show_diff.py`
  3. Workflows: `commit_workflow/workflow.py`, `amend_workflow.py`, `rewind_workflow/workflow.py`,
     `accept_workflow/workflow.py`
  4. TUI/scheduler: `ace/handlers/` (mail, reword, workflow_handlers), `ace/mail_ops.py`, `ace/archive.py`,
     `ace/scheduler/` (hooks_runner, mentor_runner, workflows_runner), `ace/tui/actions/`
- Provider obtained via `get_vcs_provider(cwd)` — most call sites already have `workspace_dir`
- Update existing test mocks accordingly

### Phase 3.5: Validation & Cleanup

**Goal:** Verify no direct VCS calls remain, remove dead code, ensure tests pass.

- Grep for residual `bb_hg_`/`"hg "` calls outside `_hg.py` — should find zero
- Remove superseded functions from `workspace.py`, `operations.py` if fully delegated
- Run `make test-python-gai` and `make lint-python-lite`
- Maintain test coverage threshold

---

## Phase 4: Git VCS Provider Implementation

**Goal:** Implement the git backend against the Phase 3 abstraction.

- Implement `GitProvider` class mapping each VCS operation to git equivalents:
  - `hg diff` → `git diff`
  - `bb_hg_update <CL>` → `git checkout <branch>` / `git switch <branch>`
  - `bb_hg_amend` → `git commit --amend`
  - `bb_hg_reword` → `git commit --amend` (message only)
  - `bb_hg_clean` → `git stash` or `git checkout -- .`
  - `bb_hg_archive` → `git branch -d` + tag for archival
  - `hg import --no-commit` → `git apply`
  - Workspace management: `hg` workspaces → `git worktrees`
- Create `bb_git_*` wrapper scripts where needed, or inline logic into the provider
- Handle differences in diff format between hg and git (already partially supported in `mentor_checks.py`)

---

## Phase 5: ChangeSpec Model Generalization

**Goal:** Generalize the ChangeSpec/CL model so it maps to git branches + PRs.

- Abstract the CL concept: in hg, a CL is a commit with a description; in git, it's a branch with a PR
- Map ChangeSpec STATUS transitions to PR lifecycle:
  - Unstarted → branch not yet created
  - In Progress → branch exists, no PR yet
  - Drafted → draft PR created
  - Mailed → PR open for review
  - Submitted → PR merged
- Generalize `cl_desc` to read from either hg commit descriptions or git branch metadata / PR descriptions
- Generalize `commit_workflow/cl_formatting.py` to format both hg commit messages and git commit messages + PR bodies
- Generalize the COMMITS suffix tracking for git (amend history)
- Update `get_all_cl_names` → works with both hg bookmarks and git branches
- Update `is_cl_submitted` → checks hg submission status or PR merge status (via `gh` CLI or git API)

**Key files:**

- `src/ace/changespec/models.py` (ChangeSpec data model)
- `src/ace/changespec/parser.py` (parsing ChangeSpec files)
- `src/commit_workflow/cl_formatting.py` (CL description formatting)
- `src/status_state_machine/` (status transitions)

---

## Phase 6: ace TUI & axe Scheduler Generalization

**Goal:** Update the interactive TUI and scheduler daemon to work with both backends.

- **ace TUI:**
  - Display branch name / PR URL instead of CL number where applicable
  - Update navigation (bb_hg_update → VCS-agnostic checkout)
  - Update diff display to handle both diff formats
  - Generalize any hg-specific status indicators

- **axe Scheduler:**
  - Generalize CL status checking (hg CL status → PR status via `gh` CLI)
  - Generalize comment monitoring (hg comments → PR review comments)
  - Update hook execution to work in git repos
  - Generalize workspace management for concurrent operations

- **Workflow YAML files:**
  - Audit xprompts/ for VCS-specific references
  - Parameterize or conditionalize VCS-specific workflow steps

**Key files:**

- `src/ace/tui/` (TUI widgets, actions, models)
- `src/axe/` (scheduler, check cycles, hook jobs)
- `xprompts/*.yml` (workflow definitions)

---

## Phase 7: Configuration & Auto-Detection

**Goal:** Make backend selection seamless via config and auto-detection.

- **Auto-detection:** Check for `.git/` vs `.hg/` in the repo root to select VCS provider automatically
- **gai.yml schema updates:**
  - Add `llm_provider` section: provider name, model mappings, CLI path overrides
  - Add `vcs_provider` section: provider name (or "auto"), provider-specific options
- **Environment variables:** Generalize from `GAI_BIG_GEMINI_ARGS` to provider-agnostic equivalents (e.g.,
  `GAI_LLM_LARGE_ARGS`) while keeping old vars as fallbacks for the Gemini provider
- **CLI updates:** Update `--model-size` and any VCS-specific flags in `src/main/parser.py`
- Update `gai.schema.json` for all config changes

---

## Phase 8: Testing & Validation

**Goal:** Ensure both backends work correctly and coexist without regressions.

- Add unit tests for provider abstractions (LLM + VCS interfaces)
- Add unit tests for each provider implementation (mock subprocess calls)
- Update existing tests that assume Gemini/hg to be parameterized across providers
- Add integration test fixtures that exercise git workflows end-to-end
- Ensure `make test-python-gai` and `make lint-python-lite` pass
- Maintain or exceed current test coverage threshold

---

## Suggested execution order

Phases 1-2 (LLM) and Phases 3-4 (VCS) are largely independent and could be worked on in parallel. Phase 5 depends on
Phase 3-4. Phase 6 depends on Phases 1-5. Phases 7-8 can be woven in incrementally.

```
Phase 1 (LLM abstraction) ──→ Phase 2 (Claude Code impl)
                                                          ╲
Phase 3 (VCS abstraction) ──→ Phase 4 (Git impl) ──→ Phase 5 (ChangeSpec) ──→ Phase 6 (TUI/Scheduler)
                                                                                        ↓
                                                                              Phase 7 (Config) ──→ Phase 8 (Testing)
```

Testing should happen incrementally within each phase, with Phase 8 being the final comprehensive pass.
