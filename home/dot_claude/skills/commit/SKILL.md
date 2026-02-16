---
name: commit
description: Create a conventional commit using ccommit. Use when the user asks to commit changes. Do not EVER use
without user request.
---

Create a commit using ccommit, which stages the specified files and commits them.

## Usage

ccommit <tag> <message> <file>...

## Valid Tags (in order of preference)

1. **feat** - New feature, feature improvement, or feature removal
2. **fix** - User-facing bug fix (not linting errors unless they caught a real bug)
3. **ref** - Refactor/restructure production code without changing external behavior. **IMPORTANT**: Only use 'ref' when
   there are ZERO user-facing changes. If users would notice any difference in behavior, use 'feat' or 'fix' instead.
4. **chore** - Other changes (build scripts, CI/CD, deps, linting, formatting, documentation) not modifying production
   code

## Instructions

1. Run `cd <git_root> && ccommit <tag> "<message>" <file>...`, where `<git_root>` is the root directory of the git
   repository, `<tag>` is one of the valid tags listed above, `<message>` is a descriptive commit message, and
   `<file>...` is a space-separated list of files to stage and commit.
2. The specified files will be staged automatically
3. The message can contain newlines for multi-line commits
4. **NEVER mention "Claude" or "Claude Code" in commit messages** - write as if a human authored the commit

## Bead Association

Before committing, check if your work is associated with a bead issue:

1. Run `bd list --status=in_progress` to see beads currently in progress
2. If the changes you're committing relate to an in-progress bead, include the `--bead` option:
   ```
   ccommit --bead <bead-id> <tag> "<message>" <file>...
   ```
3. The bead ID will be appended to the commit headline in parentheses, e.g. `feat: Add feature (beads-abc1234)`

## Example

ccommit feat "Add user authentication

This adds login and logout functionality." src/auth.py src/login.py
