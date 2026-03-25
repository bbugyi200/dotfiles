---
name: sase_git_commit
description:
  Commit changes using sase commit for git-based VCS (bare git and GitHub). This is the ONLY way you should EVER commit
  to git repos.
---

Commit changes via the `sase commit` command.

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
     "files": ["file1.py", "file2.py"],
     "bead_id": "sase-42"
   }
   ```

   - `message`: The full commit message (tag prefix + description). Can contain newlines for multi-line messages.
   - `files`: List of files to stage. If empty, all changes are staged (`git add -A`).
   - `bead_id`: (optional) If there's an in-progress bead related to your changes, include its ID here. The workflow
     will automatically close the bead, stage `.sase_beads/`, and append the bead ID to the commit message.

5. **Check for bead association** — Run `sase bead list --status=in_progress` to see if there's an in-progress bead
   related to your changes. If so, include `"bead_id": "<id>"` in the JSON payload (step 4). You do NOT need to manually
   close the bead or stage `.sase_beads/` — the commit workflow handles this automatically.

6. **Run the commit** — Execute:
   ```bash
   sase commit '<json_payload>'
   ```
   The `$SASE_COMMIT_METHOD` environment variable is read automatically to determine the dispatch method
   (`create_commit`, `create_proposal`, or `create_pull_request`). Do NOT pass `--method` unless you need to override.

## Example

```bash
sase commit '{"message": "feat: Add user authentication", "files": ["src/auth.py", "src/login.py"], "bead_id": "sase-42"}'
```

## Extra Requirements

- For `create_pull_request`, the payload should also include a `name` field for the branch name.
