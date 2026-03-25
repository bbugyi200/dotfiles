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

3. **Construct the JSON payload** — Build a JSON object with these fields:

   ```json
   {
     "message": "<description>",
     "files": ["file1.py", "file2.py"],
     "note": "optional COMMITS note",
     "bead_id": "sase-42"
   }
   ```

   - `message`: The commit/CL description.
   - `files`: List of files to include. If empty, all changes are included.
   - `note`: Optional note for COMMITS entry (used by `create_commit`).
   - `bead_id`: (optional) If there's an in-progress bead related to your changes, include its ID here. The workflow
     will automatically close the bead and append the bead ID to the commit message.

4. **Check for bead association** — Run `sase bead list --status=in_progress` to see if there's an in-progress bead
   related to your changes. If so, include `"bead_id": "<id>"` in the JSON payload (step 3). You do NOT need to manually
   close the bead — the commit workflow handles this automatically.

5. **Run the commit** — Execute:
   ```bash
   sase commit '<json_payload>'
   ```
   The `$SASE_COMMIT_METHOD` environment variable is read automatically to determine the dispatch method
   (`create_commit`, `create_proposal`, or `create_pull_request`). Do NOT pass `--method` unless you need to override.

## Example

```bash
sase commit '{"message": "Add user authentication", "files": ["auth.py", "login.py"], "note": "Added login/logout flow", "bead_id": "sase-42"}'
```

## Extra Requirements

- For `create_pull_request`, the payload should also include a `name` field for the CL name.
