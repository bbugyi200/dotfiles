---
name: sase_questions
description: Ask the user questions. Use instead of AskUserQuestion (which is disabled).
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_questions --reason "<one-line reason for using this skill>"
```

Use this skill when you need user input. This replaces Claude's native AskUserQuestion.

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

## Handoff And Continuation

On success, `sase questions` writes a durable handoff marker and sends `SIGTERM` to the
current agent runner process group. The runner recognizes the marker as an intentional
question handoff and creates a **question gate shell** — a named, non-LLM member of your
agent family that publishes the questions, outlives you, and hands the answer to the
next family member. Your turn ends as `DONE`; there is nothing after this for you to do.
The family's status shows `QUESTION` until it is answered, then `ANSWERED`. Answering it
launches a follow-up agent whose prompt carries the merged Q&A across every round asked
so far, continuously numbered — the same `## Your next action` shape a gate shell always
composes. Do not create a question gate shell yourself with `/sase_gate`;
`sase questions` already does this for you.

Do not poll question request or response files. ACE, mobile, and Telegram submit the
complete validated form through the same write-once gate command, and the gate shell's
settlement observes the terminal response mechanically.
