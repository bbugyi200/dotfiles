---
name: sase_hg_commit
description: |
  Commit changes using sase commit for Google's fig VCS. This skill is the ONLY way that you should EVER commit to fig
  repos.
---

Commit changes via the `sase commit` command.

## Instructions

1. **Examine uncommitted changes** — Run `hg status` or `hg diff` to understand what files have changed and why.

2. **Determine the commit message** — Compose a descriptive message appropriate for the VCS operation:
   - For `create_commit`: Describes what changed (amends the current CL with a COMMITS entry).
   - For `create_proposal`: Describes the proposal being created on the CL.
   - For `create_pull_request`: Describes the new CL being created.

3. **Check for bead association** — Run `sase bead list --status=in_progress` to see if there's an in-progress bead
   related to your changes. If so, include `--bead-id <id>` in the commit command (step 4). You do NOT need to manually
   close the bead — the commit workflow handles this automatically.

4. **Run the commit** — Execute:
   ```bash
   sase commit -m "<description>" -f file1.py -f file2.py --bead-id <bead-id>
   ```

   Flags:
   - `-m`: Commit/CL description (required). Use quotes for messages with spaces.
   - `-f`: File to include (repeat for multiple files). Omit to include all changes.
   - `--bead-id`: Include if there's an in-progress bead for your changes.
   - `--name`: CL name (only needed for `create_pull_request` method).
   - `--note`: Optional note for COMMITS entry (used by `create_commit`).

   The `$SASE_COMMIT_METHOD` environment variable is read automatically to determine the dispatch method
   (`create_commit`, `create_proposal`, or `create_pull_request`). Do NOT pass `--method` unless you need to override.

## Example

```bash
sase commit -m "Add user authentication" -f auth.py -f login.py --note "Added login/logout flow" --bead-id sase-42
```
