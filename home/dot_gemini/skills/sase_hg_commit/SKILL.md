---
name: sase_hg_commit
description: |
  Commit changes using sase commit for Google's fig VCS. This skill is the ONLY way that you should EVER commit to fig
  repos. NEVER invoke this skill unless the user explicitly asks you to commit or a post-completion hook triggers it.
---

Commit changes via the `sase commit` command.

## Instructions

1. **Examine uncommitted changes** — Run `hg status` or `hg diff` to understand what files have changed and why.

2. **Write a commit message file** — Create a file (e.g., `commit_message.md`) containing a good commit message.

3. **Check for bead association** — Run `sase bead list --status=in_progress` to see if there's an in-progress bead
   related to your changes. If so, include `--bead-id <id>` in the commit command (step 5). You do NOT need to manually
   close the bead — the commit workflow handles this automatically.

4. **Run the commit** — Execute:

   ```bash
   sase commit -M commit_message.md -f file1.py -f file2.py --bead-id <bead-id>
   ```

   Flags:
   - `-M`: Path to file containing the commit message. The file is deleted after reading.
   - `-m`: Inline commit message string (alternative to `-M`). `-m` and `-M` are mutually exclusive.
   - `-f`: File to include (repeat for multiple files). Omit to include all changes.
   - `--bead-id`: Include if there's an in-progress bead for your changes.
   - `--name`: CL name (only needed for `create_pull_request` method).
   - `-p`/`--parent`: Parent ChangeSpec name (overrides auto-detection from current branch).

   The `$SASE_COMMIT_METHOD` environment variable is read automatically to determine the dispatch method
   (`create_commit`, `create_proposal`, or `create_pull_request`). Do NOT pass `--type` unless you need to override.

## Example

```bash
sase commit -M commit_message.md -f auth.py -f login.py --bead-id sase-42
```
