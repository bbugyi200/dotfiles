# SASE Memory

The `sase/memory/` directory holds agent-facing project context. It separates compact, always-loaded notes from detailed
reference notes that agents read only when relevant.

![How SASE memory files are used](assets/memory-directory-map.png)

## How Memory Files Are Used

- Non-README Markdown files live directly under `sase/memory/` and use YAML frontmatter for `type`, `parent`, and
  `description`.
- `type: short` notes are Tier 1 context. `sase memory init` inlines them into `AGENTS.md`, then copies that exact
  content to each provider instruction shim.
- `type: long` notes are detailed reference material for Tier 2. They require a `description` and are fetched explicitly
  with audited `sase memory read` calls.
- `sase/memory/sase.md` is generated from SASE configuration and captures linked repositories plus workspace rules.
- `sase/memory/README.md` is generated from the notes themselves, including the statistics below.

### Frontmatter Schema

- `type`: `short` for always-loaded notes or `long` for read-on-demand reference notes.
- `parent`: `AGENTS.md` for top-level notes, or `sase/memory/<note>.md` when a long note belongs under another long
  note.
- `description`: required for long notes and used in generated agent instructions and this README.

### Linking

- `@sase/memory/<note>.md` loads a note into agent context when the root instruction file is read.
- Plain `sase/memory/<note>.md` mentions keep a note discoverable without loading it automatically.
- Long notes parented under another long note are reachable through that parent for validation.

## Memory Notes

### `sase/memory/sase.md`

- Type: `short`
- Description: No description set.
- Parent: `AGENTS.md`
- Lines: 33
- Approx. tokens: 463

## Statistics

- Total notes: 1
- Short notes: 1
- Long notes: 0
- Total lines: 33
- Total approx. tokens: 463

## Commands

- `sase memory list` shows loaded, referenced, available, and missing memory files.
- `sase memory init` creates or refreshes generated memory files, renders `AGENTS.md` and provider shims from
  `AGENTS.template.md`, and refreshes this asset-backed README.
- Set `amd_agents_template` (or `amd_agents_minimal_template`) to a root-relative project template in `sase.yml`; home
  roots can instead use `AGENTS.template.md` (or `AGENTS.minimal.template.md`) in the SASE user config directory.
- Set `memory_sase_template` or `memory_readme_template` to root-relative project templates in `sase.yml`; home roots
  can instead use `memory-sase.template.md` or `memory-README.template.md` in the SASE user config directory.
- `sase memory init --check` reports drift without writing files.
- `sase memory read <note>.md --reason <reason>` reads a long note and records an audited access event.
- `sase memory write` proposes a new long-term memory note for review.
- `sase memory review` reviews pending memory proposals.
- `sase memory log` summarizes audited long-memory reads.
