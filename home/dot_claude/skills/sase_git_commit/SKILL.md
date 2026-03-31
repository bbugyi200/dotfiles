---
name: sase_git_commit
description:
  Commit changes using sase commit for git-based VCS (bare git and GitHub). This is the ONLY way you should EVER commit
  to git repos. NEVER invoke this skill unless the user explicitly asks you to commit or a post-completion hook triggers
  it.
---

Commit changes via the `sase commit` command.

## Instructions

1. **Examine uncommitted changes** — Run `git status` and `git diff` to understand what files have changed and why. Pay
   attention to **untracked files** (newly created files) shown in `git status` — these must also be staged.

2. **Determine the commit tag** — Pick the correct conventional commit tag:
   - `feat` — New feature, feature improvement, or feature removal
   - `fix` — User-facing bug fix
   - `ref` — Refactor/restructure without changing external behavior
   - `chore` — Build scripts, CI/CD, deps, docs, or other non-production changes

3. **Write a commit message file** — Create a file (e.g., `commit_message.md`) containing the commit message. **NEVER
   mention "Claude" or "Claude Code"** — write as if a human authored the commit.

4. **Check for bead association** — Run `sase bead list --status=in_progress` to see if there's an in-progress bead
   related to your changes. If so, include `--bead-id <id>` in the commit command (step 5). You do NOT need to manually
   close the bead or stage `.sase_beads/` — the commit workflow handles this automatically.

5. **Run the commit** — Execute:

   ```bash
   sase commit -m commit_message.md -f file1.py -f file2.py --bead-id <bead-id>
   ```

   Flags:
   - `-m`: Path to file containing the commit message (required). The file is deleted after reading.
   - `-f`: File to stage (repeat for multiple files). **Include both modified AND newly created (untracked) files.**
     Omit to stage all changes (including untracked files).
   - `--bead-id`: Include if there's an in-progress bead for your changes.
   - `--name`: Branch name (only needed for `create_pull_request` method).

   The `$SASE_COMMIT_METHOD` environment variable is read automatically to determine the dispatch method
   (`create_commit`, `create_proposal`, or `create_pull_request`). Do NOT pass `--method` unless you need to override.

## Example

```bash
sase commit -m commit_message.md -f src/auth.py -f src/login.py --bead-id sase-42
```
