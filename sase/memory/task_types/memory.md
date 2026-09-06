---
keyword: Memory
summary: A sase memory note or skill that is out of date.
metadata:
  generated_by: sase.task_types.generated-strand.v1
  task_type: memory
---

## Identity

- Task type: `memory`
- Label: Memory
- Glyph: ▤
- Accent color: `#8787FF`
- Agent creatable: yes
- Show schema version: `1`
- Digest: `37366acc1543cf5793a8c8d9c2cdca3f9583ee1f30b8ca9fce3936bc88da52be`

## Summary

A sase memory note or skill that is out of date.

## When To Use

File one when a sase memory file or skill contains out-of-date information that should
be updated. Closing still requires explicit user permission plus `sase memory init`.
Record the memory path and the proposed change.

## Fields

**Field `path`**

- Name: `path`
- Label: Path
- Type: `string`
- Required: yes
- Roles: `data`, `template`
- Help: Memory note path relative to memory/, e.g. sase_beads.md
- Validators: (none)

**Field `proposed_change`**

- Name: `proposed_change`
- Label: Proposed change
- Type: `string`
- Required: yes
- Roles: `template`
- Help: The correction the memory note should receive
- Validators: (none)

## Body Template

```markdown
## Memory update

- **Path:** `{{ path }}`

{{ proposed_change }}
```

## Triage

- min_plus_ones: `0`

## Provenance

- Provenance label: `builtin:sase`
- Source: `builtin`
- Package: `sase`
