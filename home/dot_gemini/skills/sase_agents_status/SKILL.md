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
- For completed agents' transcripts, use the `/sase_chats` skill — `sase chats show --agent <name>` resolves to the
  saved chat for any agent that has run.

## Artifacts directory

Each row's `artifacts_dir` is the on-disk state for that agent. Files you may read mid-run:

- `live_reply.md` — streaming buffer for the agent's in-flight response. Treat as draft; only quote with an
  "in-progress" caveat.
- `agent_meta.json` — static metadata, including `chat_path` (where the transcript will live once saved).
- `workflow_state.json`, `prompt_step_*.json` — per-step checkpoints, written once on each step transition. Stable to
  read while the agent is still running.
- `done.json` — only present after the agent has stopped. When present it is authoritative; it has `outcome`,
  `response_path`, and `plan_path` (if the agent submitted a plan).

`workspace_num` resolves to `<parent-of-this-repo>/sase_<N>/` — the agent's ephemeral workspace clone. Pre-submission
plan drafts live there as `<workspace>/sase_plan_*.md`; once the agent has run `sase plan`, the submitted copy is at
`~/.sase/plans/<YYMM>/<descriptive>.md` and won't be rewritten.

### Stable vs streaming

Rule of thumb: if a file is the agent's in-flight response and the agent is RUNNING, treat it as draft. If the file is a
checkpoint, submission, or per-step output, treat it as stable — safe to read and quote even while the agent runs.

When you use live state to answer, cite the artifact paths you read and label each piece of evidence as draft/live or
stable/completed. For review or comparison questions across multiple active agents, do not treat the absence of a
completed transcript as the absence of useful evidence.

## Implementation notes

The JSON shape is stable — do not reorder keys or rename fields when summarizing. `started_at` is ISO 8601 with
timezone. `duration_seconds` is an integer. `workspace_num` is null for home-project agents.
