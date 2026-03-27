---
name: sase_hg_commit
description:
  Commit changes using sase commit for Mercurial/Google VCS. Invoked by the sase_commit_stop_hook when uncommitted
  changes are detected during a commit workflow. NEVER invoke this skill unless the user explicitly asks you to commit
  or a post-completion hook triggers it.
---

Commit changes via `sase commit`, which dispatches to the active VCS provider's commit hook.

This skill is used for Mercurial (hg) / Google-internal VCS workflows. It is typically invoked by the stop hook when
`$SASE_COMMIT_METHOD` is set and uncommitted changes are detected.

## Instructions

1. **Examine uncommitted changes** — Run `hg status` or `hg diff` to understand what files have changed and why.

2. **Determine the commit message** — Compose a descriptive message appropriate for the VCS operation:
   - For `create_commit`: Describe **only the changes you made in this commit** — not the overall CL or prior commits.
   - For `create_proposal`: Describes the proposal being created on the CL.
   - For `create_pull_request`: Describes the new CL being created.

3. **Write a commit message file** — Create a file (e.g., `commit_message.md`) containing the message composed in
   step 2. For `create_pull_request`, write a detailed description. For `create_commit`/`create_proposal`, a concise
   summary of **this commit's changes only** is sufficient. The first line becomes the COMMITS entry note.

4. **Check for bead association** — Run `sase bead list --status=in_progress` to see if there's an in-progress bead
   related to your changes. If so, include `--bead-id <id>` in the commit command (step 5). You do NOT need to manually
   close the bead — the commit workflow handles this automatically.

5. **Run the commit** — Execute:

   ```bash
   sase commit -m commit_message.md -f file1.py -f file2.py --bead-id <bead-id>
   ```

   Flags:
   - `-m`: Path to file containing the commit message (required). The file is deleted after reading.
   - `-f`: File to include (repeat for multiple files). Omit to include all changes.
   - `--bead-id`: Include if there's an in-progress bead for your changes.
   - `--name`: CL name (only needed for `create_pull_request` method).

   The `$SASE_COMMIT_METHOD` environment variable is read automatically to determine the dispatch method
   (`create_commit`, `create_proposal`, or `create_pull_request`). Do NOT pass `--method` unless you need to override.

## Example

```bash
sase commit -m commit_message.md -f auth.py -f login.py --bead-id sase-42
```

## Notes

- The VCS provider plugin handles the actual hg operations (amend, upload, mail, etc.).
- For `create_pull_request`, the payload should also include a `name` field for the CL name.
- The `precommit_command` (configured in `sase.yml`) runs automatically before commit — no manual formatting step
  needed.
- If `SASE_PLAN` is set, the plan path is appended to the commit message and the plan is marked as done automatically.
