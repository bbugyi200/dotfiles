# SBD (Sase-Beads) - AI-Native Issue Tracking

This repository uses **sbd** (sase-beads) for issue tracking - a modern, AI-native tool designed to live directly
in your codebase alongside your code.

## What is SBD?

SBD is issue tracking that lives in your repo, making it perfect for AI coding agents and developers who want their
issues close to their code. No web UI required - everything works through the CLI and integrates seamlessly with git.

## Quick Start

### Essential Commands

```bash
# Create new issues
sbd create "Add user authentication"

# View all issues
sbd list

# View issue details
sbd show <issue-id>

# Update issue status
sbd update <issue-id> --status in_progress
sbd update <issue-id> --status done

# Sync with git remote
sbd sync
```

### Working with Issues

Issues in SBD are:

- **Git-native**: Stored in `.sbd/issues.jsonl` and synced like code
- **AI-friendly**: CLI-first design works perfectly with AI coding agents
- **Branch-aware**: Issues can follow your branch workflow
- **Always in sync**: Auto-syncs with your commits
