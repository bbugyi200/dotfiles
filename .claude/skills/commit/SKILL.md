---
name: commit
description: Create a conventional commit using bb_commit. Use when the user asks to commit changes or after completing file modifications.
---

Stage all relevant changes and create a commit using bb_commit.

## Usage
bb_commit <tag> <message>

## Valid Tags
- feat: New or changed feature
- fix: Bug fix
- ref: Refactor
- test: Test changes only
- docs: Documentation only
- chore: Any other changes

## Instructions
1. Stage the relevant files with `git add`
2. Run `bb_commit <tag> "<message>"`
3. The message can contain newlines for multi-line commits

## Example
bb_commit feat "Add user authentication

This adds login and logout functionality."
