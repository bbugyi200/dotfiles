# Migration Plan: gai → sase

## Context

The `gai` project (~79K lines, 334 source files, 197 test files) currently lives at `~/lib/gai/` as part of the chezmoi
dotfiles repo. It has no proper Python packaging — it's run via a `pybash` script that manages a venv and sets
PYTHONPATH.

**Goal**: Migrate to `~/projects/github/bbugyi200/sase/` as a standalone Git repo with proper modern Python packaging,
rename all "gai" references to "sase" (Structured Agentic Software Engineering), and ensure infrastructure quality
matches or exceeds the original.

**Scope**: Only the new sase repo. Chezmoi references (~/bin/gai\*, targets.mk) will be updated separately later. Config
paths (`~/.config/gai` → `~/.config/sase`, `~/.gai` → `~/.sase`) will be renamed. Only src/, test/, docs/, and xprompts/
are migrated (not chats/, plans/, prompts/).

---

## Phase 1: Project Scaffolding & Infrastructure

**Goal**: Create the full project skeleton with modern Python packaging and CI, modeled after the `zorg` project at
`~/projects/github/bbugyi200/zorg/`.

### Files to Create

| File                       | Based on                         | Notes                                                                                                  |
| -------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `pyproject.toml`           | zorg's pyproject.toml + setup.py | Modern `[project]` table, `[project.scripts]` entry point, setuptools backend, ruff/black/isort config |
| `setup.cfg`                | zorg's setup.cfg                 | coverage, pytest, flake8, mypy config                                                                  |
| `tox.ini`                  | zorg's tox.ini                   | py312, py313 envs                                                                                      |
| `Makefile`                 | zorg's Makefile                  | Docker switching pattern                                                                               |
| `targets.mk`               | zorg's targets.mk                | Adapt targets: build, test, lint (ruff, black, flake8, mypy), fix                                      |
| `.github/workflows/ci.yml` | zorg's ci.yml                    | test + lint + publish jobs                                                                             |
| `.gitignore`               | Standard Python                  | venv, **pycache**, dist, \*.egg-info, htmlcov, .tox                                                    |
| `README.md`                | —                                | Project description, installation, usage                                                               |
| `CLAUDE.md`                | gai's CLAUDE.md + lib/CLAUDE.md  | Adapted coding guidelines and schema references                                                        |
| `requirements.in`          | gai's requirements.txt           | Runtime deps: jinja2, jsonschema, langgraph, langchain-core, rich, schedule, textual>=0.45.0, pyyaml   |
| `requirements-dev.in`      | zorg's requirements-dev.in       | pytest, pytest-cov, tox, ruff, black, flake8, mypy, etc.                                               |
| `.pylintrc`                | zorg's .pylintrc                 | Adapted                                                                                                |
| `src/sase/__init__.py`     | —                                | Package init with `__version__`                                                                        |
| `src/sase/py.typed`        | —                                | PEP 561 marker                                                                                         |

### Key pyproject.toml Decisions

- **Build backend**: setuptools (matching zorg)
- **Entry point**: `[project.scripts] sase = "sase.main.entry:main"`
- **Python requires**: `>=3.12`
- **Version**: `setuptools_scm` from git tags, fallback `0.1.0`

### Actions

1. Create all files listed above
2. Set up GitHub remote: `gh repo create bbugyi200/sase --private --source=.`
3. `pip install -e .` to verify packaging skeleton works
4. Commit: "Initial project scaffolding for sase"

---

## Phase 2: Migrate & Rename Source Code

**Goal**: Copy all 334 Python source files from `~/lib/gai/src/` into `src/sase/`, restructure imports for proper
packaging, and rename all `gai` references to `sase`.

### Import Restructuring

The original code uses flat imports via PYTHONPATH (e.g., `from ace.changespec import ChangeSpec`). In the new package,
these become `from sase.ace.changespec import ChangeSpec`.

**Strategy**: For every `.py` file in src/sase/:

1. Identify all intra-package imports (imports that reference other modules within the project)
2. Prefix them with `sase.` (e.g., `from ace.foo import bar` → `from sase.ace.foo import bar`)
3. The `__main__.py` import changes: `from main.entry import main` → `from sase.main.entry import main`

### Rename Operations

| What         | From                        | To                           |
| ------------ | --------------------------- | ---------------------------- |
| Files        | `gai_utils.py`              | `sase_utils.py`              |
| Files        | `gai_migrate_gp_to_yaml.py` | `sase_migrate_gp_to_yaml.py` |
| Functions    | `get_gai_directory()`       | `get_sase_directory()`       |
| Functions    | `ensure_gai_directory()`    | `ensure_sase_directory()`    |
| Config paths | `~/.config/gai/`            | `~/.config/sase/`            |
| Data paths   | `~/.gai/`                   | `~/.sase/`                   |
| Env vars     | `GAI_VCS_PROVIDER`          | `SASE_VCS_PROVIDER`          |
| CLI prog     | `prog="gai"`                | `prog="sase"`                |
| Docstrings   | "GAI" / "gai"               | "SASE" / "sase"              |
| State dirs   | `~/.axe_state/`             | Review — may keep or rename  |

