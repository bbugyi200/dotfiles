# SASE Memory

The `memory/` directory holds agent-facing project context. Use `sase memory list` to inspect what a launch would load
or reference, and `sase memory init` to create or refresh generated memory files.

- Non-README Markdown files live directly under `memory/` and use YAML frontmatter for `type` and `parent`.
- `type: short` notes are always-loaded context, inlined directly into `AGENTS.md` (and each provider instruction file)
  by `sase memory init`.
- `type: long` notes are detailed reference material. They require a `description` and are read with `sase memory read`.
- Long notes can set `parent: memory/<note>.md` to appear in that parent note's `## Children` section.
