---
name: sase_questions
description: Ask the user questions. Use instead of ask_user (which is disabled).
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_questions --reason "<one-line reason for using this skill>"
```

Use this skill when you need user input. This replaces Codex's native ask_user tool.

## Usage

```bash
sase questions '<json>'
```

### JSON Schema

```json
[
  {
    "question": "Full question text (required)",
    "header": "Short sidebar label (optional)",
    "options": [
      { "label": "Option label (required)", "description": "Details (optional)" }
    ],
    "multiSelect": false
  }
]
```

### Examples

Single question with options:

```bash
sase questions '[{"question": "Which database should we use?", "options": [{"label": "PostgreSQL", "description": "Relational, mature"}, {"label": "SQLite", "description": "Embedded, simple"}]}]'
```

Multiple questions:

```bash
sase questions '[{"question": "Approach?", "header": "Approach", "options": [{"label": "A"}, {"label": "B"}]}, {"question": "Include tests?", "options": [{"label": "Yes"}, {"label": "No"}]}]'
```

## Questions Versus Plan Decisions

When the question shapes the plan but one complete plan can cover every answer, embed a
Plan Decision in the plan's `decisions:` frontmatter instead of asking now. Ask with
this skill only when the answer changes the tier, size, phase graph, or architecture.

## Recommended Option First

Put your recommended option first in every question's options list, then order the
remaining options by preference. Your questions, with the first option shown as the
recommendation, and their answers, with how they were answered, appear in the session's
QUESTIONS section on the Agents tab.

## Handoff And Continuation

Run `sase questions` in the foreground and wait for the process to exit on its own.
Never invoke it with a yield window, a background flag, or any early-return timeout: an
early return means you stopped watching before the CLI finished, not that the handoff
happened. Never wrap the command in `timeout`, a pipe, or a background job. If a tool
yields a live session anyway, keep polling that same session until it reports an exit
code; never end your turn while it is still running.

If the command reports **Staged**, it validated the questions and staged a question gate
for host completion. Nothing starts until your turn ends: finish through `/sase_final`,
submitting only when its context says a declaration is required. Stage before you
declare, do not mutate files after a successful declaration, and never wait for your own
staged questions. If it does not report **Staged**, the questions were not handed off —
read the output and continue or retry. **If the tool call ever returns any result at all
— output, an error, or a normal exit — and that output does not report Staged, your turn
has NOT ended.**

Your turn ends as `DONE` once the host adopts the handoff. The host then publishes a
**question gate turn** — a named, non-LLM member of your agent session that publishes
the questions, outlives you, and hands the answer to the next session member. The agent
session's status shows `QUESTION` until it is answered, then `ANSWERED`. Answering it
launches a follow-up agent whose prompt carries the merged Q&A across every round asked
so far, continuously numbered — the same `## Your next action` shape a gate turn always
composes. Do not create a question gate turn yourself with `/sase_gate`;
`sase questions` already does this for you.

Do not poll question request or response files. sase's TUI, mobile, and Telegram submit
the complete validated form through the same write-once gate command, and the gate
turn's settlement observes the terminal response mechanically.
