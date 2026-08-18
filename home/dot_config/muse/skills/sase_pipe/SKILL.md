---
name: sase_pipe
description: >-
  Hand this agent's turn to a fresh successor in the same agent family: this turn ends
  and the next family member starts immediately with the prompt you write, in the same
  workspace, optionally on a different model or with a clean context window. Use ONLY
  when the user explicitly asks you to pipe or hand off work to another agent. Not for
  running or waiting on a command (`/sase_monitor`), and not for launching helper agents
  (`/sase_run`).
---

## Core Rule

Use this skill only when the user explicitly asks you to pipe or hand off work to
another agent. `sase pipe` kills the calling agent once it starts the hand-off, so this
turn will not return normally. Write everything the successor needs inside the piped
prompt itself, not in a reply you plan to send afterward — there is no afterward.

## Canonical Invocation

```bash
sase pipe 'implement the approved plan' --reason 'hand off to a coding pass' --model opus
```

## When To Pipe

- The remaining work needs a different model or effort than this turn is running.
- This context window is spent, and the rest of the work is fully self-contained in the
  prompt you write.
- The next step is a distinct role that deserves its own agent row and its own reply,
  not more of this turn.

Do not pipe for:

- A long-running or blocking command — use `/sase_monitor` instead.
- Parallel helpers or reviewers running alongside this agent — use `/sase_run` instead.
- Work this agent can simply do now.

## Options

- `-f, --fresh` — successor starts with a clean context window. Default: prefix
  `#fork:<this agent>` so the successor inherits this chat.
- `-j, --json` — print a machine-readable hand-off summary instead of the rich one.
- `-m, --model MODEL` — model or alias for the successor (`opus`, `opus@high`, `sonnet`,
  `codex/gpt-5`). Default: inherit this agent's model.
- `-n, --name TOKEN` — successor role token: `review` yields `<family>--review`.
  Default: the next free numbered family member.
- `-r, --reason TEXT` — one-line reason, recorded on the successor and shown in agent
  lists.

## Hazards

- The piped prompt is re-parsed by the successor: `%` directives and `#` references in
  it are live. Fence any literal `%` or `#` syntax you do not want expanded.
- The successor runs in the same workspace with the same uncommitted changes and the
  same Patch, so the piped prompt needs no workspace reference.
- A non-zero exit means nothing was handed off — this agent is still running and should
  continue or retry, not assume a successor exists.
- Chains are bounded by the `max_agent_pipe_chain` config field; a piped successor that
  pipes again can eventually be refused once the bound is reached.
- Do not keep working, poll, or wait after running this command.
