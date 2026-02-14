# Plan: Migrate .gp Project Spec Files to YAML

## Context

The gai project uses a custom `.gp` text format for project specification files at `~/.gai/projects/<name>/<name>.gp`.
This format is parsed line-by-line and written via raw text manipulation across 16+ callsites. Migrating to YAML with a
JSON Schema provides:

- Machine-readable schema validation
- Structured read/write (no more brittle regex/text manipulation)
- Standard tooling support (YAML editors, linters)

The TUI display will remain unchanged -- this is purely an on-disk format migration.

## Phased Approach

**Phase 1** (this plan): Schema + ProjectSpec model + YAML parser + YAML serializer + structured update API + migration
script + tests. The infrastructure for .yaml files, but the system continues to read both formats.

**Phase 2** (follow-up): Convert all 16 writer callsites to use structured updates, switch default format to .yaml.

**Phase 3** (follow-up): Update all tests, remove .gp parser, update documentation.

---

## Phase 1 Implementation

### Step 1: ProjectSpec + WorkspaceClaim Models

**File**: `home/lib/gai/src/ace/changespec/project_spec.py` (NEW)

Add top-level dataclasses that wrap the existing `ChangeSpec` hierarchy:

```python
@dataclass
class WorkspaceClaim:
    workspace_num: int
    pid: int
    workflow: str
    cl_name: str | None = None
    artifacts_timestamp: str | None = None

@dataclass
class ProjectSpec:
    file_path: str
    bug: str | None = None
    running: list[WorkspaceClaim] | None = None
    changespecs: list[ChangeSpec] | None = None
```

`WorkspaceClaim` replaces the private `_WorkspaceClaim` in `running_field.py` (same fields). The `_WorkspaceClaim` in
`running_field.py` stays for now (Phase 2 migrates it).

### Step 2: JSON Schema

**File**: `home/lib/gai/xprompts/project_spec.schema.json` (NEW)

JSON Schema Draft-07 (matching `workflow.schema.json` pattern). Defines:

- Top level: `bug` (string|null), `running` (array of workspace claims), `changespecs` (array)
- ChangeSpec: `name`, `description`, `parent`, `cl`, `status`, `test_targets`, `kickstart`, `commits`, `hooks`,
  `comments`, `mentors`
- Nested types: `commit_entry`, `hook_entry`, `hook_status_line`, `comment_entry`, `mentor_entry`, `mentor_status_line`
- All fields match the existing dataclass hierarchy in `models.py`

### Step 3: YAML Parser

**File**: `home/lib/gai/src/ace/changespec/project_spec.py` (continued)

```python
def parse_project_spec(file_path: str) -> ProjectSpec:
    """Parse a YAML project spec file."""
    # yaml.safe_load() -> dict -> construct ProjectSpec with nested dataclasses
```

Key behaviors:

- Uses `yaml.safe_load()` (already used throughout codebase with `import yaml  # type: ignore[import-untyped]`)
- Constructs `ChangeSpec` objects with `file_path` set to the YAML file path and `line_number=0` (not meaningful for
  YAML)
- Sets `bug` on each ChangeSpec from the top-level `bug` field (matching current parser behavior)
- Returns empty `ProjectSpec` for empty/missing files

### Step 4: YAML Serializer

**File**: `home/lib/gai/src/ace/changespec/project_spec.py` (continued)

```python
def serialize_project_spec(spec: ProjectSpec) -> str:
    """Serialize a ProjectSpec to YAML string."""
    # Convert dataclass tree -> dict (omitting None values and metadata fields)
    # yaml.dump() with block style, no flow, sort_keys=False
```

Key behaviors:

- Omits `None` values from output (clean YAML, no `null` noise)
- Omits metadata fields: `file_path`, `line_number` from ChangeSpec
- Multi-line descriptions use YAML literal block style (`|`)
- Key ordering: name, description, parent, cl, status, test_targets, kickstart, commits, hooks, comments, mentors
- Uses `yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)`

### Step 5: Write Function

**File**: `home/lib/gai/src/ace/changespec/project_spec.py` (continued)

```python
def write_project_spec_atomic(
    project_file: str, spec: ProjectSpec, commit_message: str
) -> None:
    """Serialize and write a ProjectSpec atomically with git commit."""
    content = serialize_project_spec(spec)
    write_changespec_atomic(project_file, content, commit_message)
```

Also add a convenience function for structured updates:

```python
def read_and_update_project_spec(
    project_file: str,
    update_fn: Callable[[ProjectSpec], ProjectSpec],
    commit_message: str,
) -> None:
    """Read, update, and write a project spec atomically (with locking)."""
    with changespec_lock(project_file):
        spec = parse_project_spec(project_file)
        updated = update_fn(spec)
        write_project_spec_atomic(project_file, updated, commit_message)
```

### Step 6: Structured Update Functions

