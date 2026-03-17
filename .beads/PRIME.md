# SBD Workflow Context

> **Context Recovery**: Run `sbd prime` after compaction, clear, or new session. Hooks auto-call this in Claude Code when
> .sbd/ detected

# Session Close Protocol

Before wrapping up, run `sbd sync` to ensure sbd data is flushed to JSONL.

**Do NOT commit or push code changes.** The stop hook handles commit prompting — it runs quality checks and then asks
you to use the `/commit` skill if there are uncommitted changes.

## Core Rules

- **Default**: Use sbd for ALL task tracking (`sbd create`, `sbd ready`, `sbd close`)
- **Prohibited**: Do NOT use TodoWrite, TaskCreate, or markdown files for task tracking
- **Workflow**: Create sbd issue BEFORE writing code, mark in_progress when starting
- Persistence you don't need beats lost context
- Git workflow: hooks auto-sync, run `sbd sync` at session end
- Session management: check `sbd ready` for available work

## Essential Commands

### Finding Work

- `sbd ready` - Show issues ready to work (no blockers)
- `sbd list --status=open` - All open issues
- `sbd list --status=in_progress` - Your active work
- `sbd show <id>` - Detailed issue view with dependencies

### Creating & Updating

- `sbd create --title="..." --type=task|bug|feature --priority=2` - New issue
  - Priority: 0-4 or P0-P4 (0=critical, 2=medium, 4=backlog). NOT "high"/"medium"/"low"
- `sbd update <id> --status=in_progress` - Claim work
- `sbd update <id> --assignee=username` - Assign to someone
- `sbd update <id> --title/--description/--notes/--design` - Update fields inline
- `sbd close <id>` - Mark complete
- `sbd close <id1> <id2> ...` - Close multiple issues at once (more efficient)
- `sbd close <id> --reason="explanation"` - Close with reason
- **Tip**: When creating multiple issues/tasks/epics, use parallel subagents for efficiency
- **WARNING**: Do NOT use `sbd edit` - it opens $EDITOR (vim/nano) which blocks agents

### Dependencies & Blocking

- `sbd dep add <issue> <depends-on>` - Add dependency (issue depends on depends-on)
- `sbd blocked` - Show all blocked issues
- `sbd show <id>` - See what's blocking/blocked by this issue

### Sync & Collaboration

- `sbd sync` - Sync with git remote (run at session end)
- `sbd sync --status` - Check sync status without syncing

### Project Health

- `sbd stats` - Project statistics (open/closed/blocked counts)
- `sbd doctor` - Check for issues (sync problems, missing hooks)

## Common Workflows

**Starting work:**

```bash
sbd ready           # Find available work
sbd show <id>       # Review issue details
sbd update <id> --status=in_progress  # Claim it
```

**Completing work:**

```bash
sbd close <id1> <id2> ...    # Close all completed issues at once
sbd sync                     # Push to remote
```

**Creating dependent work:**

```bash
# Run sbd create commands in parallel (use subagents for many items)
sbd create --title="Implement feature X" --type=feature
sbd create --title="Write tests for X" --type=task
sbd dep add beads-yyy beads-xxx  # Tests depend on Feature (Feature blocks tests)
```
