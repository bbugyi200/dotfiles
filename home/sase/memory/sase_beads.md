---
type: long
parent: AGENTS.md
description:
  Read before creating, updating, closing, or querying sase beads — bead types and tiers, the status lifecycle agents
  must never hand-edit, task-bead triage, phase-bead description prefixes, and non-cascading close, resolution, and note
  semantics.
---

# SASE Beads

`sase bead <cmd> -h` documents every flag and `sase bead onboard` prints a quick start; this note covers only what that
help output cannot tell you. Always invoke `sase bead`, never `.venv/bin/sase bead`.

## Store And IDs

`sase bead` reads and writes the current effective SDD bead store, so never hand-build `sdd/...` paths. Launched agents
have `SASE_SDD_PLANS_DIR` (plan files) and `SASE_SDD_BEADS_DIR` (bead store); elsewhere resolve them from
`sase repo path plans`. Canonical state lives in `beads/events/**`; `issues.jsonl` is a generated projection. Sibling
workspaces and legacy stores are never merged in.

Any argument naming an existing bead accepts the full ID (`sase-a1`) or the suffix after the final dash (`a1`, `a1.2`).
Ambiguous shorthand fails and lists the candidates. Output and stored relationships always use full IDs.

## Types, Tiers, And Launching

- `plan` — `-T "plan(<plan_file>[,<parent_id>])"`, top level, `--tier plan|epic`.
- `phase` — `-T "phase(<parent_id>)"`, child of a plan bead.
- `task` — `-T task`, standalone discovered follow-up; no tier, optional `--size` for model routing.

`sase bead work <epic-id|plan.md|task-id>` launches an epic's phase and land agents or one task worker. Epic launches
normally come from plan approval and task launches from a `TaskTriage` gate, so hand-create beads only for tracker or
backlog work. `--model` on an epic plan bead selects its land agent's model; on a phase bead it selects that phase's
work model.

A phase bead's description comes from its entry in the epic plan's `phases:` frontmatter and starts with that phase's
slug ID and `: ` (for example `login: add the endpoint and its auth checks.`). Keep that prefix when you write or edit
one by hand. Plan and epic bead descriptions do not take it.

## Statuses

`open` (draft) · `claimed` (runtime reserved) · `ready` (task bead awaiting triage) · `in_progress` · `closed`.

Never set `claimed` by hand — the agent runner owns that transition. A bead you were launched to work on is already
`in_progress` before you read your prompt, because an epic launch preassigns every phase bead and the land bead. Rerun
`sase bead work <epic-id>` to recover a runner that died; it reassigns every non-closed bead and never touches closed
phases.

## Task Beads

Capture useful work that falls outside your current task as a task bead: create it as an `open` draft, refine its
description and dependencies, then mark it `ready`. Each ready bead raises one `TaskTriage` gate, from which the owner
either launches `sase bead work <id>` or closes it as `canceled`.

```bash
sase bead create -T task -t "<title>" -d "<what is wrong and how you found it>"
sase bead update <id> -s ready
```

Epic phase workers are the exception: they never create beads. They append `PROPOSED FOLLOW-UP: <summary — detail>` to
their own phase bead, and the epic's land agent decides which proposals become task beads.

## Closing

```bash
sase bead close <id> --note "<what you verified>"
```

That is the completion path; prefer it over `update -s closed`. Every close records a resolution (`done` by default,
else `canceled` or `superseded` through `-R`) plus free-text `--reason`.

- **Closing never cascades.** A bead with any unclosed descendant is rejected, the error names those beads, and nothing
  is written. Finish or reopen them instead.
- `--force` sweeps unfinished descendants closed; it requires `--reason` and a resolution other than `done`.
- Re-closing is a safe no-op (exit 0, no event, no commit), but a conflicting resolution or reason is refused. Record
  later evidence with `sase bead note`.
- `-p 1-3` on an epic bead closes only those phase beads. `sase bead open <id>` reopens a bead and every closed ancestor
  above it.
- Never close the parent epic bead; its land agent does that.

## Notes And History

`sase bead note <id> "<text>"` appends an attributed entry atomically, while `update --notes` replaces the whole field,
so use `note` for progress, verification, and handoff state. `sase bead history <id>` replays the event stream field by
field (`--format full` recovers a value a later write replaced), and `sase bead history --lost-notes [--restore]` finds
and re-appends notes text that went missing.

## Reading And Repairing

`list` (repeatable `--status`/`--type`/`--tier` filters; with no `--status` and nothing active it falls back to closed
beads and says so), `search` (case-insensitive substring), `ready` (unblocked ready task beads), `show`, `blocked`,
`stats`, `dep list|tree|add|rm`, `ref list|add|rm` (artifact references, stored without the prompt-time `@`), `rm` (a
bead and all its children), and `doctor` (bead-store, plan-link, and artifact-reference health, with confirmed `--fix-*`
repairs).
