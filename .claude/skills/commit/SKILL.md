---
name: commit
description: Create a conventional commit using chez_commit. Use when the user asks to commit changes. Do not EVER use
without user request.
---

Create a commit using chez_commit, which stages the specified files and commits them.

## Usage

chez_commit <tag> <message> <file>...

## Valid Tags (in order of preference)

1. **feat** - New feature, feature improvement, or feature removal
2. **fix** - User-facing bug fix (not linting errors unless they caught a real bug)
3. **ref** - Refactor/restructure production code without changing external behavior
4. **test** - Test additions/changes/fixes only
5. **docs** - Documentation changes only
6. **lint** - Linting/formatting fixes only
7. **chore** - Other changes (build scripts, CI/CD, deps) not modifying production code

## Instructions

1. Run `chez_commit <tag> "<message>" <file>...`
2. The specified files will be staged automatically
3. The message can contain newlines for multi-line commits
4. **NEVER mention "Claude" or "Claude Code" in commit messages** - write as if a human authored the commit

## Example

chez_commit feat "Add user authentication

This adds login and logout functionality." src/auth.py src/login.py
