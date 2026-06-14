---
name: sase_var
description: Attach named output variables to the current SASE agent run.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skills log sase_var --reason "<one-line reason for using this skill>"
```

Use this skill when you need a later SASE agent to consume a small string value produced by the current agent, or when
you want the value to appear in the Agents-tab metadata for this run.

## Workflow

1. Make sure the producing agent has a stable name with `%name:<producer>` or an agent-name template such as
   `%name:build-@`.
2. Set one or more output variables:

   ```bash
   sase var set KEY=VALUE [KEY=VALUE ...]
   ```

3. In later prompts, wait for the producer before referencing its variables. Every producer's variables live under a
   single `agents` dictionary keyed by agent name. For example, `%name:build-@` can produce:

   ```bash
   sase var set result_path=dist/report.md status=ok
   ```

   A later waited agent can render `{{ agents["build"].result_path }}` after the producer has written the variable.

The key is always the agent's stable name. Agent-name templates use the template base, so `%name:build-@` is
`{{ agents["build"].result_path }}`, not `build-0`. The key is the raw agent name with no identifier munging, so dotted,
hyphenated, and digit-leading names all work via bracket access: `%name:research.@.final` →
`{{ agents["research.final"].report_path }}`, and `%name:0n.cld` → `{{ agents["0n.cld"].report_path }}`. Identifier-safe
keys also support attribute access such as `{{ agents.build.result_path }}`.

## Rules

- Run this only inside a SASE agent; the command requires `SASE_AGENT=1` and `SASE_ARTIFACTS_DIR`.
- Keys must be valid Jinja attribute identifiers: `[A-Za-z_][A-Za-z0-9_]*`.
- Values are strings and are split on the first `=`, so `sase var set token=a=b=c` stores `a=b=c`.
- Quote assignments when your shell would otherwise split or expand the value, for example
  `sase var set "summary=tests passed"`.
- Multiple calls merge into the same agent's variable map; later writes for the same key replace earlier values.
- Do not store secrets. Output variables are persisted in `agent_meta.json` and shown in ACE.

Use `%wait:<producer>` when a later agent needs a variable from another agent.

## Stopping a `%repeat` / `%r` chain with `STOP`

`STOP` is a reserved output variable that only affects later `%repeat` / `%r` slots. Inside a repeat iteration, run:

```bash
sase var set STOP=1
```

before the iteration completes to skip every remaining repeat slot. Each later slot wakes, sees its repeat predecessor's
`STOP`, finalizes as a successful completed (skipped) slot, and exits without running its prompt. Set `STOP` when the
current iteration determines no further repeat work is needed.

`STOP` is conservative about truthiness: `""`, `0`, `false`, `no`, and `off` (case-insensitive) are treated as not-stop,
so a computed `STOP=0` is a safe no-op; any other value stops the chain. It is otherwise an ordinary output variable:
agents that simply `%wait` on this producer (outside a repeat chain) are not affected and can still read
`{{ agents["name"].STOP }}`.
