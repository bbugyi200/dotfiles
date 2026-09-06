---
keyword: Bug
summary:
  A defect an agent found while doing unrelated work, not an external tracker bug.
metadata:
  generated_by: sase.task_types.generated-strand.v1
  task_type: bug
---

## Identity

- Task type: `bug`
- Label: Bug
- Glyph: ⨯
- Accent color: `#FF5F5F`
- Agent creatable: yes
- Show schema version: `1`
- Digest: `d7a5c9f46756d566c0c277ab62306d375397522ef5bf82db26a771bea938dda6`

## Summary

A defect an agent found while doing unrelated work, not an external tracker bug.

## When To Use

File one when you found a defect while doing unrelated work and it is not an external
tracker issue. Record where it lives, how to reproduce it, and who it hurts; one
independent reproduction separates it from a misreading. Do not use this for a flake, a
confirmed CI failure, or a GitHub-mirrored bug.

## Related Task Types

- [[task_types/ci]]
- [[task_types/flake]]

## Fields

**Field `location`**

- Name: `location`
- Label: Location
- Type: `string`
- Required: yes
- Roles: `data`, `template`
- Help: File, symbol, or other locator for the defect
- Validators: (none)

**Field `repro`**

- Name: `repro`
- Label: Repro
- Type: `string`
- Required: yes
- Roles: `template`
- Help: Steps or command that reproduce the defect
- Validators: (none)

**Field `impact`**

- Name: `impact`
- Label: Impact
- Type: `string`
- Required: no
- Roles: `template`
- Help: Who or what the defect breaks, and how badly
- Validators: (none)

## Body Template

```markdown
## Bug

- **Location:** `{{ location }}`

{{ repro }}

{{ impact }}
```

## Triage

- min_plus_ones: `1`

## Provenance

- Provenance label: `builtin:sase`
- Source: `builtin`
- Package: `sase`
