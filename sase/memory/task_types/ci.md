---
keyword: CI failure
summary: A confirmed true test or lint failure you did not cause, not a flake.
metadata:
  generated_by: sase.task_types.generated-strand.v1
  task_type: ci
---

## Identity

- Task type: `ci`
- Label: CI failure
- Glyph: ⚙
- Accent color: `#D7D700`
- Agent creatable: yes
- Show schema version: `1`
- Digest: `7bb84890e8db43abd920cf3af5952ab7a95dd432e66e38018d547e6c1993bd33`

## Summary

A confirmed true test or lint failure you did not cause, not a flake.

## When To Use

File one when a test or lint failed and you confirmed it is a true failure, not a flake.
Record the pytest node ID, the failing SHA if known, and why this is not intermittent.
Use flake instead when a rerun on the same tree passed.

## Related Task Types

- [[task_types/flake]]

## Fields

**Field `node_id`**

- Name: `node_id`
- Label: Test node ID
- Type: `string`
- Required: yes
- Roles: `data`, `template`
- Help: The pytest node ID, e.g. tests/foo.py::test_bar
- Validators: (none)

**Field `sha`**

- Name: `sha`
- Label: SHA
- Type: `string`
- Required: no
- Roles: `data`
- Help: Commit SHA where the failure was observed
- Validators: (none)

**Field `why_not_flake`**

- Name: `why_not_flake`
- Label: Why not a flake
- Type: `string`
- Required: yes
- Roles: `template`
- Help: Why this is a confirmed true failure rather than a flake
- Validators: (none)

## Body Template

```markdown
## CI failure

- **Node:** `{{ node_id }}`

{{ why_not_flake }}
```

## Triage

- min_plus_ones: `0`

## Provenance

- Provenance label: `builtin:sase`
- Source: `builtin`
- Package: `sase`
