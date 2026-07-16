---
name: sase_questions
description: Ask the user questions. Use instead of ask_user (which is disabled).
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_questions --reason "<one-line reason for using this skill>"
```

Use this skill when you need user input. This replaces Antigravity's native ask_user tool.

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
    "options": [{ "label": "Option label (required)", "description": "Details (optional)" }],
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

On success, `sase questions` writes a durable handoff marker and sends `SIGTERM` to the current agent runner process
group. The runner recognizes this as an intentional question handoff, creates a command-backed `UserQuestion` gate,
yields its runner slot while it waits, and reacquires a slot before continuing. The answer is added to the Q&A history
and reconstructed follow-up prompt; the interrupted provider turn does not return normally.

Do not poll question request or response files. ACE, mobile, and Telegram submit the complete validated form through the
same write-once gate command, and the runner observes the terminal response mechanically.
