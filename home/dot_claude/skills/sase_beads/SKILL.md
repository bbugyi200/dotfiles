---
name: sase_beads
description:
  Reference for sase bead commands (create, update, close, list, search, ready, show, dep). Use when working with beads.
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
- `in_progress` — actively being worked
- `closed` — complete

Do NOT set `claimed` by hand. The agent runner owns it: it claims a bead when a bead-carrying agent starts waiting,
promotes the claim to `in_progress` right before that agent begins working, and releases it back to `open` if the agent
dies before it ever started. A bead you were told to work on is already `in_progress` by the time you read your prompt.

The wait-time claim is best-effort, and the `bead_claim_checks` chop reconciles whatever it misses, so a waiting agent's
bead can turn `claimed` a few seconds after that agent starts waiting rather than instantly. A freshly launched epic
whose phases are still `open` is normal for one reconciler interval; it is not a signal to claim anything by hand.

## Types

- `plan` — plan-like work item (created with `--type "plan(...)"`)
- `phase` — child of a plan (created with `--type "phase(...)"`)

Plan beads can carry bead tier `--tier plan` or `--tier epic`. Plan files live under `${SASE_SDD_PLANS_DIR}/{YYYYMM}/`
in migrated projects; `sase repo path plans` preserves the legacy layout for older stores. Plan files independently
carry `tier: tale` or `tier: epic` in frontmatter. `sase bead work` runs `epic`-tier plan beads by launching phase +
land agents.

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

# Create a nested plan (plan with parent)
sase bead create --title "Sub-plan" --type "plan(${SASE_SDD_PLANS_DIR}/202605/sub.md,<parent-bead-id>)"

# With optional fields
sase bead create --title "..." --type "phase(<id>)" --description "Details here" --assignee alice --size medium
```

`--type` / `-T` is required. Syntax: `plan(<plan_file>)`, `plan(<plan_file>,<parent_id>)`, or `phase(<parent_id>)`.
`--size` / `-z` accepts `xsmall|small|medium|large|xlarge` and controls plan-first prompting and default model routing.

### update

```bash
# Claim ready work by hand
sase bead update <id> --status in_progress

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

Use `close` for completion and `open` for reopening.

### close / open

```bash
# Close finished work (the standard completion path; used by runtime prompts)
sase bead close <id>
sase bead close <id1> <id2> --reason "why"

# Reopen a closed bead
sase bead open <id>
```

`close` accepts multiple IDs and an optional `-r`/`--reason`; prefer it over `update --status closed`.

### list

```bash
sase bead list
sase bead list --format json
sase bead list --format full --limit 3
sase bead list --status open --type phase
sase bead list --tier epic
sase bead list --status closed --limit 0
```

`compact` is the default and prints `[icon] [id] · [title][ ← parent_id]`, where icons are `○` open, `◎` claimed, `◐`
in_progress, and `✓` closed. `full` prints the same detail blocks as `sase bead show`, separated by 60-dash rules.
`json` emits an envelope with `count`, `total`, `statuses`, `implied_status_closed`, and flat issue objects in
`results`.

If no `--status` is provided and no open, claimed, or in-progress beads match, `list` falls back to closed beads and
prints a notice that it implied `--status closed`.

Closed results default to the newest 20 unless `--limit` / `-n` is given (`0` means unlimited); the default
open/claimed/in-progress listing is unlimited. `--status`, `--type`, and `--tier` are repeatable.

### search

```bash
sase bead search auth
sase bead search auth --format full --limit 3
sase bead search auth --status open --type phase
```

Search uses a case-insensitive literal substring match across human-readable bead fields. It searches open, claimed,
in-progress, and closed beads by default; use `--status`, `--type`, and `--tier` to narrow results. A missing `--limit`
or `--limit 0` means unlimited results.

### ready

```bash
# Show open beads with no active blockers
sase bead ready
```

No arguments. Lists all beads that are open and have no unresolved dependencies blocking them. Claimed beads are already
reserved by a live agent, so they do not appear here.

### show

```bash
sase bead show <id>
```

Displays full details: status, type, tier, owner, assignee, model, parent, children, dependencies, blocks, description,
notes, and linked design file.

### dep add

```bash
# Make <issue> depend on <depends_on> (issue is blocked until depends_on is closed)
sase bead dep add <issue> <depends_on>
```

### other commands

- `sase bead blocked` — list blocked beads with their blockers.
- `sase bead rm <id> [<id2> ...]` — remove beads and all their children.
- `sase bead stats` — show project statistics.
- `sase bead sync` — stage bead state in git.
- `sase bead doctor` — run health checks.
- `sase bead work <epic-id|plan.md>` — launch an epic's phase and land agents (`--dry-run` previews). Normally driven by
  plan approval; do not run it casually from a working agent.

## Typical Workflow

1. **Epics come from plans.** An approved epic plan file creates the plan bead, phase beads, and dependencies
   automatically because plan approval runs `sase bead work`. Hand-create beads with `create` and `dep add` only for
   standalone tracker or backlog work.
2. **Working loop.** `sase bead ready` → `sase bead update <id> --status in_progress` → do the work →
   `sase bead close <id>`. A bead you were launched to work is already `in_progress` (see Statuses). Never close the
   parent epic bead; the epic's land agent does that.
