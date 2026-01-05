---
name: commit
description:
  Create a conventional commit using chez_commit. Use when the user asks to commit changes or after completing file
  modifications.
---

Create a commit using chez_commit, which stages the specified files and commits them.

## Usage

chez_commit <tag> <message> <file>...

## Valid Tags

- feat: New or changed feature
- fix: Bug fix
- ref: Refactor
- test: Test changes only
- docs: Documentation only
- lint: Fix linter errors
- chore: Any other changes

## Instructions

1. Run `chez_commit <tag> "<message>" <file>...`
2. The specified files will be staged automatically
3. The message can contain newlines for multi-line commits

## Example

chez_commit feat "Add user authentication

This adds login and logout functionality." src/auth.py src/login.py
