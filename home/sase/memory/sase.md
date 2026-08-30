---
type: core
parent: AGENTS.md
priority: 10
---

# SASE = Structured Agentic Software Engineering

## SASE Memory

SASE memory is this project's durable agent context: Markdown notes under `sase/memory/`
that render into this file. A note's kind — flat note or memory web — and a flat note's
`type:` frontmatter decide how it reaches you.

- **Core memory** (`type: core`) is inlined here and into every provider instruction
  shim, so it is always in your context and is paid for on every turn.
- **Reference memory** (`type: reference`) is not inlined. Only its one-line description
  is listed here; read the body on demand with your `/sase_memory_read` skill, never by
  opening the file directly.
- **Memory webs** are keyed collections: a flat descriptor note (`sase/memory/<web>.md`)
  plus a sibling directory of strand files (`sase/memory/<web>/<slug>.md`). A web's
  descriptor is always inlined here; a strand body never is — read strands on demand
  with your `/sase_memory_read` skill (`sase memory read <web>:<keyword>`, for example
  `glossary:stitch`).

Memory files are not ordinary files: before you create, edit, or delete any of them — or
propose a plan that would — use your `/sase_memory_write` skill.

## Repositories

Configured linked and sidecar repositories associated with this project:

- `chezmoi`: Chezmoi-managed dotfiles and global SASE configuration source. Use
  `sase repo open` to access a private linked workspace when running from a numbered
  host workspace.

When you need to read or modify files in any repository other than your own workspace
checkout, agents MUST use your `/sase_repo` skill first. This includes configured linked
repos and sidecars, another SASE project's repo, and any GitHub repo not linked to the
current project. Open different-project and unlinked GitHub repos as external repos
through the skill. Use the path it prints as the only path for reads and writes.

This rule applies regardless of transport. Fetching a repository's files or history over
the web — github.com file/blob/raw URLs, raw.githubusercontent.com, repo tarballs, or
GitHub-API/`gh` file-content reads — counts as reading that repo: open it with
`/sase_repo` (unlinked GitHub repos open as external repos) and read the local checkout
instead. Web tools remain appropriate only for content a checkout does not contain, such
as blog posts, docs sites, and GitHub issue/PR discussions.

**IMPORTANT**: The `sase artifact read <ref> "<reason>"` command MUST be used to read
artifacts (so the reads are audited) from sidecar repos. Do NOT read sidecar artifact
files directly or locate, clone, or web-fetch another repo's contents any other way than
by using `/sase_repo` or `sase artifact read`!

## SASE Final Declaration

Before any normal response that ends this SASE provider turn, use your `/sase_final`
skill as the last action. This includes a final answer, an incomplete-status response,
an "I will wait" response, or any reply that intends to resume in a later turn. Only a
successfully executed plan, monitor, pipe, or questions handoff is exempt, because those
commands terminate the runner mechanically. Intending to resume later is not an
exemption.
