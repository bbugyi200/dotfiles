# chezmoi - Agent Instructions

## 1. Core Memory

The following memories contain core (always loaded) context:

### 1.1 SASE = Structured Agentic Software Engineering (sase)

#### 1.1.1 SASE Memory

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

#### 1.1.2 Ephemeral `dotfiles_<N>` Workspace Directories

SASE runs agents (like you) from ephemeral workspace directories, which are full clones
of the dotfiles repo. These directories are named `dotfiles_<N>` where `<N>` is some
integer. You need to be mindful not to run commands outside of these workspace
directories.

IMPORTANT: Do NOT mention your workspace directory (or any sibling workspace directory)
in any plan files that you generate using your `/sase_plan` skill. The agent(s) that
implement the plan might not run in the same workspace directory as you!

#### 1.1.3 Repositories

No linked repositories are associated with this project.

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

#### 1.1.4 SASE Final Declaration

Before any normal response that ends this SASE provider turn, use your `/sase_final`
skill as the last action. This includes a final answer, an incomplete-status response,
an "I will wait" response, or any reply that intends to resume in a later turn. Only a
successfully executed plan, monitor, pipe, or questions handoff is exempt, because those
commands terminate the runner mechanically. Intending to resume later is not an
exemption.

### 1.2 Chezmoi Apply After Commit (gotchas)

After making any commits to this repository (including after a SASE finalizer lands a
commit) you MUST run `chezmoi update -a --force` to apply the source tree to the home
directory.

See https://github.com/twpayne/chezmoi and https://www.chezmoi.io/ for chezmoi
documentation.

## 2. Reference Memory

The below files contain detailed reference material. When working in their domain, you
MUST use your `/sase_memory_read` skill to review their contents. Do not read canonical
memory files directly.

1. **`sase/memory/sase_artifacts.md`** - Read before creating, consuming, resolving,
   linking, or managing retention for SASE artifact references and indexed files.
2. **`sase/memory/sase_beads.md`** - Read before creating, updating, closing, or
   querying sase beads — bead types and tiers, the status lifecycle agents must never
   hand-edit, task-bead triage, phase-bead description prefixes, and non-cascading
   close, resolution, and note semantics.

## 3. Memory Webs

Each memory web below is a keyed collection. Its descriptor is always loaded, but a
strand's body is not: read strands on demand with your `/sase_memory_read` skill, for
example `sase memory read glossary:stitch -r "<why>"`.

### 3.1 Task Bead Types (task_types)

Every task bead can carry a `task_type` drawn from this project's catalog.
`sase bead task-type list` always shows the live catalog; read
`sase memory read task_types:<slug> -r "<why>"` for one generated type in full. This
note is the generated, always-current snapshot of the agent-creatable types below.

1. **Bug** (`bug`) - A defect an agent found while doing unrelated work, not an external
   tracker bug.
2. **CI failure** (`ci`) - A confirmed true test or lint failure you did not cause, not
   a flake.
3. **Feature** (`feature`) - An out-of-scope product or tooling idea that should not
   become a wish list.
4. **Flaky test** (`flake`) - A test that fails and then passes on an unchanged tree.
5. **Memory** (`memory`) - A sase memory note or skill that is out of date.

#### 3.1.1 File Discovered Work As Task Beads

Unless your prompt explicitly forbids creating beads (epic phase workers, for example,
must record `PROPOSED FOLLOW-UP:` notes on their own bead instead), you can and SHOULD
capture discovered follow-up work as sase task beads. Before creating any task bead, you
MUST use `/sase_new_task`.
