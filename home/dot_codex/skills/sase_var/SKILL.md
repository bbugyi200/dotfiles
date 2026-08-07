---
name: sase_var
description: Attach named JSON-shaped output variables to the current SASE agent run.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_var --reason "<one-line reason for using this skill>"
```

Use this skill when you need a later SASE agent to consume a small value produced by the
current agent, or when you want the value to appear in the Agents-tab metadata and
Telegram completion message for this run. A value may be any JSON shape: string, number,
boolean, null, list, or map, nested within the reliability limits below.

## Workflow

1. Make sure the producing agent has a stable name with `%id:<producer>` or an
   agent-name template such as `%id:build-@`.
2. Set one or more output variables:

   ```bash
   sase var set KEY=VALUE [KEY=VALUE ...]
   ```

   Without `--json`, values are strings. Use `--value` for text containing spaces, or a
   heredoc through `--value-file -` for a multi-line value:

   ```bash
   sase var set summary --value "tests passed"
   sase var set details --value-file - <<'EOF'
   Tests passed.
   The release artifact is ready.
   EOF
   ```

   Add `-j` / `--json` to any input form to decode a structured JSON value:

   ```bash
   sase var set 'suites=["unit","integration"]' --json
   sase var set cfg --json --value '{"retries":3,"enabled":true}'
   sase var set report --json --value-file report.json
   sase var set findings --json --value-file - <<'JSON'
   [{"file":"src/a.py","severity":"high"},{"file":"src/b.py","severity":"low"}]
   JSON
   ```

3. Inspect the current agent's stored values with `sase var list`, or use
   `sase var list --json` for compact machine-readable JSON.
4. In later prompts, wait for the producer before referencing its variables. Every
   producer's variables live under a single `agents` dictionary keyed by agent name. For
   example, `%id:build-@` can produce:

   ```bash
   sase var set result_path=dist/report.md status=ok
   ```

   A later waited agent can render `{{ agents["build"].result_path }}` after the
   producer has written the variable.

Structured values reach Jinja as real containers. Attribute/subscript access and
iteration work normally:

```jinja
Retries: {{ agents["build"].cfg.retries }}
{% for host in agents["build"].cfg.hosts %}
- {{ host }}
{% endfor %}
```

Implicitly rendering a whole container, such as `{{ agents["build"].cfg }}`, produces
compact JSON rather than a Python representation. Jinja's `| tojson` filter remains
available when explicit JSON formatting is preferred.

The key is always the agent's stable name. Agent-name templates use the template base,
so `%id:build-@` is `{{ agents["build"].result_path }}`, not `build-0`. The key is the
raw agent name with no identifier munging, so dotted, hyphenated, and digit-leading
names all work via bracket access: `%id:research.@.final` →
`{{ agents["research.final"].report_path }}`, and `%id:0n.cld` →
`{{ agents["0n.cld"].report_path }}`. Identifier-safe keys also support attribute access
such as `{{ agents.build.result_path }}`.

## Rules

- Run this only inside a SASE agent; the command requires `SASE_AGENT=1` and
  `SASE_ARTIFACTS_DIR`.
- Keys must be valid Jinja attribute identifiers: `[A-Za-z_][A-Za-z0-9_]*`.
- Without `--json`, values are strings and are split on the first `=`, so
  `sase var set token=a=b=c` stores `a=b=c`.
- With `--json`, a value may be a string, number, boolean, null, list, or map. Nested
  map keys may be any non-empty, NUL-free strings. Map keys are stored and displayed in
  sorted order; list order is preserved.
- Use `KEY=VALUE` for simple tokens, `--value` for values containing spaces, and a
  heredoc into `--value-file -` for multi-line bodies. `--json` composes with all three
  forms.
- An agent may store at most 256 variables. Each string leaf and nested map key is
  limited to 8 KiB of UTF-8 text; each variable is limited to depth 8, 1,024 total
  nodes, and 65,536 encoded JSON bytes. Numbers must be finite and integers must fit the
  signed 64-bit range.
- Output variables are for small handoff values, not report bodies; store a report as an
  artifact file and publish its path instead.
- Multiple calls merge into the same agent's variable map; later writes for the same key
  replace earlier values.
- Do not store secrets. Output variables are persisted in `agent_meta.json` and shown in
  ACE and the Telegram agent-completion message.

Use `%wait:<producer>` when a later agent needs a variable from another agent.

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
