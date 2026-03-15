---
name: sase_questions
description: Ask the user questions. Use instead of AskUserQuestion (which is disabled). Only available inside sase.
---

# /sase_questions - Ask the User Questions

Use this skill when you need user input. This replaces Claude's native AskUserQuestion.

**IMPORTANT**: Only available when running inside sase (via `sase ace` TUI or `sase run`).

## How It Works

When you use this skill, the current claude instance will be **terminated**. The questions
are presented to the user in the sase TUI. After answering, a NEW agent is spawned with the
original prompt plus a "Questions and Answers" section appended.

## Usage

```bash
.venv/bin/sase questions '<json>'
```

## JSON Schema

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

## Examples

Single question with options:

```bash
.venv/bin/sase questions '[{"question": "Which database should we use?", "options": [{"label": "PostgreSQL", "description": "Relational, mature"}, {"label": "SQLite", "description": "Embedded, simple"}]}]'
```

Multiple questions:

```bash
.venv/bin/sase questions '[{"question": "Approach?", "header": "Approach", "options": [{"label": "A"}, {"label": "B"}]}, {"question": "Include tests?", "options": [{"label": "Yes"}, {"label": "No"}]}]'
```

## Notes

- Users can always provide a custom "Other..." response
- Users can add a global note across all questions
- Always use `.venv/bin/sase questions`, never bare `sase questions`
- JSON must be a single shell argument (wrap in single quotes)
