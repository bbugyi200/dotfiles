---
name: sase_memory_read
description:
  Guide audited SASE long-term memory reads through `sase memory read`. Use when instructions require reading
  `memory/long/...` context or mention long-term memory procedure.
---

Use this skill when project instructions or a prompt require reading SASE long-term memory.

## Rules

- Read canonical long-term memory only through `sase memory read`; it checks project `memory/long` first and then
  `~/memory/long`.
- Pass the long-memory path relative to `memory/`, such as `long/generated_skills.md`.
- Include a specific, non-empty reason with `--reason` or `-r`.
- Do not read canonical `memory/long/*.md` files directly with shell commands or file-reading tools.

## Command

```bash
sase memory read <long-memory-path> --reason "<why this context is needed>"
```

Examples:

```bash
sase memory read long/generated_skills.md --reason "Need generated skill workflow before editing bundled skill sources"
sase memory read long/tui_perf.md -r "Need TUI performance gotchas before changing TUI navigation"
```
