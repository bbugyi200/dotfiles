---
name: sase_beads
description:
  Reference for sase bead commands (create, update, close, list, search, ready, show, dep, ref). Use when working with
  beads.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_beads --reason "<one-line reason for using this skill>"
```

Quick reference for the `sase bead` CLI. Use `sase bead` (not `.venv/bin/sase bead`) for all bead commands.

## SDD Path Convention

Do not assume `sdd/...` is relative to the current checkout. In launched agents, use `SASE_SDD_PLANS_DIR` for plan paths
and `SASE_SDD_BEADS_DIR` for the bead store. Outside a launched agent, resolve them with
`SASE_SDD_PLANS_DIR=$(sase repo path plans)` and `SASE_SDD_BEADS_DIR=$(sase repo path plans)/beads`.

The examples below use `${SASE_SDD_PLANS_DIR}/...` plan paths. Quote `--type` values so shell expansion works reliably.

`sase bead` reads and writes the current effective SDD bead store. In migrated projects this is `beads/` in the plans
sidecar; legacy in-tree projects use `sdd/beads/`, and legacy local/separate-repo stores use `.sase/sdd/beads/`.
Canonical state lives in `beads/events/**` when present; `issues.jsonl` is a generated compatibility projection. It does
not merge bead records from numbered sibling workspaces or legacy bead stores.

## Statuses

- `open` — not started (default)
- `claimed` — reserved by a live agent that has not started working yet (runtime-managed)
- `ready` — a drafted task bead awaiting human triage (task beads only)
- `in_progress` — actively being worked
- `closed` — complete, canceled, or superseded

Do NOT set `claimed` by hand. For an ad-hoc bead-carrying launch, the agent runner owns this transition: it claims the
bead when the agent starts waiting, promotes the claim to `in_progress` right before work begins, and releases it back
to `open` if the agent dies before it ever started.

`sase bead work` uses a stronger epic-launch path. Before any runner spawns, it assigns every rendered phase bead and
the epic land bead directly to `in_progress` under their exact agent names, then commits and publishes that complete
launch state. The runner's later wait claim, launch promotion, and waiting-claim release therefore become quiet no-ops.
If an epic-launched runner dies while waiting, its bead stays `in_progress`; rerun `sase bead work <epic-id|plan.md>` to
recover and reassign every remaining non-closed bead. Closed phases are never reassigned.

The ad-hoc wait-time claim remains best-effort, and the `bead_claim_checks` chop reconciles whatever it misses, so a
waiting ad-hoc agent's bead can turn `claimed` a few seconds after that agent starts waiting rather than instantly. A
bead you were told to work on is already `in_progress` by the time you read your prompt.

## Types

- `plan` — plan-like work item (created with `--type "plan(...)"`)
- `phase` — child of a plan (created with `--type "phase(...)"`)
- `task` — standalone discovered follow-up (created with `--type task`)

Plan beads can carry bead tier `--tier plan` or `--tier epic`. Plan files live under `${SASE_SDD_PLANS_DIR}/{YYYYMM}/`
in migrated projects; `sase repo path plans` preserves the legacy layout for older stores. Plan files independently
carry `tier: tale` or `tier: epic` in frontmatter. `sase bead work` runs `epic`-tier plan beads by launching phase +
land agents. Task beads are top-level, have no tier, and may carry a size for launch-model routing.

## Task Bead Workflow

Task beads capture discovered work that is useful but outside the current task. Unless a prompt forbids bead creation,
create one as an `open` draft, refine its description and dependencies, then mark it `ready` for the project owner:

```bash
sase bead create --type task --title "Fix flaky integration test" \
  --description "The retry test flakes under parallel pytest; discovered while landing sase-xy."
sase bead update <task-id> --status ready
```

The `bead_task_triage` chop raises one human-only `TaskTriage` gate for each ready task bead. Its default **Launch**
branch runs `sase bead work <task-id>` in a detached background task; optional launch feedback is appended to the worker
prompt. Its **Close** branch requires a reason and closes the bead with `resolution=canceled`. A pending gate is
canceled if the bead leaves `ready`, and the chop does not raise duplicate gates while one remains pending.

Epic phase workers are the exception: they must not create beads themselves. They append a
`PROPOSED FOLLOW-UP: <summary — detail>` note to their own phase bead, and the epic land agent decides which proposals
become ready task beads.

## Phase Bead Descriptions

An epic phase bead's description comes from the matching `phases:` entry in the epic plan file's frontmatter. By
convention, the description starts with that phase's slug ID followed by `: `, then a short summary. For example:
`serialize: put the bead-store worktree materialization inside the store-write-lock critical section.`

The prefix identifies the phase without repeating its `title`, which already names the phase's section in the plan body.
Resolve a slug to its section by looking up the ID in the plan frontmatter that `sase bead show` displays.

Use this prefix when authoring a phase bead description by hand:

```bash
sase bead create --title "Implement login endpoint" --type "phase(<plan-bead-id>)" \
  --description "login: add the endpoint and its auth checks."
```

The same prefix applies when editing the description by hand. This prefix applies only to phase beads. Plan/epic bead
descriptions carry the plan's goal and do not take it.

## Commands

### create

```bash
# Create a plan bead (top-level, linked to a plan file)
sase bead create --title "Add auth system" --type "plan(${SASE_SDD_PLANS_DIR}/202605/auth.md)" --tier plan

# Create an executable epic bead
sase bead create --title "Auth epic" --type "plan(${SASE_SDD_PLANS_DIR}/202605/auth.md)" --tier epic

# Set the launch model (epic plan bead → land-agent model; phase bead → per-phase work model)
sase bead create --title "Auth epic" --type "plan(${SASE_SDD_PLANS_DIR}/202605/auth.md)" --tier epic --model claude/opus

# Create a phase bead (child of a plan)
sase bead create --title "Implement login endpoint" --type "phase(<plan-bead-id>)"

# Create a standalone task bead (open draft)
sase bead create --title "Fix flaky login test" --type task --description "Failure details and provenance"

# Create a nested plan (plan with parent)
sase bead create --title "Sub-plan" --type "plan(${SASE_SDD_PLANS_DIR}/202605/sub.md,<parent-bead-id>)"

# With optional fields
sase bead create --title "..." --type "phase(<id>)" --description "Details here" --assignee alice --size medium
sase bead create --title "..." --type "phase(<id>)" --ref research:202607/report.md
```

`--type` / `-T` is required. Syntax: `task`, `plan(<plan_file>)`, `plan(<plan_file>,<parent_id>)`, or
`phase(<parent_id>)`. `--size` / `-z` accepts `xsmall|small|medium|large|xlarge` on phase and task beads and controls
plan-first prompting and default model routing. `--ref` / `-R` attaches a durable artifact reference to the bead and can
be repeated.

### update

```bash
# Start work by hand (task beads normally use `sase bead work <task-id>`)
sase bead update <id> --status in_progress

# Propose a drafted task bead for triage
sase bead update <task-id> --status ready

# Update other fields
sase bead update <id> --title "New title"
sase bead update <id> --description "Updated description"
sase bead update <id> --notes "Implementation notes"
sase bead update <id> --assignee bob
sase bead update <id> --design "${SASE_SDD_PLANS_DIR}/202605/revised.md"
sase bead update <id> --model codex/gpt-5.6-sol
sase bead update <id> --model ""  # clear the stored model
sase bead update <id> --size medium
# Combine multiple updates
sase bead update <id> --status in_progress --assignee alice
```

Use `close` for completion and `open` for reopening. `--notes` **replaces** the whole field; use `sase bead note` when
you are recording progress that should accumulate. Moving a bead to `closed` through `update` obeys the same descendant
guard `close` does.

### close / open

```bash
# Close finished work (the standard completion path; used by runtime prompts)
sase bead close <id> --note "<what you verified>"
sase bead close <id1> <id2> --reason "why"

# Close selected phase beads by their numeric suffix without closing the epic
sase bead close <epic-id> -p 1-3

# Cancel or supersede an unfinished tree (explicit, never the normal path)
sase bead close <id> --force --resolution canceled --reason "why this tree stops here"

# Reopen a closed bead (and every closed ancestor above it)
sase bead open <id>
```

`close` accepts multiple IDs and an optional `-r`/`--reason`; prefer it over `update --status closed`.

For an epic plan bead, `-p`/`--phases` accepts comma-separated phase numbers and inclusive ranges. It requires exactly
one epic ID, treats each number as the phase bead's ID suffix, and closes only those phases—not the epic itself.

Every real close records a typed resolution with `-R`/`--resolution`: `done`, `canceled`, or `superseded`. A real close
defaults to `done` when no resolution is supplied; an already-closed bead is not compared unless `--resolution` is
explicitly supplied. `--reason` stays free text for the human explanation. Historical closures made before resolutions
existed are not backfilled and render as `(unrecorded)`.

Closing an already-closed bead is safe and free: it exits 0, reports `Already closed`, writes no close event, and
creates no commit. If the request supplies a conflicting `--resolution` or `--reason`, the command is refused before
writing rather than applying the new value. To add completion evidence after closure, use `sase bead note <id> "..."` or
`sase bead close <id> --note "..."`; that records a note-only mutation instead of another close.

`-n`/`--note` appends the same attributed entry to every explicitly listed bead before closing them. The note and close
events are written in one mutation, one commit, and one push when a real close happens; on an already-closed bead it is
a note-only mutation. Use it for completion evidence; keep `sase bead note` for mid-work progress, handoff notes, and
evidence on already-closed beads.

**Closing does not cascade.** A bead with any descendant that is not already closed is rejected, and the error names the
unfinished beads. Nothing is written — a multi-ID close either applies completely or leaves the store untouched. The
same guard applies to `sase bead update <id> --status closed`. Closing your own assigned phase bead is unaffected by
this guard, because a phase bead normally has no descendants.

`--force` (`-f`) is the deliberate exception: it sweeps the unfinished descendants closed, and it requires both a
`--reason` and a `--resolution` other than `done`. `--force --resolution done` is rejected — you may close an unfinished
tree, but you may not call it done. Each swept descendant gets the same resolution plus a close reason naming the
forcing parent, and the swept IDs are recorded on the parent's close event. Never force merely to make a rejected close
succeed; finish or reopen the named beads instead.

`sase bead open <id>` reopens the bead and every closed ancestor above it, clears their resolutions, close reasons, and
close timestamps, and prints the ancestor IDs it changed, so a closed parent never sits above reopened work.

### history

```bash
sase bead history <id>                                  # compact timeline
sase bead history <id> --format full                    # every from/to value
sase bead history <id> --field notes --format full      # one field's revision chain
sase bead history <id> --limit 5                        # newest 5 entries
sase bead history <id> --format json                    # machine-readable envelope
```

Replays a bead's canonical event stream as an ordered, field-level timeline. `compact` (the default) prints one line per
event with timestamp, actor, operation, and the changed field names; `full` prints each change's prior and new value,
which is how an earlier note revision that a later update replaced becomes readable again; `json` emits one envelope
with `issue_id`, `schema_version`, and `entries`. `-F`/`--field` is repeatable, and `-n`/`--limit 0` means unlimited.

```bash
sase bead history --lost-notes            # scan the store for notes text that vanished
sase bead history <id> --lost-notes       # check one bead
sase bead history --lost-notes --restore  # re-append findings after one confirmation
sase bead history --lost-notes --restore --yes  # non-interactive restore
```

`-l`/`--lost-notes` reports beads whose current notes no longer contain text an earlier revision held (with no ID it
scans the whole store). `-R`/`--restore` previews the provenance-tagged appends, prompts once, and restores them through
the same atomic append used by `note`; add `-y`/`--yes` for non-interactive approved restores. It is idempotent — a
second scan finds nothing — and `--restore` without `--lost-notes` is a usage error.

### note

```bash
# Append an attributed entry to a bead's notes
sase bead note <id> "Verified with just check; symvision clean"
sase bead note <id> "..." --author alice
```

`note` appends through a `note_appended` event; `update --notes` replaces the whole field. Prefer `note` for recording
progress, verification results, and handoff state, so you never destroy what an earlier writer left behind. Each entry
lands as `[<timestamp> · <author>] <text>` separated by a blank line, written atomically inside the Rust bead store's
mutation lock, so concurrent writers do not clobber each other. `-a`/`--author` defaults to the current agent and falls
back to the store owner.

### list

```bash
sase bead list
sase bead list --format json
sase bead list --format full --limit 3
sase bead list --status ready --type task
sase bead list --status open --type phase
sase bead list --tier epic
sase bead list --status closed --limit 0
```

`compact` is the default and prints `[type_icon] [status_icon] [id] · [title][ ← parent_id]`, where type icons are `▸`
plan, `↳` phase, and `◆` task, and status icons are `○` open, `◎` claimed, `◇` ready, `◐` in_progress, and `✓` closed.
`--color auto|always|never` (`-c`) controls compact output color and honors `NO_COLOR`; piped or non-TTY output is
colorless by default. `full` prints the same detail blocks as `sase bead show`, separated by 60-dash rules. `json` emits
an envelope with `count`, `total`, `statuses`, `implied_status_closed`, and flat issue objects in `results`.

If no `--status` is provided and no open, claimed, ready, or in-progress beads match, `list` falls back to closed beads
and prints a notice that it implied `--status closed`.

Closed results default to the newest 20 unless `--limit` / `-n` is given (`0` means unlimited); the default
open/claimed/ready/in-progress listing is unlimited. `--status`, `--type`, and `--tier` are repeatable.

### search

```bash
sase bead search auth
sase bead search auth --format full --limit 3
sase bead search auth --status open --type phase
```

Search uses a case-insensitive literal substring match across human-readable bead fields. It searches open, claimed,
ready, in-progress, and closed beads by default; use `--status`, `--type`, and `--tier` to narrow results. A missing
`--limit` or `--limit 0` means unlimited results.

### ready

```bash
# Show ready task beads with no active blockers
sase bead ready
```

No arguments. Lists task beads whose explicit status is `ready` and whose dependencies are all closed. Epic work does
not appear because phase agents are preassigned at launch.

### show

```bash
sase bead show <id>
sase bead show <id> --format compact
sase bead show <id> --format json
```

Displays full details: status, type, tier, owner, assignee, model, parent, children, dependencies, blocks, description,
notes, linked design file, artifact references, and each reference's current resolution when context is available. A
closed bead also shows its resolution, close reason, and close timestamp; use `sase bead history <id>` to read how any
of those fields got their current value. `full` is the default; `compact` prints the same single row as
`sase bead list`. `json` emits a single-bead envelope with `issue`, `ancestors`, `children`, `depends_on`, `blocks`, and
`plan`. Every relationship reference has a `resolved` flag, with unresolved IDs retaining fixed null-valued fields.

### dep

```bash
sase bead dep list <id>                                  # see what blocks <id> and what <id> blocks
sase bead dep tree <id>                                  # follow the blocking graph
sase bead dep rm <issue> <depends_on> [<depends_on2> ...] # remove wrong dependency edges
sase bead dep add <issue> <depends_on>
```

`sase bead dep` with no child subcommand delegates to `sase bead dep list`. Use `list` first when diagnosing readiness:
it prints `DEPENDS ON` and `BLOCKS`, marks outgoing edges as `satisfied` or `blocking`, and `--format full` includes the
edge's recorded `added <timestamp> by <author>` provenance.

`dep tree` walks dependencies as a terminating tree. `--direction out` follows what the root waits on, `--direction in`
follows what waits on the root, and `--direction both` renders both. It marks repeats as `⇡ (shown above)`, cycles as
`↻ (cycle)`, depth truncation as `(+N more, use --levels 0)`, and unresolved targets as `? <id> (not found)`.

`dep rm` mirrors `dep add` argument order: the source issue first, then one or more targets it should no longer depend
on. The removal is all-or-nothing, records `dependency_removed` events, and prints whether the source bead is now ready
or still blocked.

### ref

```bash
sase bead ref list [<id>]                       # list stored artifact references
sase bead ref list <id> --resolve               # include current resolution status
sase bead ref list <id> --json                  # machine-readable reference data
sase bead ref add <id> <ref> [<ref2> ...]       # attach references
sase bead ref rm <id> <ref> [<ref2> ...]        # detach references
```

`sase bead ref` with no child subcommand delegates to `sase bead ref list`. Store references without the prompt-time `@`
sigil, for example `research:202607/report.md`, `file:default:<id>`, or `bead:sase-b7`. Add and remove normalize
references through the shared artifact-reference parser; they do not require the reference to resolve on this machine.
Use `--resolve` when listing if you need the current path or unresolved marker.

### other commands

- `sase bead blocked` — list blocked beads with their blockers.
- `sase bead rm <id> [<id2> ...]` — remove beads and all their children.
- `sase bead stats` — show project statistics.
- `sase bead sync` — stage bead state in git.
- `sase bead doctor` — run bead-store, plan-link, and artifact-reference health checks.
- `sase bead doctor --fix-design-refs` — preview recoverable legacy plan links and repair them only after an interactive
  default-no confirmation.
- `sase bead doctor --fix-issue-prefix` — preview and, after confirmation, reset a store's issue prefix when it was
  leaked as the project's ProjectSpec directory key instead of its `PROJECT_NAME`. A deliberately customized prefix is
  never flagged. Forward-only: existing bead IDs keep the old prefix, only new top-level beads use the corrected one.
- `sase bead doctor --fix-projection` — preview `issues.jsonl` drift against canonical event streams and repair only the
  expected projection shape after confirmation.
- `sase bead doctor` reports artifact references with unknown namespaces, missing targets, or ambiguous targets.
- `sase bead work <epic-id|plan.md|task-id>` — launch an epic's phase and land agents or one standalone task worker
  (`--dry-run` previews). Epic launches are normally driven by plan approval; task launches are normally driven by a
  `TaskTriage` gate.

## Typical Workflow

1. **Epics come from plans.** An approved epic plan file creates the plan bead, phase beads, and dependencies
   automatically because plan approval runs `sase bead work`. Hand-create beads with `create` and `dep add` only for
   standalone tracker or backlog work.
2. **Tasks go through triage.** `sase bead create --type task ...` → refine the `open` draft →
   `sase bead update <id> --status ready` → the owner launches or closes it from its `TaskTriage` gate.
3. **Assigned working loop.** Do the work → `sase bead close <id> --note "<what you verified>"`. A bead you were
   launched to work is already `in_progress` (see Statuses). Never close the parent epic bead; the epic's land agent
   does that, and the descendant guard now rejects that close outright while sibling phases are unfinished.
