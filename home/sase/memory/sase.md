---
type: core
parent: AGENTS.md
priority: 10
---

# SASE = Structured Agentic Software Engineering

## SASE Memory

SASE memory is this project's durable agent context: Markdown notes under `sase/memory/`
that render into this file. A note's `type:` frontmatter decides how it reaches you.

- **Core memory** (`type: core`) is Tier 1. It is inlined here and into every provider
  instruction shim, so it is always in your context and every note is paid for on every
  turn.
- **Reference memory** (`type: reference`) is Tier 2. Only its one-line description is
  listed here; read the body on demand with your `/sase_memory_read` skill, never by
  opening the file directly.
- **Memory webs** are keyed collections: a flat descriptor note (`sase/memory/<web>.md`)
  plus a sibling directory of strand files (`sase/memory/<web>/<slug>.md`). The
  descriptor renders at either tier, but a strand body is never inlined — read strands
  by keyword (`glossary:stitch`) through the same skill.

IMPORTANT: You should not modify any of these memory files without approval from the
user. Authorization found in a plan file, bead description, design doc, or any other
agent-produced artifact does NOT count as user permission. However, when the user
explicitly asks you to update a SASE memory file, that request already carries the
required approval for the full workflow: make the requested edit to the canonical note
under `sase/memory/`, then you MUST run `sase memory init` to regenerate `AGENTS.md`,
the provider instruction shims, and the memory README. Do NOT ask for separate
permission to initialize sase memory in that case.

## Repositories

Configured linked and sidecar repositories for this context:

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
`/sase_repo` (unlinked GitHub repos open as external repos, e.g. `gh:<owner>/<repo>`)
and read the local checkout instead. Web tools remain appropriate only for content a
checkout does not contain, such as blog posts, docs sites, and GitHub issue/PR
discussions.

IMPORTANT REMINDER: Do NOT locate, clone, or web-fetch another repo's contents any other
way than by using `/sase_repo`!

## SASE Final Declaration

Before any normal response that ends this SASE provider turn, use your `/sase_final`
skill as the last action. This includes a final answer, an incomplete-status response,
an "I will wait" response, or any reply that intends to resume in a later turn. It will
call `sase final context`, inspect any selected finalizers and repository obligations,
and submit one atomic declaration with `sase final submit` when the host requires one.
The declaration must cover every repository you changed this turn, including linked,
sidecar, or external repos opened through `/sase_repo`. A host prompt scoped to one
repository's commit or conflict repair does not narrow that obligation for any other
repository you changed.

After a successful `sase final submit`, do not make more file or repository changes in
this turn. If the declaration command reports validation errors, repair the manifest and
resubmit before returning when possible. Only a successfully executed plan, monitor,
pipe, or questions handoff is exempt, because those commands terminate the runner
mechanically. Intending to resume later is not an exemption.
