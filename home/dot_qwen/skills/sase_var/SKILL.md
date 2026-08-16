---
name: sase_var
description: Attach named JSON-shaped output variables to the current SASE agent run.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_var --reason "<one-line reason for using this skill>"
```

Use this skill to publish a small JSON-shaped value for a later SASE agent, inspect a
snapshot or selector, or discover historical keys. A value may be a string, number,
boolean, null, list, or map, nested within the reliability limits below.

## get

Show the current snapshot, show a quoted `<agent_name>` snapshot, or retrieve selectors.

```bash
sase var get
sase var get --format json
sase var get '<build>' --format json
sase var get status
sase var get build.status --format raw
sase var get '*.status' --format json
sase var get 'research.*.report["summary"]'
```

- No target: current agent's snapshot from `SASE_ARTIFACTS_DIR` (`pretty` or `json`).
- `'<agent_name>'`: newest exact-name historical snapshot. Quote the wrappers. Distinct
  from selector `build.*`.
- Ordinary targets: selector grammar `[SCOPE.]KEY[PATH ...]`.
- Formats: snapshots use `pretty` or `json`. Selector mode also accepts `raw` (exactly
  one value) and `jsonl`.

## list

Discover historical keys and typed values.

```bash
sase var list
sase var list --key 'status*' --agent 'build.*'
sase var list --project sase --hidden --limit 20:5
sase var list --since 1w --format json
sase var list --value-json '"ok"' --limit 0
```

Useful filters: `--agent`, `--key`, `--project` (repeatable), `--since` / `--until`,
`--value` or `--value-json`, `--hidden`, `--reverse`, and `--limit KEYS[:VALUES]`.

## set

```bash
sase var set KEY=VALUE [KEY=VALUE ...]
sase var set summary --value "tests passed"
sase var set details --value-file - <<'EOF'
Tests passed.
The release artifact is ready.
EOF
sase var set 'suites=["unit","integration"]' --json
sase var set cfg --json --value '{"retries":3,"enabled":true}'
sase var set report --json --value-file report.json
sase var set findings --json --value-file - <<'JSON'
[{"file":"src/a.py","severity":"high"},{"file":"src/b.py","severity":"low"}]
JSON
```

Writes merge into the current agent's map; later values replace earlier ones. Without
`--json`, values are strings and split on the first `=`, so `sase var set token=a=b=c`
stores `a=b=c`. `--json` composes with assignment, `--value`, and `--value-file`.

## Cross-agent facts

- Give the producer a stable name (`%id:<producer>` or `%id:build-@`). Wait with
  `%wait:<producer>` before reading its variables.
- Every producer's variables live under `agents` keyed by agent name. `%id:build-@` is
  `{{ agents["build"].result_path }}`, not `build-0`. Dotted, hyphenated, and
  digit-leading names use bracket access: `{{ agents["research.final"].report_path }}`,
  `{{ agents["0n.cld"].report_path }}`. Identifier-safe keys also support
  `{{ agents.build.result_path }}`.
- Structured values reach Jinja as real containers. Implicitly rendering a whole
  container produces compact JSON. Map keys are stored and displayed in sorted order;
  list order is preserved.
- Run this only inside a SASE agent (`SASE_AGENT=1` and `SASE_ARTIFACTS_DIR`). Keys must
  be `[A-Za-z_][A-Za-z0-9_]*`. At most 256 variables. Each string leaf and nested map
  key is limited to 8 KiB of UTF-8 text; each variable is limited to depth 8, 1,024
  total nodes, and 65,536 encoded JSON bytes. Numbers must be finite and integers must
  fit the signed 64-bit range.
- Output variables are for small handoff values, not report bodies; store a report as an
  artifact file and publish its path instead.
- Do not store secrets. Output variables are persisted in `agent_meta.json` and shown in
  ACE and the Telegram completion message.

## Stopping a `%repeat` / `%r` chain with `STOP`

`STOP` is a reserved output variable that only affects later `%repeat` / `%r` slots.
Inside a repeat iteration, run:

```bash
sase var set STOP=1
```

before the iteration completes to skip every remaining repeat slot. Each later slot
wakes, sees its repeat predecessor's `STOP`, finalizes as a successful completed
(skipped) slot, and exits without running its prompt. Set `STOP` when the current
iteration determines no further repeat work is needed.

`STOP` follows structured truthiness. `null`, `false`, numeric zero, empty strings,
empty lists, and empty maps are not-stop; strings `0`, `false`, `no`, and `off` are also
not-stop case-insensitively after trimming. Any other value stops the chain. It is
otherwise an ordinary output variable: agents that simply `%wait` on this producer
(outside a repeat chain) are not affected and can still read
`{{ agents["name"].STOP }}`.
