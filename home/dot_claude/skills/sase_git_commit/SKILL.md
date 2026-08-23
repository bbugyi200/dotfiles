---
name: sase_git_commit
description:
  Commit changes using sase stitch create for git-based VCS (bare git and GitHub). This
  is the ONLY way you should EVER commit to git repos manually. NEVER invoke this skill
  unless the user explicitly asks you to commit or the host explicitly instructs you to
  invoke `/sase_git_commit`; the provider-neutral `/sase_final` flow is not such an
  instruction.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_git_commit --reason "<one-line reason for using this skill>"
```

Commit changes via the `sase_git_commit` wrapper. The wrapper records skill invocation
evidence, then delegates to `sase stitch create`.

Only use this skill for an explicit manual commit request or an explicit host
instruction naming `/sase_git_commit`. A `commit` action in a `/sase_final` manifest is
declarative; `builtin@commit` executes the corresponding `sase stitch create` after the
host accepts the declaration.

## Instructions

1. **Examine uncommitted changes** — Run `git status` and `git diff` to understand what
   files have changed and why. Every changed file, including **untracked files** (newly
   created files) shown in `git status`, is committed automatically — review the list to
   confirm nothing unwanted is dirty and decide whether any path needs `-x`.

2. **Determine the commit tag** — Pick the correct conventional commit tag. The header
   shape is `tag(optional-scope)!: description`; the scope is optional and the `!` marks
   a breaking change.
   - `feat` — Adds or meaningfully improves a user-facing feature or capability. This
     normally triggers a minor version bump. Feature removal is also `feat`, but is
     backwards-incompatible and must carry the breaking-change marker described below.
   - `fix` — Fixes a user-facing bug or incorrect behavior. This normally triggers a
     patch version bump.
   - `perf` — Improves performance without changing external behavior.
   - `refactor` — Restructures code without changing external behavior; no new features,
     no bug fixes.
   - `docs` — Documentation-only changes, including README files, docstrings, comments,
     or docs sites.
   - `test` — Adds or corrects tests only; no production code changes.
   - `build` — Build system, packaging, or dependency changes, including
     `pyproject.toml`, lockfiles, or justfiles. Dependency bumps are conventionally
     scoped as `build(deps)` or `chore(deps)`.
   - `ci` — CI/CD pipeline and workflow configuration changes.
   - `style` — Formatting or whitespace only; no change to code meaning.
   - `revert` — Reverts a previous commit; reference the reverted commit in the message
     body.
   - `chore` — Maintenance that fits none of the tags above, such as tooling config,
     housekeeping, or asset updates.

   Picking a tag is mandatory, not advisory: `sase stitch create` **rejects** a message
   whose subject line is not a conventional header, before it syncs any bead or runs any
   hook. If that happens, rewrite the subject in the same `-M` message file (which is
   preserved on failure) and re-run the identical command — do not disable the check.

   A project may restrict its allowed tag set, for example via a PR-title check or
   `commit.message.allowed_types`. When in doubt, prefer a tag the project's history
   already uses.

   Commit tags can drive automated release tooling such as release-please or
   release-plz. These tools parse tags to compute semantic version bumps and changelog
   entries: `fix` -> patch, `feat` -> minor, and breaking changes -> major. The tag is
   not cosmetic; picking the wrong tag can ship the wrong version number or omit a
   changelog entry.

   Any backwards-incompatible API, CLI, config format, or behavior change MUST be marked
   using standard breaking-change syntax that release-please and release-plz parse:
   - Append `!` after the tag or scope, such as `feat!: drop legacy config format` or
     `feat(cli)!: remove old flag`; and/or
   - Add a footer line at the end of the commit message body:
     `BREAKING CHANGE: <description of what broke and how to migrate>`.

   The spec-standard footer token is singular `BREAKING CHANGE:`; `BREAKING-CHANGE:` is
   also accepted. Prefer the `!` suffix even when the footer is present, since
   squash-merge workflows keep the title but can mangle bodies.

3. **Write a commit message file** — Create the file at `.sase/commit_message.md`,
   relative to the repository being committed, containing the commit message. Create the
   `.sase/` directory first if it does not exist yet (e.g. `mkdir -p .sase`) — do not
   rely on a file-writing tool to auto-create parent directories. `.sase/` is
   git-ignored in every SASE-managed checkout, so this temporary file never shows up as
   an uncommitted change to the post-completion commit finalizer and can never be swept
   into a whole-repository commit. **NEVER mention "Claude" or "Claude Code"** — write
   as if a human authored the commit. Do not preemptively stash, fast-forward, pull, or
   hand-sync before committing; `sase stitch create` commits first, rebases
   automatically, and handles mechanical bead-store conflicts.

4. **Run the commit** — Execute:

   ```bash
   sase_git_commit -M .sase/commit_message.md
   ```

   Flags:
   - `-M`: Path to file containing the commit message. The file is deleted only after a
     successful commit. If the command fails, retry with the same `-M` path; do not
     recreate the message.
   - `-m`: Inline commit message string (alternative to `-M`). `-m` and `-M` are
     mutually exclusive.
   - `-x`: Repo-relative path (file or directory) to leave out of this commit
     (repeatable). Everything else that changed, including untracked files, is
     committed. A path that has no pending change is an error, so the commit fails
     loudly rather than quietly committing a mistyped path.
   - `-B`: Do not auto-close your assigned in-progress bead; use it for mid-flight
     commits.
   - `--name`: Branch name (only needed for `create_pull_request` method).

   The `$SASE_COMMIT_METHOD` environment variable is read automatically to determine the
   dispatch method (`create_commit`, `create_proposal`, or `create_pull_request`). Do
   NOT pass `--type` unless you need to override. Short aliases are also accepted:
   `commit`, `propose`, `pr`.

   Exit codes:
   - `0`: Commit succeeded.
   - `1`: Commit failed with a printed reason. Fix the cause and re-run the same
     command. A successful commit auto-closes the assigned `in_progress` bead in this
     repo. Re-runs stay safe when the bead is already closed, but failed lifecycle
     validation must be resolved explicitly.
   - `2`: A rebase is paused for a real conflict. Do not re-run the original command
     while the rebase is paused; use the recovery flow below.

5. **Verify clean and pushed** — For git repos, `sase_git_commit` delegates to
   `sase stitch create`, which normally pushes commits as part of the `create_commit`
   workflow. After it exits successfully, run:

   ```bash
   git status --short --branch
   ```

   Do not declare the commit finished while the repo is dirty or ahead of its upstream.
   If the branch is still ahead of upstream, run `git push`. If pushing fails, fix the
   issue or report the push failure clearly.

## Example

```bash
sase_git_commit -M .sase/commit_message.md
```

To leave a path out of the commit:

```bash
sase_git_commit -M .sase/commit_message.md -x sdd/plans/202608/unrelated_plan.md
```

## On Merge Conflict

Bead-store conflicts and benign upstream movement are handled automatically. If
`sase_git_commit` exits with code **2** and prints a "merge conflict" message, the local
working tree is in a paused rebase state and the post-commit bookkeeping has been
deferred. Do NOT re-run the original `sase_git_commit` command — that would attempt to
re-stage and re-commit on top of the already-paused state. Instead, resolve the conflict
and finalize:

1. **Find conflicted files**: Run `git diff --name-only --diff-filter=U`.
2. **Read each file** and resolve conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`):
   - During a rebase, `HEAD` is the upstream version and the other side is the local
     commit being replayed.
   - Prefer the upstream version when uncertain — it's the more recent change.
   - NEVER leave conflict markers in any file.
3. **Stage resolved files**: Run `git add <file>` for each.
4. **Continue the rebase/merge**: Run `git -c core.editor=true rebase --continue` (or
   `git merge --continue` for a non-rebase merge). If this produces more conflicts,
   repeat steps 1–4 until clean.
5. **Verify the working tree is clean**: `git status` should show "nothing to commit,
   working tree clean".
6. **Finalize the sase stitch create**: Run `sase_git_commit --resume`. This replays the
   post-commit bookkeeping (push, Patch row, STITCHES entry, result marker) and exits 0
   on success.

```bash
sase_git_commit --resume
```
