---
name: sase_memory_read
description:
  Guide audited SASE reference memory reads through `sase memory read`. Use when
  instructions require reading SASE reference memory or mention the reference-memory
  read procedure.
---

Use this skill when project instructions or a prompt require reading SASE reference
memory.

A memory's **kind** — note, web, or strand — decides how it reaches an agent. A flat
note declares `type: core` (inlined into generated agent instructions, always loaded) or
`type: reference` (named with its description only, read on demand through this
command); legacy `type: short` and `type: long` still parse and mean the same two
things. A web is a keyword-addressed collection of small strand files (the bundled
`glossary` web is one): its descriptor declares no `type:` and always inlines into the
generated Memory Webs section, while a strand's body never inlines and is always read on
demand.

Core memory cannot be read with this command because it is already in context.

`sase memory read` and `sase memory show` accept three selector shapes in one variadic
batch, resolved together before anything is printed or logged:

- a flat note name, e.g. `generated_skills.md`
- a bare web name, e.g. `glossary`, which reads every strand in that web
- a `web:keyword` strand reference, e.g. `glossary:stitch`, resolved by canonical
  keyword, alias, or an unambiguous prefix

A note or strand can link other memory as `[[target]]`, listed under a numbered
`## Linked References` section, or `![[target]]`, rendered inline in the body. A web
whose descriptor sets `link_reference: implicit` (`glossary` is one) additionally treats
every strand its body mentions as such a link. `-d/--depth N` caps how far inline links
recurse (`-d 0` prints only the requested selectors and lists every link as a reference;
the default is unlimited).

## Rules

- Read canonical reference memory only through `sase memory read`; it checks project
  memory first and then home memory.
- Pass a flat note path relative to `memory/` (`generated_skills.md`), a bare web name
  (`glossary`), or a `web:keyword` strand reference (`glossary:stitch`).
- Pass every selector needed in one command: the whole batch resolves before anything
  prints, so one unknown selector fails the entire request with no partial output.
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
sase memory read <selector> [<selector> ...] --reason "<why this context is needed>"
```

Examples:

```bash
sase memory read generated_skills.md --reason "Need generated skill workflow before editing bundled skill sources"
sase memory read tui_perf.md -r "Need TUI performance gotchas before changing TUI navigation"
sase memory read glossary:stitch glossary:patch -r "Need the stitch/patch vocabulary"
sase memory read glossary -r "Need the whole glossary"
```
