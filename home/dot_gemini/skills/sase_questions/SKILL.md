---
name: sase_questions
description: Ask the user questions. Use instead of ask_user (which is disabled).
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skills log sase_questions --reason "<one-line reason for using this skill>"
```

Use this skill when you need user input. This replaces Gemini's native ask_user tool.

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