**File**: `home/lib/gai/src/ace/changespec/structured_updates.py` (NEW)

Provides the structured API that Phase 2 writers will use. Each function takes a `ProjectSpec`, modifies it immutably
(returns a new one), and returns the result:

- `update_changespec_status(spec, cs_name, new_status) -> ProjectSpec`
- `update_changespec_cl(spec, cs_name, new_cl) -> ProjectSpec`
- `update_changespec_parent(spec, cs_name, new_parent) -> ProjectSpec`
- `update_changespec_description(spec, cs_name, new_description) -> ProjectSpec`
- `update_changespec_hooks(spec, cs_name, hooks) -> ProjectSpec`
- `update_changespec_comments(spec, cs_name, comments) -> ProjectSpec`
- `update_changespec_mentors(spec, cs_name, mentors) -> ProjectSpec`
- `add_changespec_commit_entry(spec, cs_name, entry) -> ProjectSpec`
- `update_commit_entry_suffix(spec, cs_name, entry_id, ...) -> ProjectSpec`
- `add_running_claim(spec, claim) -> ProjectSpec`
- `remove_running_claim(spec, workspace_num, ...) -> ProjectSpec`
- `update_parent_references(spec, old_name, new_name) -> ProjectSpec`

Helper: `_find_changespec(spec, cs_name) -> tuple[int, ChangeSpec]` to locate a ChangeSpec by name.

### Step 7: Backward Compatibility

**File**: `home/lib/gai/src/ace/changespec/parser.py` (MODIFY)

Update `parse_project_file()` to dispatch based on extension:

```python
def parse_project_file(file_path: str) -> list[ChangeSpec]:
    if file_path.endswith(".yaml") or file_path.endswith(".yml"):
        spec = parse_project_spec(file_path)
        return spec.changespecs or []
    else:
        # Existing .gp parser (unchanged)
        return _parse_gp_project_file(file_path)
```

Rename the existing implementation to `_parse_gp_project_file()`.

**File**: `home/lib/gai/src/ace/changespec/__init__.py` (MODIFY)

Update `find_all_changespecs()` to prefer `.yaml` over `.gp`:

```python
yaml_file = project_dir / f"{project_name}.yaml"
gp_file = project_dir / f"{project_name}.gp"
if yaml_file.exists():
    changespecs = parse_project_file(str(yaml_file))
elif gp_file.exists():
    changespecs = parse_project_file(str(gp_file))
```

Re-export new symbols: `ProjectSpec`, `WorkspaceClaim`, `parse_project_spec`, `serialize_project_spec`,
`write_project_spec_atomic`, `read_and_update_project_spec`.

**File**: `home/lib/gai/src/ace/changespec/locking.py` (MODIFY)

Update `write_changespec_atomic()`: change temp file suffix from `.gp` to match the target file extension (use
`os.path.splitext()`).

### Step 8: Migration Script

**File**: `home/bin/executable_gai_migrate_gp_to_yaml` (NEW)

Standalone Python script:

```
#!/usr/bin/env python3
"""Migrate .gp project spec files to YAML format.

Usage:
    gai_migrate_gp_to_yaml [--dry-run] [--remove-old] [--project NAME]
"""
```

Algorithm:

1. Find all `~/.gai/projects/<name>/<name>.gp` files
2. For each: a. Parse with old `.gp` parser -> `list[ChangeSpec]` b. Parse RUNNING field separately using
   `running_field.get_claimed_workspaces()` c. Extract top-level BUG from first ChangeSpec's `.bug` field d. Construct
   `ProjectSpec(bug=bug, running=claims, changespecs=changespecs)` e. Serialize to YAML f. Validate against JSON schema
   using `jsonschema.validate()` g. Write to `<name>.yaml` h. **Round-trip verify**: parse the new `.yaml` file, compare
   ChangeSpec fields i. If `--remove-old`: remove the `.gp` file
3. Git commit all changes in `~/.gai`
4. Print summary

Flags:

- `--dry-run`: print what would happen, don't write
- `--remove-old`: delete `.gp` files after successful migration
- `--project NAME`: only migrate a specific project

### Step 9: Tests

**File**: `home/lib/gai/test/test_project_spec.py` (NEW)

Round-trip serialization tests:

- Empty ProjectSpec
- ProjectSpec with bug only
- Full ProjectSpec with all ChangeSpec fields
- Multi-line descriptions (YAML literal blocks)
- All suffix types (error, running_agent, killed_agent, etc.)
- CommitEntry with proposal_letter, chat, diff
- HookEntry with status_lines (all statuses: RUNNING, PASSED, FAILED, DEAD, KILLED)
- HookStatusLine with compound suffix (summary field)
- CommentEntry with/without suffix
- MentorEntry with is_wip, multiple profiles
- RUNNING field with workspace claims
- None/null handling (omitted from YAML, round-trips correctly)

**File**: `home/lib/gai/test/test_structured_updates.py` (NEW)

