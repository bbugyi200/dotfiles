---
name: sase_chats
description:
  Inspect prior sase agent chat transcripts. Use when the user asks about previous chats, chat transcripts, prior agent
  conversations, "what did agent X say?", "summarize the previous agent", or any question about an earlier sase agent's
  prompt or response.
---

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

This follows the same fallback as `#resume`: completed agent's `done.json["response_path"]` first, then
`agent_meta.json["chat_path"]`. If the agent isn't found, the command exits non-zero — report that plainly instead of
guessing.

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
- If a named-agent lookup fails (artifact removed, never saved a transcript), say so plainly instead of falling back to
  an unrelated transcript.

## Not for continuing a conversation

This skill is read-only. To continue a prior conversation in a new agent, use `#resume:<name>` or
`#resume_by_chat:<basename>` xprompts — they remain the right tool for that.
