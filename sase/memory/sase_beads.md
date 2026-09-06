---
type: reference
parent: AGENTS.md
description:
  Read before creating, updating, closing, or querying sase beads — bead types and
  tiers, the status lifecycle agents must never hand-edit, task-bead triage, phase-bead
  description prefixes, and non-cascading close, resolution, and note semantics.
---

# SASE Beads

`sase bead <cmd> -h` documents every flag and `sase bead onboard` prints a quick start;
this note covers only what that help output cannot tell you. Always invoke `sase bead`,
never `.venv/bin/sase bead`.

## Store And IDs

`sase bead` reads and writes the current effective SDD bead store, so never hand-build
`sdd/...` paths. Launched agents have `SASE_SDD_PLANS_DIR` (plan files) and
`SASE_SDD_BEADS_DIR` (bead store); elsewhere resolve them from `sase repo path plans`.
Canonical state lives in `beads/events/**`; `issues.jsonl` is a generated projection.
Sibling workspaces and legacy stores are never merged in.

Any argument naming an existing bead accepts the full ID (`sase-a1`) or the suffix after
the final dash (`a1`, `a1.2`). Ambiguous shorthand fails and lists the candidates.
Output and stored relationships always use full IDs.

## Types, Tiers, And Launching

- `plan` — `-T "plan(<plan_file>[,<parent_id>])"`, top level, `--tier plan|epic`.
- `phase` — `-T "phase(<parent_id>)"`, child of a plan bead.
- `task` — `-T "task(<slug>)"` for a typed task, standalone discovered follow-up; no
  tier, required `--size` when newly created. Bare `-T task` is an error that lists the
  agent-creatable slugs. `task_type` is immutable once set (`sase bead update` has no
  `--task-type`), and a typed task takes repeatable `-f/--field k=v` values for its
  declared fields (`@<path>` reads a value from a file). Read the generated
  [[task_types]] catalog and `sase memory read task_types:<slug> -r "<why>"` for one
  type in full.

`sase bead work <epic-id|plan.md|task-id>` launches an epic's phase and land agents or
one task worker. Epic launches normally come from plan approval and task launches from a
`TaskTriage` gate, so hand-create beads only for tracker or backlog work. `--model` on
an epic plan bead selects its land agent's model; on a phase bead it selects that
phase's work model.

A phase bead's description comes from its entry in the epic plan's `phases:` frontmatter
and starts with that phase's slug ID and `: ` (for example
`login: add the endpoint and its auth checks.`). Keep that prefix when you write or edit
one by hand. Plan and epic bead descriptions do not take it.

## Statuses

`open` (draft) · `claimed` (runtime reserved) · `ready` (task bead awaiting triage) ·
`snoozed` (task bead deferred to a wake time or +1 target; set only by
`sase bead snooze`, never by `update --status`) · `in_progress` · `closed`.

Never set `claimed` by hand — the agent runner owns that transition. A bead you were
launched to work on is already `in_progress` before you read your prompt, because an
epic launch preassigns every phase bead and the land bead. Rerun
`sase bead work <epic-id>` to recover a runner that died; it reassigns every non-closed
bead and never touches closed phases.

## Task Beads

Before creating any task bead, invoke `/sase_new_task`. It gathers evidence and checks
all task statuses plus in-progress epic plans. Reports with the same underlying
defect/root cause or desired remediation are semantic duplicates: corroborate the
existing task with independent evidence instead of creating another one. An issue
credibly caused by an active epic belongs on that epic as a `DISCOVERED ISSUE:` note,
even when it is also a task duplicate.

```bash
sase bead +1 <task-id> -n "<independent reproduction and impact>" -R <artifact-ref>
sase bead create -T "task(<slug>)" -t "<title>" -d "<what is wrong and how you found it>" -z <size> -f <field>=<value>
sase bead update <id> -s ready
```

A genuinely new task starts as an `open` draft; refine its description, evidence refs,
dependencies, and scope before marking it `ready`. Each ready bead raises one
`TaskTriage` gate, from which the owner either launches `sase bead work <id>` or closes
it as `canceled`. Every new task requires an intentional size; read [[sase_sizes.md]]
before choosing it. Legacy sizeless tasks remain readable and launch through the
small-task fallback.

Each reporter contributes at most one +1, and the original creator does not count as an
additional reporter. A +1 is append-only evidence, not a vote; repeat reporters use
`sase bead note` for supplementary details. Adding the first valid +1 to an `open` task
atomically promotes it to `ready`. A closed task promotes only when the reporter's
observation window starts strictly after the current close; evidence with missing
provenance preserves the legacy reopen behavior. Stale-window evidence is recorded, but
the close remains standing. Use `--verified-after-close` only for an actual reproduction
on a tree that already contains the close. `claimed`, `ready`, `in_progress`, and
`snoozed` tasks retain their existing status behavior.

`sase bead update` accepts one or more bead IDs and applies the same requested fields to
the whole batch atomically. Beads that already match are reported as unchanged and are
not committed; descendant-close validation evaluates the entire batch together.

Epic phase workers are the exception: they never create beads. They append
`PROPOSED FOLLOW-UP: <summary — detail>` to their own phase bead, and the epic's land
agent decides which proposals become task beads.

## Closing

```bash
sase bead close <id> --note "<what you verified>"
```

That is the completion path; prefer it over `update -s closed`. Every close records a
resolution (`done` by default, else `canceled` or `superseded` through `-R`) plus
free-text `--reason`.

- **Closing never cascades.** A bead with any unclosed descendant is rejected, the error
  names those beads, and nothing is written. Finish or reopen them instead.
- `--force` sweeps unfinished descendants closed; it requires `--reason` and a
  resolution other than `done`.
- Re-closing is a safe no-op (exit 0, no event, no commit), but a conflicting resolution
  or reason is refused. Record later evidence with `sase bead note`.
- `-p 1-3` on an epic bead closes only those phase beads. `sase bead open <id>` reopens
  a bead and every closed ancestor above it.
- Never close the parent epic bead; its land agent does that.

## Notes And History

Notes are a timestamped, attributed, append-only log. `sase bead note <id> "<text>"` and
`sase bead update --note <text>` both append an entry; `update --notes` is a removed
tombstone that now errors and names `sase bead note` instead.
`sase bead note --edit <n>` rewrites note `<n>` (the ordinal `sase bead show` renders)
and `--remove <n>` retracts it; re-read `show` after either, since ordinals shift.
`sase bead history <id>` replays the event stream field by field (`--format full`
recovers a value a later write replaced), and
`sase bead history --lost-notes [--restore]` is a historical repair that finds and
re-appends notes text that went missing from a store that predates the log.

## Reading And Repairing

`list` (repeatable `--status`/`--type`/`--tier` filters; with no `--status` and nothing
active it falls back to closed beads and says so), `search` (case-insensitive
substring), `ready` (unblocked ready task beads), `show`, `blocked`, `stats`,
`dep list|tree|add|rm`, `ref list|add|rm` (artifact references, stored without the
prompt-time `@`), `rm` (a bead and all its children), and `doctor` (bead-store,
plan-link, and artifact-reference health, with confirmed `--fix-*` repairs).
