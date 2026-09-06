---
keyword: Flaky test
summary: A test that fails and then passes on an unchanged tree.
metadata:
  generated_by: sase.task_types.generated-strand.v1
  task_type: flake
---

## Identity

- Task type: `flake`
- Label: Flaky test
- Glyph: ≈
- Accent color: `#00D7D7`
- Agent creatable: yes
- Show schema version: `1`
- Digest: `b5b410e11c62c945193bbc0594705ce9979b1627d3416b53c230f8311fa54cd1`

## Summary

A test that fails and then passes on an unchanged tree.

## When To Use

File one when a test or lint failed, a rerun on the same tree passed, and you did not
cause the failure. Record the fail rate and whether it reproduces serially. Use ci
instead when the failure is confirmed and reproducible.

## Related Task Types

- [[task_types/ci]]

## Fields

**Field `node_id`**

- Name: `node_id`
- Label: Test node ID
- Type: `string`
- Required: yes
- Roles: `data`, `template`
- Help: The pytest node ID, e.g. tests/foo.py::test_bar
- Validator `pattern`: `\S+::\S+`

**Field `repro_cmd`**

- Name: `repro_cmd`
- Label: Repro command
- Type: `string`
- Required: no
- Roles: `data`, `template`
- Help: Command that reproduced the intermittent failure
- Validators: (none)

**Field `evidence`**

- Name: `evidence`
- Label: Evidence
- Type: `string`
- Required: yes
- Roles: `template`
- Help: Fail/pass observations, fail rate, and serial vs parallel
- Validators: (none)

## Body Template

```markdown
## Flake report

- **Test:** `{{ node_id }}`
- **Repro:** `{{ repro_cmd }}`

{{ evidence }}
```

## Triage

- min_plus_ones: `3`

## Provenance

- Provenance label: `builtin:sase`
- Source: `builtin`
- Package: `sase`
