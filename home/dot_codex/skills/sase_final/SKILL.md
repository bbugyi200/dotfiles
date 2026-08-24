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

- Every repository you changed during this turn is yours to commit. This includes the
  primary workspace checkout and every linked, sidecar, or external repo you opened with
  `/sase_repo` and then edited. Give each one a `commit` decision; `action: "commit"` is
  the only legal repository action. A repository not being the main repo, not being the
  focus of the turn, or being outside a host prompt scoped to one repository's commit is
  not a reason to leave your own work uncommitted.
- Run this after all ordinary work, edits, and verification for the turn are complete,
  immediately before the normal response that ends the provider turn.
- Do not mutate files or repositories after a successful declaration submit.
- A `commit` action in the manifest is declarative: the host's `builtin@commit`
  finalizer runs `sase stitch create`. Do not invoke `/sase_git_commit` after reading a
  required final context.
- SASE agents work in ephemeral numbered workspace clones, so uncommitted work is lost
  work. The host commits your turn's work by default and does not need the user to ask.
  Deferral is a safety valve for a tree that must not be committed, not the polite
  default.
- In a recovery turn, build the commit message from the host's evidence brief rather
  than assuming no work happened.
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
   in `context.obligations` with `kind: repository` needs exactly one repository
   decision, and the only legal `action` is `commit` with a valid Conventional Commit
   `message`.

   Use only the `repo_id` values from the context. Do not submit absolute paths. Keep
   `action: "commit"` and write a message that describes the work in that repository. A
   `commit` decision authorizes the host finalizer to commit; it is not an instruction
   to run any commit skill manually.

   Read the `commit_declaration` object in the context when present. Its
   `repository_evidence` lists model-visible provenance for the dirty paths: paths
   written by this run, paths already dirty at run start, and protected paths.

   Only add a typed `deferrals` entry when the repository tree itself must not be
   committed. Legal reasons are `protected_paths`, `foreign_work`, `unsafe_content`, and
   `belongs_to_another_turn`. Each deferral is an object in `payload.deferrals`
   alongside `payload.repositories`, and must name the affected `repo_id`, `reason`, and
   explicit `paths`. The host adjudicates deferrals at submit time using
   `src/sase/finalizers/declaration_deferrals.py` and rejects deferrals whose evidence
   points back to this turn's own work. A deferral is a claim about authorship or
   safety, not a way to skip work.

   If `finalizer_baseline.json` shows a repository with empty `fingerprints`, nothing
   was dirty when it was opened, so every dirty path in that repository is your own
   work. Commit it. Do not read a sparse or empty baseline as permission to skip.

4. Submit the manifest:

   ```bash
   sase final submit <manifest-file>
   ```

   You may also pipe JSON with:

   ```bash
   sase final submit -
   ```

5. Treat a successful submit as the final action of the normal turn.
