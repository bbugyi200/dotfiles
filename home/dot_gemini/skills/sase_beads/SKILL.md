---
name: sase_beads
description: Reference for sase bead commands (create, update, list, ready, show, dep). Use when working with beads.
---

Quick reference for the `sase bead` CLI. Use `sase bead` (not `.venv/bin/sase bead`) for all bead commands.

## Statuses

- `open` — not started (default)
- `in_progress` — actively being worked
- `closed` — complete

## Types

- `plan` — top-level work item (created with `--plan`)
- `phase` — child of a plan (created with `--parent`)

## Commands

### create

```bash
# Create a plan bead (top-level, linked to a plan file)
sase bead create --title "Add auth system" --plan plans/auth.md

# Create a phase bead (child of a plan)
sase bead create --title "Implement login endpoint" --parent <plan-bead-id>

# With optional fields
sase bead create --title "..." --parent <id> --description "Details here" --assignee alice
```

At least one of `--plan` or `--parent` is required.

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
sase bead update <id> --design plans/revised.md

# Combine multiple updates
sase bead update <id> --status in_progress --assignee alice
```

### list

```bash
# List all beads
sase bead list

# Filter by status
sase bead list --status=open
sase bead list --status=in_progress
sase bead list --status=closed

# Filter by type
sase bead list --type=plan
sase bead list --type=phase
```

Output format: `[icon] [id] · [title][ ← parent_id]` where icons are `○` open, `◐` in_progress, `✓` closed.

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

Displays full details: status, type, owner, assignee, parent, children, dependencies, blocks, description, notes, and
linked design file.

### dep add

```bash
# Make <issue> depend on <depends_on> (issue is blocked until depends_on is closed)
sase bead dep add <issue> <depends_on>
```

## Typical Workflow

1. `sase bead create --title "..." --plan plan.md` — create a plan bead
2. `sase bead create --title "Phase 1" --parent <plan-id>` — add phases
3. `sase bead dep add <phase-2-id> <phase-1-id>` — set ordering
4. `sase bead ready` — find unblocked work
5. `sase bead update <id> --status in_progress` — claim work
6. _(do the work)_
7. `sase bead update <id> --status closed` — mark done
