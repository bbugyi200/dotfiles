---
name: sase_final
description:
  Submit the current turn's SASE finalizer declaration. Use this as the last normal
  action when beta finalizer instructions ask for `/sase_final`.
---

Use this skill only when the current SASE turn's instructions ask you to finish with
`/sase_final`.

## Rules

- Run this after all ordinary work, edits, and verification for the turn are complete.
- Do not mutate files or repositories after a successful declaration submit.
- If context says no payloads are required, return after reading it.
- If submit reports validation errors, repair the manifest and resubmit when possible.
- Intentional handoffs through plan, monitor, pipe, or questions terminate the runner
  mechanically and do not need this skill.

## Steps

1. Get the current host-issued context:

   ```bash
   sase final context -f json
   ```

2. If `submission_required` is false, stop here and return.

3. Build one manifest from `manifest_template`. For a `commit` payload, every repository
   in `context.obligations` with `kind: repository` needs exactly one decision:
   - `commit` with a valid Conventional Commit `message`, or
   - `refuse` with a nonblank `reason`.

   Use only the `repo_id` values from the context. Do not submit absolute paths.

4. Submit the manifest:

   ```bash
   sase final submit <manifest-file>
   ```

   You may also pipe JSON with:

   ```bash
   sase final submit -
   ```

5. Treat a successful submit as the final action of the normal turn.
