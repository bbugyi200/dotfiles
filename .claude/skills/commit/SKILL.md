---
name: commit
description: Create a conventional commit using bb_commit. Use when the user asks to commit changes or after completing file modifications.
---

Create a commit using bb_commit, which stages the specified files and commits them.

## Usage
bb_commit <tag> <message> <file>...

## Valid Tags
- feat: New or changed feature
- fix: Bug fix
- ref: Refactor
- test: Test changes only
- docs: Documentation only
- chore: Any other changes

## Instructions
1. Run `bb_commit <tag> "<message>" <file>...`
2. The specified files will be staged automatically
3. The message can contain newlines for multi-line commits

## Example
bb_commit feat "Add user authentication

This adds login and logout functionality." src/auth.py src/login.py
