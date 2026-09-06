---
keyword: Feature
summary: An out-of-scope product or tooling idea that should not become a wish list.
metadata:
  generated_by: sase.task_types.generated-strand.v1
  task_type: feature
---

## Identity

- Task type: `feature`
- Label: Feature
- Glyph: ✦
- Accent color: `#5FD75F`
- Agent creatable: yes
- Show schema version: `1`
- Digest: `4b065df3f621cb1dec1e93f80b8b45b4525ec720aac1f252f5d2b7d196d07507`

## Summary

An out-of-scope product or tooling idea that should not become a wish list.

## When To Use

File one when you discovered a product or capability idea that is outside the current
task or epic. State the proposal and why it is out of scope for the work you were doing.
Do not file one for in-scope follow-up that belongs on the current epic.

## Create Refusal

Agents never create this type with `sase bead create` or `/sase_new_task` where it is
not agent-creatable. Do not refile the idea under another type: record it as a
`PROPOSED FOLLOW-UP:` note on the bead you are working, or raise it with the project
owner.

## Fields

**Field `proposal`**

- Name: `proposal`
- Label: Proposal
- Type: `string`
- Required: yes
- Roles: `template`
- Help: What should exist that is outside the current work
- Validators: (none)

**Field `why_out_of_scope`**

- Name: `why_out_of_scope`
- Label: Why out of scope
- Type: `string`
- Required: yes
- Roles: `template`
- Help: Why this does not belong on the current task or epic
- Validators: (none)

## Body Template

```markdown
## Feature proposal

{{ proposal }}

{{ why_out_of_scope }}
```

## Triage

- min_plus_ones: `0`

## Provenance

- Provenance label: `builtin:sase`
- Source: `builtin`
- Package: `sase`
