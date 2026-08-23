# athena - Bryan Bugyi's Home Server

IMPORTANT: You should not modify any of these memory files without approval from the
user. However, when the user explicitly asks you to update a SASE memory file, that
request already carries the required approval for the full workflow: make the requested
edit to the canonical note under `sase/memory/`, then you MUST run `sase memory init` to
regenerate `AGENTS.md`, the provider instruction shims, and the memory README. Do NOT
ask for separate permission to initialize sase memory in that case.

## 1. Tier 1 (short-term) Memory

The following memories contain core (always loaded) context:

### 1.1 SASE = Structured Agentic Software Engineering (sase)

#### 1.1.1 Repositories

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

#### 1.1.2 SASE Final Declaration

Before any normal response that ends this SASE provider turn, use your `/sase_final`
skill as the last action. This includes a final answer, an incomplete-status response,
an "I will wait" response, or any reply that intends to resume in a later turn. It will
call `sase final context`, inspect any selected finalizers and repository obligations,
and submit one atomic declaration with `sase final submit` when the host requires one.

After a successful `sase final submit`, do not make more file or repository changes in
this turn. If the declaration command reports validation errors, repair the manifest and
resubmit before returning when possible. Only a successfully executed plan, monitor,
pipe, or questions handoff is exempt, because those commands terminate the runner
mechanically. Intending to resume later is not an exemption.

### 1.2 Task Bead Types (task_types)

Every task bead can carry a `task_type` drawn from this project's catalog.
`sase bead task-type list` always shows the live catalog and
`sase bead task-type show <slug>` shows one type in full; this note is the generated,
always-current snapshot of the agent-creatable types below.

#### 1.2.1 Types

##### 1.2.1.1 `bug` — Bug

File one when you found a defect while doing unrelated work and it is not an external
tracker issue. Record where it lives, how to reproduce it, and who it hurts. Do not use
this for a flake, a confirmed CI failure, or a GitHub-mirrored bug.

- Required fields: `location`, `repro`
- Optional fields: `impact`

Run `sase bead task-type show bug` for the full field list, validators, and body
template.

##### 1.2.1.2 `ci` — CI failure

File one when a test or lint failed and you confirmed it is a true failure, not a flake.
Record the pytest node ID, the failing SHA if known, and why this is not intermittent.
Use flake instead when a rerun on the same tree passed.

- Required fields: `node_id`, `why_not_flake`
- Optional fields: `sha`

Run `sase bead task-type show ci` for the full field list, validators, and body
template.

##### 1.2.1.3 `flake` — Flaky test

File one when a test or lint failed, a rerun on the same tree passed, and you did not
cause the failure. Record the fail rate and whether it reproduces serially. Use ci
instead when the failure is confirmed and reproducible.

- Required fields: `node_id`, `evidence`
- Optional fields: `repro_cmd`

Run `sase bead task-type show flake` for the full field list, validators, and body
template.

##### 1.2.1.4 `memory` — Memory

File one when a sase memory file or skill contains out-of-date information that should
be updated. Closing still requires explicit user permission plus `sase memory init`.
Record the memory path and the proposed change.

- Required fields: `path`, `proposed_change`

Run `sase bead task-type show memory` for the full field list, validators, and body
template.

#### 1.2.2 File Discovered Work As Task Beads

Unless your prompt explicitly forbids creating beads (epic phase workers, for example,
must record `PROPOSED FOLLOW-UP:` notes on their own bead instead), you can and SHOULD
capture discovered follow-up work as sase task beads. Pick the type above whose
`when_to_use` matches what you found:

- A linter or test is flaky or failing and you did not cause it: file a task bead
  instead of ignoring the failure.
- A sase memory file or skill contains out-of-date information that should be updated:
  file a task bead proposing the update.
- A tool, command, or script this project is responsible for has a bug or a clear,
  objective improvement that would help future agents: file a task bead to fix or
  improve it.

Before creating any task bead, you MUST use `/sase_new_task`. That skill checks every
task status for semantic duplicates, checks in-progress epics for a credible causal
link, and records the issue in the right place. Only a genuinely new task becomes an
`open` draft, and every new task requires an intentional `--size` plus
`-T "task(<slug>)"` and `-f/--field` values for that type's required fields. Ready task
beads are proposed to the project owner, who either launches an agent to work them or
closes them with a reason.

## 2. Tier 2 (long-term) Memory

The below files contain detailed reference material. When working in their domain, you
MUST use your `/sase_memory_read` skill to review their contents. Do not read canonical
memory files directly.

### 2.1 `sase/memory/obsidian.md`

Obsidian vault, notes workflow, and obsidian-headless/ob usage.
