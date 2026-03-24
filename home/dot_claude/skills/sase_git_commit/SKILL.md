---
name: sase_git_commit
description: Commit changes using sase commit for git-based VCS (bare git and GitHub). Invoked by the sase_commit_stop_hook when uncommitted changes are detected during a commit workflow.
---

Commit changes via `sase commit`, which dispatches to the active VCS provider's commit hook.

This skill is used for both bare-git and GitHub VCS workflows. It is typically invoked by the stop hook when
`$SASE_COMMIT_METHOD` is set and uncommitted changes are detected.

## Instructions

1. **Examine uncommitted changes** — Run `git status` and `git diff` to understand what files have changed and why.

2. **Determine the commit tag** — Pick the correct conventional commit tag:
   - `feat` — New feature, feature improvement, or feature removal
   - `fix` — User-facing bug fix
   - `ref` — Refactor/restructure without changing external behavior
   - `chore` — Build scripts, CI/CD, deps, docs, or other non-production changes

3. **Compose the commit message** — Write a concise, descriptive message. **NEVER mention "Claude" or "Claude Code"** —
   write as if a human authored the commit.

4. **Construct the JSON payload** — Build a JSON object with these fields:
   ```json
   {
     "message": "<tag>: <description>",
     "files": ["file1.py", "file2.py"]
   }
   ```
   - `message`: The full commit message (tag prefix + description). Can contain newlines for multi-line messages.
   - `files`: List of files to stage. If empty, all changes are staged (`git add -A`).

5. **Check for bead association** — Run `sase bead list --status=in_progress` to see if there's an in-progress bead
   related to your changes. If so, include the bead ID in the commit message headline in parentheses, e.g.
   `feat: Add feature (sase-42)`. Also close the bead and stage `.sase_beads/`:
   ```bash
   sase bead close <bead-id>
   git add .sase_beads/
   ```

6. **Run the commit** — Execute:
   ```bash
   .venv/bin/sase commit '<json_payload>'
   ```
   The `$SASE_COMMIT_METHOD` environment variable is read automatically to determine the dispatch method
   (`create_commit`, `create_proposal`, or `create_pull_request`). Do NOT pass `--method` unless you need to override.

## Example

```bash
.venv/bin/sase commit '{"message": "feat: Add user authentication (sase-42)", "files": ["src/auth.py", "src/login.py"]}'
```

## Notes

- The VCS provider plugin handles the actual git operations (add, commit, push).
- For `create_pull_request`, the payload should also include a `name` field for the branch name.
- If `.venv/bin/sase` is not available, try `sase commit` directly.
