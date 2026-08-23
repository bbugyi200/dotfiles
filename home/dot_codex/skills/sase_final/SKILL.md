---
name: sase_final
description:
  Submit the current turn's SASE finalizer declaration. Use this as the last action
  before every normal response that ends a SASE provider turn.
---

Use this skill whenever the current SASE turn is about to end with a normal response. It
is mandatory for final answers, incomplete-status responses, "I will wait" responses,
and replies that intend to resume in a later turn. Only a successfully executed plan,
monitor, pipe, or questions handoff is exempt.

## Rules

- Run this after all ordinary work, edits, and verification for the turn are complete,
  immediately before the normal response that ends the provider turn.
- Do not mutate files or repositories after a successful declaration submit.
- A `commit` action in the manifest is declarative: the host's `builtin@commit`
  finalizer runs `sase stitch create`. Do not invoke `/sase_git_commit` after reading a
  required final context.
- A `refuse` decision needs a substantive reason about the _changes_. Missing
  conversational context is not a valid reason. In a recovery turn, build the commit
  message from the host's evidence brief rather than assuming no work happened.
- If context says no payloads are required, return after reading it.
- If submit reports `stale_final_context`, rerun `sase final context -f json` and
  rebuild the manifest from the refreshed template, or abandon the manifest if the
  refreshed context no longer requires one.
- If submit reports other validation errors, repair the manifest and resubmit when
  possible.
- Successfully executed handoffs through plan, monitor, pipe, or questions terminate the
  runner mechanically and do not need this skill.

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

   Use only the `repo_id` values from the context. Do not submit absolute paths. A
   `commit` decision authorizes the host finalizer to commit; it is not an instruction
   to run any commit skill manually.

4. Submit the manifest:

   ```bash
   sase final submit <manifest-file>
   ```

   You may also pipe JSON with:

   ```bash
   sase final submit -
   ```

5. Treat a successful submit as the final action of the normal turn.
