---
name: sase_memory_read
description:
  Guide audited SASE long-term memory reads through `sase memory read`. Use when instructions require reading long-term
  memory context or mention the long-memory read procedure.
---

Use this skill when project instructions or a prompt require reading SASE long-term memory.

## Rules

- Read canonical long-term memory only through `sase memory read`; it checks project memory first and then home memory.
- Pass the long-memory path relative to `memory/`, such as `generated_skills.md`.
- Include a specific, non-empty reason with `--reason` or `-r`.
- Do not read canonical long-term memory files directly with shell commands or file-reading tools.
- When the note has nested long-term child notes, `sase memory read` appends a `## Children` section listing them.

## Command

```bash
sase memory read <memory-note-path> --reason "<why this context is needed>"
```

Examples:

```bash
sase memory read generated_skills.md --reason "Need generated skill workflow before editing bundled skill sources"
sase memory read tui_perf.md -r "Need TUI performance gotchas before changing TUI navigation"
```
