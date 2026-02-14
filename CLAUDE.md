# Chezmoi Dotfile Repo

This repository contains all of my dotfiles as well as a lot of my scripts (all of which live in the home/ directory),
some of which are pretty large (these tend to be Python projects in the home/lib/ directory).

## Executable Scripts

Since this is a Chezmoi repo, all executable scripts in the home/ directory (which tend to live in home/bin) have
`executable_` prefixed to their filenames. These scripts will exist on this system's PATH as executables without the
prefix.

## Beads Agent Workflow

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
```