### Approach

1. `cp -r ~/lib/gai/src/* ~/projects/github/bbugyi200/sase/src/sase/`
2. Run a Python script to perform all import rewrites and gai→sase renames across all files
3. Manual review of edge cases (strings that contain "gai" as part of other words, e.g. "again")
4. Commit: "Migrate and rename source code from gai to sase"

### Critical Source Files (highest gai reference counts)

- `src/sase/shared_utils.py` (17 refs)
- `src/sase/gemini_wrapper/file_references.py` (17 refs)
- `src/sase/xprompt/loader.py` (14 refs)
- `src/sase/ace/query/evaluator.py` (12 refs)
- `src/sase/main/entry.py` — CLI entry point
- `src/sase/main/parser.py` — argparse with `prog="gai"`
- `src/sase/sase_utils.py` — core utilities with directory helpers

---

## Phase 3: Migrate & Rename Tests

**Goal**: Copy all 197 test files from `~/lib/gai/test/` into `tests/`, update imports and rename references.

### Actions

1. `cp -r ~/lib/gai/test/* ~/projects/github/bbugyi200/sase/tests/`
2. Update all imports:
   - `from gai_utils import ...` → `from sase.sase_utils import ...`
   - `from ace.foo import ...` → `from sase.ace.foo import ...`
   - All other intra-package imports get `sase.` prefix
3. Rename `test_gai_utils.py` → `test_sase_utils.py`
4. Rename all `gai` references in test strings, assertions, mock paths
5. Update `conftest.py` for new package structure
6. Run `pytest tests/` to verify tests pass (fix failures as needed)
7. Commit: "Migrate and rename tests from gai to sase"

---

## Phase 4: Migrate Supporting Files

**Goal**: Copy docs, xprompts, and schema files. Rename all gai references.

### Files to Migrate

**docs/** (7 files):

- `change_spec.md`, `llms.md`, `project_spec.md`, `vcs.md`, `workflow_spec.md`
- `vcs_llms_problems.md`, `vcs_llms_problems_critique.md`

**xprompts/** (18 files):

- Workflow definitions: `amend.yml`, `commit.yml`, `crs.md`, `fix_hook.md`, `mentor.md`, `propose.yml`, `split.yml`,
  etc.
- Schema files: `workflow.schema.json`, `project_spec.schema.json`

**Also migrate**:

- `home/dot_config/gai/gai.schema.json` → `config/sase.schema.json` (or similar location in the repo)
- Any README.md files inside src/ subdirectories (e.g., `src/ace/README.md`, `src/ace/CLAUDE.md`)

### Actions

1. Copy docs/ and xprompts/ directories
2. Rename all gai→sase references in all files
3. Update CLAUDE.md schema path references
4. Commit: "Migrate supporting files from gai to sase"

---

## Phase 5: Verification & Final Polish

**Goal**: Ensure no remaining `gai` references, all tests pass, linters are clean, and packaging works.

### Verification Checklist

1. **No gai references**: `rg gai ~/projects/github/bbugyi200/sase` — must return empty (excluding false positives like
   "again", "regain", etc.)
2. **Packaging works**: `pip install -e .` succeeds
3. **Entry point works**: `sase --help` runs and shows SASE description
4. **Tests pass**: `make test` or `pytest tests/`
5. **Linters pass**: `make lint` (ruff, black, flake8, mypy)
6. **CI works**: Push to GitHub, verify Actions pass

### Potential False Positives for `rg gai`

Words containing "gai" that are NOT references to the old project name:

- "again", "regain", "against" — these should be left as-is
- The regex `\bgai\b` (word boundary) is more accurate for finding true references

### Actions

1. Run `rg '\bgai\b' ~/projects/github/bbugyi200/sase` (case-insensitive) and fix any remaining references
2. Run `rg 'gai_' ~/projects/github/bbugyi200/sase` to catch function/variable prefixes
3. Run `rg '\.gai' ~/projects/github/bbugyi200/sase` to catch config paths
4. Run `rg 'GAI' ~/projects/github/bbugyi200/sase` to catch env vars and uppercase references
5. Fix all issues found
6. Run full test suite and linters
7. Fix any failures
8. Final commit: "Final verification and polish"
9. Push to GitHub

---

## Summary

| Phase | Description                          | Estimated Scope                     |
| ----- | ------------------------------------ | ----------------------------------- |
| 1     | Project scaffolding & infrastructure | ~15 new files                       |
| 2     | Migrate & rename source code         | ~334 Python files                   |
| 3     | Migrate & rename tests               | ~197 Python files                   |
| 4     | Migrate supporting files             | ~25 files (docs, xprompts, schemas) |
| 5     | Verification & final polish          | Audit + fixes                       |

Each phase is designed to be run by a separate Claude Code agent in a new session. The plan file for each phase should
reference this document and include the specific instructions for that phase.
