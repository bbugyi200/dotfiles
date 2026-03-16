---
name: sase_questions
description: Ask the user questions. Use instead of ask_user (which is disabled).
---

Use this skill when you need user input. This replaces Gemini's native ask_user tool.

## Usage

```bash
.venv/bin/sase questions '<json>'
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
.venv/bin/sase questions '[{"question": "Which database should we use?", "options": [{"label": "PostgreSQL", "description": "Relational, mature"}, {"label": "SQLite", "description": "Embedded, simple"}]}]'
```

Multiple questions:

```bash
.venv/bin/sase questions '[{"question": "Approach?", "header": "Approach", "options": [{"label": "A"}, {"label": "B"}]}, {"question": "Include tests?", "options": [{"label": "Yes"}, {"label": "No"}]}]'
```
