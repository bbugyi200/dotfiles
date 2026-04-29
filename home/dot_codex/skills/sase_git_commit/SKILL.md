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
   mention "Codex"** — write as if a human authored the commit.

4. **Check for bead association** — Run `sase bead list --status=in_progress` to see if there's an in-progress bead
   related to your changes. If so, include `--bead-id <id>` in the commit command (step 5). You do NOT need to manually
   close the bead or stage `.sase_beads/` — the commit workflow handles this automatically.

5. **Run the commit** — Execute:

   ```bash
   sase commit -M commit_message.md -f file1.py -f file2.py --bead-id <bead-id>
   ```

   Flags:
   - `-M`: Path to file containing the commit message. The file is deleted after reading.
   - `-m`: Inline commit message string (alternative to `-M`). `-m` and `-M` are mutually exclusive.
   - `-f`: File to stage (repeat for multiple files). **Include both modified AND newly created (untracked) files.**
     Omit to stage all changes (including untracked files).
   - `--bead-id`: Include if there's an in-progress bead for your changes.
   - `--name`: Branch name (only needed for `create_pull_request` method).

   The `$SASE_COMMIT_METHOD` environment variable is read automatically to determine the dispatch method
   (`create_commit`, `create_proposal`, or `create_pull_request`). Do NOT pass `--type` unless you need to override.
   Short aliases are also accepted: `commit`, `propose`, `pr`.

6. **Verify clean and pushed** — For git repos, `sase commit` normally pushes commits as part of the `create_commit`
   workflow. After it exits successfully, run:

   ```bash
   git status --short --branch
   ```

   Do not declare the commit finished while the repo is dirty or ahead of its upstream. If the branch is still ahead of
   upstream, run `git push`. If pushing fails, fix the issue or report the push failure clearly.

## Example

```bash
sase commit -M commit_message.md -f src/auth.py -f src/login.py --bead-id sase-42
```

## On Merge Conflict

If `sase commit` exits with code **2** and prints a "merge conflict" message, the local working tree is in a paused
rebase/merge state and the post-commit bookkeeping has been deferred. Do NOT re-run the original `sase commit` command —
that would attempt to re-stage and re-commit on top of the already-resolved state. Instead, resolve the conflict and
finalize:

1. **Find conflicted files**: Run `git diff --name-only --diff-filter=U`.
2. **Read each file** and resolve conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`):
   - Content between `<<<<<<< HEAD` and `=======` is YOUR version.
   - Content between `=======` and `>>>>>>> <commit>` is the INCOMING version.
   - Prefer the INCOMING version when uncertain — it's the more recent change.
   - NEVER leave conflict markers in any file.
3. **Stage resolved files**: Run `git add <file>` for each.
4. **Continue the rebase/merge**: Run `git -c core.editor=true rebase --continue` (or `git merge --continue` for a
   non-rebase merge). If this produces more conflicts, repeat steps 1–4 until clean.
5. **Verify the working tree is clean**: `git status` should show "nothing to commit, working tree clean".
6. **Finalize the sase commit**: Run `sase commit --resume`. This replays the post-commit bookkeeping (push, ChangeSpec
   row, COMMITS entry, result marker) and exits 0 on success.

```bash
sase commit --resume
```
