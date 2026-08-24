---
name: sase_memory_read
description:
  Guide audited SASE reference memory reads through `sase memory read`. Use when
  instructions require reading SASE reference memory or mention the reference-memory
  read procedure.
---

Use this skill when project instructions or a prompt require reading SASE reference
memory.

What a memory **is** and how it **renders** are independent. Today every memory is a
note, and `type:` declares only whether it renders as core memory (always loaded) or
reference memory (read on demand). Legacy `type: short` and `type: long` values are
still accepted and mean core and reference respectively.

Core memory cannot be read with this command because it is already in context.

Coming soon: `sase memory read <web>:<keyword>` will read keyed memory-web collections;
that address form is not available yet.

## Rules

- Read canonical reference memory only through `sase memory read`; it checks project
  memory first and then home memory.
- Pass the reference-memory path relative to `memory/`, such as `generated_skills.md`.
- Include a specific, non-empty reason with `--reason` or `-r`.
- Do not read canonical reference memory files directly with shell commands or
  file-reading tools.
- When the note has nested reference child notes, `sase memory read` appends a
  `## Children` section listing them.
- `sase memory show` prints the same content but records no audit event, so it is for
  humans and tooling — never use it in place of `sase memory read` when consulting
  memory to do work.

## Command

```bash
sase memory read <memory-note-path> --reason "<why this context is needed>"
```

Examples:

```bash
sase memory read generated_skills.md --reason "Need generated skill workflow before editing bundled skill sources"
sase memory read tui_perf.md -r "Need TUI performance gotchas before changing TUI navigation"
```
