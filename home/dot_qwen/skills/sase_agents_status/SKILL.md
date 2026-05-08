---
name: sase_agents_status
description:
  Report on currently-running sase agents. Use when the user asks "what's running?", "agent status", "status report", or
  any question about live/background agents.
---

Quick reference for answering "what's running?" questions about sase agents.

## Primary command

```bash
sase agents status -j
```

This prints a stable-shape JSON array to stdout. Each row has: `name`, `project`, `pid`, `model`, `provider`,
`workspace_num`, `status`, `duration_seconds`, `started_at`, `approve`, `prompt_snippet`, `artifacts_dir`.

## How to summarize

- Group rows by `project` and render a compact table with `name`, `duration_seconds`, `provider`, and a short
  `prompt_snippet`.
- If more than 10 agents are running, show the 10 most recent (they come first — the list is already sorted by start
  time, newest first) and say "N more".
- If the list is empty, report "no agents are running" plainly — do not fabricate rows.

## Other useful forms

- `sase agents status` — pretty rich table (for direct terminal use, not machine consumption).
- `sase agents status -a` — include recently-completed DONE/FAILED agents.
- `sase agents status -p <project>` — filter by project name.
- `sase agents show -n <name>` — full detail panel (prompt, pid, artifacts dir, live-tail hint).
- `sase agents kill -n <name>` — SIGTERM an agent by name. No confirmation prompt; use with care.

## Implementation notes

The JSON shape is stable — do not reorder keys or rename fields when summarizing. `started_at` is ISO 8601 with
timezone. `duration_seconds` is an integer. `workspace_num` is null for home-project agents.
