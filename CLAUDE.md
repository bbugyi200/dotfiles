# Chezmoi Dotfile Repo

This repository contains all of my dotfiles as well as a lot of my scripts (all of which live in the home/ directory),
some of which are pretty large (these tend to be Python projects in the home/lib/ directory).

## Executable Scripts

Since this is a Chezmoi repo, all executable scripts in the home/ directory (which tend to live in home/bin) have
`executable_` prefixed to their filenames. These scripts will exist on this system's PATH as executables without the
prefix.

## SBD Agent Workflow

This project uses **sbd** (sase-beads) for issue tracking. Run `sbd onboard` to get started.

IMPORTANT: Make sure to claim beads before starting or planning work on them and make sure to close beads after
completing the work (ex: necessary file changes) associated with them.

### Quick Reference

```bash
sbd ready              # Find available work
sbd show <id>          # View issue details
sbd update <id> --status in_progress  # Claim work
sbd close <id>         # Complete work
sbd sync               # Sync with git
```
