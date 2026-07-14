---
name: sase_beads
description:
  Reference for sase bead commands (create, update, list, search, ready, show, dep). Use when working with beads.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_beads --reason "<one-line reason for using this skill>"
```

Quick reference for the `sase bead` CLI. Use `sase bead` (not `.venv/bin/sase bead`) for all bead commands.

## SDD Path Convention

Do not assume `sdd/...` is relative to the current checkout. In launched agents, use `SASE_SDD_PLANS_DIR` for plan paths
and `SASE_SDD_BEADS_DIR` for the bead store. Outside a launched agent, resolve them with
`SASE_SDD_PLANS_DIR=$(sase sdd path plans)` and `SASE_SDD_BEADS_DIR=$(sase sdd path beads)`.

The examples below use `${SASE_SDD_PLANS_DIR}/...` plan paths. Quote `--type` values so shell expansion works reliably.

`sase bead` reads and writes the current effective SDD bead store. In migrated projects this is `beads/` in the plans
sidecar; legacy in-tree projects use `sdd/beads/`, and legacy local/separate-repo stores use `.sase/sdd/beads/`.
Canonical state lives in `beads/events/**` when present; `issues.jsonl` is a generated compatibility projection. It does
not merge bead records from numbered sibling workspaces or legacy bead stores.

## Statuses

- `open` — not started (default)
- `in_progress` — actively being worked
- `closed` — complete

## Types

- `plan` — plan-like work item (created with `--type plan(...)`)
- `phase` — child of a plan (created with `--type phase(...)`)

Plan beads can carry bead tier `--tier plan` or `--tier epic`. Plan files live under `${SASE_SDD_PLANS_DIR}/{YYYYMM}/`
in migrated projects; `sase sdd path plans` preserves the legacy layout for older stores. Plan files independently carry
`tier: tale` or `tier: epic` in frontmatter. `sase bead work` runs `epic`-tier plan beads by launching phase + land
agents.

## Commands

### create

```bash
# Create a plan bead (top-level, linked to a plan file)
sase bead create --title "Add auth system" --type "plan(${SASE_SDD_PLANS_DIR}/202605/auth.md)" --tier plan

# Create an executable epic bead
sase bead create --title "Auth epic" --type "plan(${SASE_SDD_PLANS_DIR}/202605/auth.md)" --tier epic

# Create an executable epic bead with a land-agent model
sase bead create --title "Auth epic" --type "plan(${SASE_SDD_PLANS_DIR}/202605/auth.md)" --tier epic --model claude/opus

# Create a phase bead (child of a plan)
sase bead create --title "Implement login endpoint" --type phase(<plan-bead-id>)

# Create a phase bead with a phase-work model
sase bead create --title "Implement login endpoint" --type phase(<plan-bead-id>) --model codex/gpt-5.6-sol

# Create a nested plan (plan with parent)
sase bead create --title "Sub-plan" --type "plan(${SASE_SDD_PLANS_DIR}/202605/sub.md,<parent-bead-id>)"

# With optional fields
sase bead create --title "..." --type phase(<id>) --description "Details here" --assignee alice
```

`--type` / `-T` is required. Syntax: `plan(<plan_file>)`, `plan(<plan_file>,<parent_id>)`, or `phase(<parent_id>)`.

### update

```bash
# Change status (most common use)
sase bead update <id> --status in_progress
sase bead update <id> --status closed
sase bead update <id> --status open

# Update other fields
sase bead update <id> --title "New title"
sase bead update <id> --description "Updated description"
sase bead update <id> --notes "Implementation notes"
sase bead update <id> --assignee bob
sase bead update <id> --design "${SASE_SDD_PLANS_DIR}/202605/revised.md"
sase bead update <id> --model codex/gpt-5.6-sol
sase bead update <id> --model ""  # clear the stored model
# Combine multiple updates
sase bead update <id> --status in_progress --assignee alice
```

### list

```bash
# List open and in-progress beads
sase bead list

# Limit printed beads; closed listings default to 20, 0 means unlimited
sase bead list --limit 5
sase bead list -n 0

# Filter by status
sase bead list --status=open
sase bead list --status=in_progress
sase bead list --status=closed

# Filter by type
sase bead list --type=plan
sase bead list --type=phase

# Filter by plan-bead tier
sase bead list --tier=epic
sase bead list --tier=plan
```

Output format: `[icon] [id] · [title][ ← parent_id]` where icons are `○` open, `◐` in_progress, `✓` closed. If no
`--status` is provided and no open or in-progress beads match, `list` falls back to closed beads and prints a notice
that it implied `--status closed`.

Whenever the final result set includes closed beads — via `--status closed`, a repeated status filter that includes
`closed`, or the implicit closed fallback — and `--limit` is omitted, `list` prints only the newest 20 matching beads.
Pass `--limit 0` to print all matching closed beads. The default open/in-progress listing stays unlimited.

### search

```bash
# Search every bead status with compact output
sase bead search auth --format compact

# Emit a machine-readable JSON envelope
sase bead search auth --format json

# Show complete bead details for the first 3 matches
sase bead search auth --format full --limit 3

# Scope by status and type
sase bead search auth --status open --type phase

# Scope plan beads by tier
sase bead search auth --type plan --tier epic
```

Search uses a case-insensitive literal substring match across human-readable bead fields. It searches open, in-progress,
and closed beads by default; use `--status`, `--type`, and `--tier` to narrow results. A missing `--limit` or
`--limit 0` means unlimited results.

### ready

```bash
# Show open beads with no active blockers
sase bead ready
```

No arguments. Lists all beads that are open and have no unresolved dependencies blocking them.

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

## Typical Workflow

1. `sase bead create --title "..." --type "plan(${SASE_SDD_PLANS_DIR}/202605/plan.md)" --tier epic` — create an epic
   plan bead
2. `sase bead create --title "Phase 1" --type phase(<plan-id>)` — add phases
3. `sase bead dep add <phase-2-id> <phase-1-id>` — set ordering
4. `sase bead ready` — find unblocked work
5. `sase bead update <id> --status in_progress` — claim work
6. _(do the work)_
7. `sase bead update <id> --status closed` — mark done
