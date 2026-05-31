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
- Dynamic `.sase/memory/long-*.md` files already carry the corresponding long-memory content for that prompt. When one
  is listed in a dynamic memory section, use that dynamic copy as the provided context and do not separately read the
  matching canonical long-memory file unless you need a fresh audited read.

## Command

```bash
sase memory read <long-memory-path> --reason "<why this context is needed>"
```

Examples:

```bash
sase memory read long/generated_skills.md --reason "Need generated skill workflow before editing bundled skill sources"
sase memory read long/tui_jk_baseline.md -r "Need baseline latency data before changing TUI navigation"
```