Structured update tests:

- Each update function with happy path
- Update non-existent ChangeSpec (error handling)
- Add commit entry to ChangeSpec without existing commits
- Running claim add/remove
- Parent reference updates

**File**: `home/lib/gai/test/test_migration.py` (NEW)

Migration logic tests:

- Convert a sample `.gp` string -> ProjectSpec -> YAML -> parse back -> verify equality
- Handle empty .gp files
- Handle .gp files with RUNNING field

### Step 10: Update `__init__.py` Exports

**File**: `home/lib/gai/src/ace/changespec/__init__.py` (MODIFY)

Add exports for all new public symbols from `project_spec.py` and `structured_updates.py`.

---

## YAML Output Example

```yaml
bug: "12345"
running:
  - workspace: 1
    pid: 45678
    workflow: crs
    cl_name: my_feature
changespecs:
  - name: my_project_add_config
    description: |
      Add configuration file parser

      Detailed description body here with multiple lines
      and paragraphs.
    parent: my_project_base_setup
    cl: http://cl/99999
    status: WIP
    test_targets:
      - //myapp:test
    commits:
      - number: 1
        note: Initial implementation
        chat: ~/.gai/chats/proj-251230_123456.md
        diff: ~/.gai/diffs/proj_feature-251230_123456.diff
      - number: 1
        proposal_letter: a
        note: Fix review comments
        suffix: NEW PROPOSAL
        suffix_type: error
    hooks:
      - command: "!$bb_hg_presubmit"
        status_lines:
          - commit_entry_num: "1"
            timestamp: "240601_123456"
            status: PASSED
            duration: 1m23s
      - command: bb_hg_lint
    comments:
      - reviewer: critique
        file_path: ~/.gai/comments/proj-critique-251230.json
    mentors:
      - entry_id: "1"
        profiles:
          - code_quality
        status_lines:
          - profile_name: code_quality
            mentor_name: pylint
            status: PASSED
            timestamp: "240601_123456"
            duration: 0h2m15s
```

## Critical Files Summary

| File                                                    | Action | Purpose                                                    |
| ------------------------------------------------------- | ------ | ---------------------------------------------------------- |
| `home/lib/gai/src/ace/changespec/project_spec.py`       | NEW    | ProjectSpec model, YAML parser, serializer, write function |
| `home/lib/gai/src/ace/changespec/structured_updates.py` | NEW    | Structured update API for all ChangeSpec field operations  |
| `home/lib/gai/xprompts/project_spec.schema.json`        | NEW    | JSON Schema for YAML validation                            |
| `home/bin/executable_gai_migrate_gp_to_yaml`            | NEW    | Migration script                                           |
| `home/lib/gai/src/ace/changespec/parser.py`             | MODIFY | Dispatch .yaml/.gp by extension                            |
| `home/lib/gai/src/ace/changespec/__init__.py`           | MODIFY | Find .yaml files, re-export new symbols                    |
| `home/lib/gai/src/ace/changespec/locking.py`            | MODIFY | Fix temp file suffix                                       |
| `home/lib/gai/test/test_project_spec.py`                | NEW    | Round-trip serialization tests                             |
| `home/lib/gai/test/test_structured_updates.py`          | NEW    | Structured update tests                                    |
| `home/lib/gai/test/test_migration.py`                   | NEW    | Migration logic tests                                      |

## Existing Code to Reuse

- `ChangeSpec`, `CommitEntry`, `HookEntry`, `HookStatusLine`, `CommentEntry`, `MentorEntry`, `MentorStatusLine` from
  `home/lib/gai/src/ace/changespec/models.py`
- `changespec_lock`, `write_changespec_atomic` from `home/lib/gai/src/ace/changespec/locking.py`
- `parse_project_file` from `home/lib/gai/src/ace/changespec/parser.py` (for .gp backward compat)
- `_WorkspaceClaim.from_line` pattern from `home/lib/gai/src/running_field.py` (for migration script RUNNING field
  parsing)
- `get_claimed_workspaces` from `home/lib/gai/src/running_field.py` (migration script)
- `yaml.safe_load` / `yaml.dump` (already used in 12+ files, e.g. `home/lib/gai/src/shared_utils.py`)
- `jsonschema.validate` (already used in `home/lib/gai/src/xprompt/output_validation.py`)

## Verification

1. **Unit tests**: `make test-python-gai` -- round-trip, structured updates, migration
2. **Schema validation**: Migration script validates each .yaml file against schema
3. **Round-trip fidelity**: Parse .gp -> construct ProjectSpec -> serialize YAML -> parse YAML -> compare all ChangeSpec
   fields
4. **Backward compat**: Existing tests still pass (they use .gp files, parser still reads both)
5. **Manual test**: Run migration script with `--dry-run` on real `~/.gai/projects/` data
6. **Linting**: `make lint-python-lite`
