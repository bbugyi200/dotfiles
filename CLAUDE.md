# Chezmoi Dotfile Repo

This repository contains all of my dotfiles as well as a lot of my scripts (all of which live in the home/ directory),
some of which are pretty large (these tend to be Python projects in the home/lib/ directory).

## Executable Scripts

Since this is a Chezmoi repo, all executable scripts in the home/ directory (which tend to live in home/bin) have
`executable_` prefixed to their filenames. These scripts will exist on this system's PATH as executables without the
prefix.

## Beads Agent Workflow

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

IMPORTANT: Make sure to claim beads before starting or planning work on them and make sure to close beads after
completing the work (ex: necessary file changes) associated with them.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
```

## Chezmoi Lock

- Before making any file changes (edits, writes, creating or changing beads etc.), you MUST run `chez_lock claim` via
  Bash. This acquires a file-based lock to prevent concurrent edits from multiple agents. Only run this once per
  session, before your first file modification. Do not release the lock manually — it is released automatically by the
  stop hook.
- If the lock is held, this script will periodically poll for the lock to be released. After a max number of iterations,
  it will exit with an error. In which case, you should terminate without making any file changes.
- Do NOT run `chez_lock claim` in a background process! It MUST block the main thread to ensure that no file changes are
  made before the lock is acquired.
