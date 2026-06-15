---
name: sase_git_commit
description:
  Commit changes using sase commit for git-based VCS (bare git and GitHub). This is the ONLY way you should EVER commit
  to git repos. NEVER invoke this skill unless the user explicitly asks you to commit or a post-completion finalizer
  triggers it.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_git_commit --reason "<one-line reason for using this skill>"
```

Commit changes via the `sase_git_commit` wrapper. The wrapper records skill invocation evidence, then delegates to
`sase commit`.

## Instructions

1. **Examine uncommitted changes** — Run `git status` and `git diff` to understand what files have changed and why. Pay
   attention to **untracked files** (newly created files) shown in `git status` — these must also be staged.

2. **Determine the commit tag** — Pick the correct conventional commit tag. The header shape is
   `tag(optional-scope)!: description`; the scope is optional and the `!` marks a breaking change.
   - `feat` — Adds or meaningfully improves a user-facing feature or capability. This normally triggers a minor version
     bump. Feature removal is also `feat`, but is backwards-incompatible and must carry the breaking-change marker
     described below.
   - `fix` — Fixes a user-facing bug or incorrect behavior. This normally triggers a patch version bump.
   - `perf` — Improves performance without changing external behavior.
   - `refactor` — Restructures code without changing external behavior; no new features, no bug fixes.
   - `docs` — Documentation-only changes, including README files, docstrings, comments, or docs sites.
   - `test` — Adds or corrects tests only; no production code changes.
   - `build` — Build system, packaging, or dependency changes, including `pyproject.toml`, lockfiles, or justfiles.
     Dependency bumps are conventionally scoped as `build(deps)` or `chore(deps)`.
   - `ci` — CI/CD pipeline and workflow configuration changes.
   - `style` — Formatting or whitespace only; no change to code meaning.
   - `revert` — Reverts a previous commit; reference the reverted commit in the message body.
   - `chore` — Maintenance that fits none of the tags above, such as tooling config, housekeeping, or asset updates.

   A project may restrict its allowed tag set, for example via a PR-title check. When in doubt, prefer a tag the
   project's history already uses.

   Commit tags can drive automated release tooling such as release-please or release-plz. These tools parse tags to
   compute semantic version bumps and changelog entries: `fix` -> patch, `feat` -> minor, and breaking changes -> major.
   The tag is not cosmetic; picking the wrong tag can ship the wrong version number or omit a changelog entry.

   Any backwards-incompatible API, CLI, config format, or behavior change MUST be marked using standard breaking-change
   syntax that release-please and release-plz parse:
   - Append `!` after the tag or scope, such as `feat!: drop legacy config format` or `feat(cli)!: remove old flag`;
     and/or
   - Add a footer line at the end of the commit message body:
     `BREAKING CHANGE: <description of what broke and how to migrate>`.

   The spec-standard footer token is singular `BREAKING CHANGE:`; `BREAKING-CHANGE:` is also accepted. Prefer the `!`
   suffix even when the footer is present, since squash-merge workflows keep the title but can mangle bodies.

3. **Write a commit message file** — Create a file (e.g., `commit_message.md`) containing the commit message. **NEVER
   mention "Gemini" or "Gemini CLI"** — write as if a human authored the commit.

4. **Run the commit** — Execute:

   ```bash
   sase_git_commit -M commit_message.md -f file1.py -f file2.py
   ```

   For post-completion finalizer-triggered commits, use one `-f` flag for each listed file you intend to commit. Omit
   `-f` only when you intentionally want to stage every change in that repository.

   Flags:
   - `-M`: Path to file containing the commit message. The file is deleted after reading.
   - `-m`: Inline commit message string (alternative to `-M`). `-m` and `-M` are mutually exclusive.
   - `-f`: File to stage (repeat for multiple files). **Include both modified AND newly created (untracked) files.**
     Omitting all `-f` flags stages all changes (including untracked files); reserve that for an intentional
     whole-repository commit.
   - `--name`: Branch name (only needed for `create_pull_request` method).

   The `$SASE_COMMIT_METHOD` environment variable is read automatically to determine the dispatch method
   (`create_commit`, `create_proposal`, or `create_pull_request`). Do NOT pass `--type` unless you need to override.
   Short aliases are also accepted: `commit`, `propose`, `pr`.

5. **Verify clean and pushed** — For git repos, `sase_git_commit` delegates to `sase commit`, which normally pushes
   commits as part of the `create_commit` workflow. After it exits successfully, run:

   ```bash
   git status --short --branch
   ```

   Do not declare the commit finished while the repo is dirty or ahead of its upstream. If the branch is still ahead of
   upstream, run `git push`. If pushing fails, fix the issue or report the push failure clearly.

## Example

```bash
sase_git_commit -M commit_message.md -f src/auth.py -f src/login.py
```

## On Merge Conflict

If `sase_git_commit` exits with code **2** and prints a "merge conflict" message, the local working tree is in a paused
rebase/merge state and the post-commit bookkeeping has been deferred. Do NOT re-run the original `sase_git_commit`
command — that would attempt to re-stage and re-commit on top of the already-resolved state. Instead, resolve the
conflict and finalize:

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
6. **Finalize the sase commit**: Run `sase_git_commit --resume`. This replays the post-commit bookkeeping (push,
   ChangeSpec row, COMMITS entry, result marker) and exits 0 on success.

```bash
sase_git_commit --resume
```
