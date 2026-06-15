---
name: sase_chats
description:
  Inspect prior sase agent chat transcripts. Use when the user asks about previous chats, chat transcripts, prior agent
  conversations, "what did agent X say?", "summarize the previous agent", or any question about an earlier sase agent's
  prompt or response.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skills use sase_chats --reason "<one-line reason for using this skill>"
```

Quick reference for answering "what did the previous agent say?" questions about sase chat transcripts.

## Primary command

```bash
sase chats list -j
```

Prints a stable-shape JSON array of recent transcripts, newest first. Each row has: `path`, `basename`, `mtime`,
`size_bytes`, `workflow`, `agent`, `timestamp`, `prompt_snippet`, `response_snippet`. Prefer JSON over the pretty table
when summarizing.

Useful list options:

- `sase chats list -j -l 20` — cap how many rows are returned (default is conservative).
- `sase chats list -j -q '<text>'` — case-insensitive content/path/basename filter.

## Looking up a specific transcript

When the user names an agent, resolve by name first:

```bash
sase chats show --agent <name>
```

This follows the same fallback as `#fork`: completed agent's `done.json["response_path"]` first, then
`agent_meta.json["chat_path"]`.

Step-suffixed child workflows (e.g. `<name>.plan`, `<name>.commit`) are recorded as separate transcript entries —
`--agent <name>` does NOT include them. A submitted plan in particular appears as a `<name>.plan` chat whose
`response_snippet` begins with `Plan submitted for review.` and names the `~/.sase/plans/<YYMM>/<file>.md` path.

If `--agent <name>` exits non-zero, walk this fallback chain before giving up:

1. `sase chats list -j -q '<name>'` — catches step-suffixed siblings (`<name>.plan`, `<name>.commit`, ...) that the
   named lookup missed.
2. `sase agents status -a -j` filtered to `<name>` — includes recently DONE/FAILED agents, not just RUNNING.
3. If the agent is still RUNNING, hand off to the `/sase_agents_status` skill for the artifacts-dir workflow (live
   reply, workflow checkpoints, mid-run plan drafts).

Only after that chain is exhausted should you tell the user the agent has no recoverable transcript or artifact. When
that chain reaches live artifacts, name the artifact paths you read and label the evidence source as draft/live
(`live_reply.md` from a running agent) or stable/completed (checkpoints, submitted plans, `done.json`, or saved
transcripts).

When the user gives a path or basename:

```bash
sase chats show --path <path>
sase chats show --basename <basename>
```

Exactly one selector (`--agent`, `--path`, or `--basename`) is required.

## Picking the right `--format`

`sase chats show` defaults to `-f raw` (full transcript markdown). Switch when the question is narrower:

- `-f response` — just the agent's latest response. Use this for "what did agent X conclude?" or "what was the
  recommendation?". Exits non-zero if no response heading can be parsed; fall back to `-f raw` and say so rather than
  guessing.
- `-f resume` — flattened User/Assistant turns with nested resume references expanded. Use this when the user wants the
  full chronological context (e.g. "summarize the back-and-forth").

## How to summarize

- Always cite the agent name and `path`/`basename` you read so the user can open the source.
- Distinguish prompt content from response content — they live under separate headings in the transcript.
- Prefer short excerpts over long quotes; only include a longer quote when the exact wording matters.
- If `sase chats list -j` returns an empty array, say "no transcripts found" plainly — do not fabricate rows.
- If a named-agent lookup fails AND the fallback chain above (content-filtered list, `-a` status, `/sase_agents_status`
  artifacts) turns up nothing, say so plainly instead of falling back to an unrelated transcript.

## Not for continuing a conversation

This skill is read-only. To continue a prior conversation in a new agent, use `#fork:<name>` or
`#fork_by_chat:<basename>` xprompts — they remain the right tool for that.
