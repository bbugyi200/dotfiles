---
name: sase_final
description:
  Submit the current turn's SASE finalizer declaration. Use this as the last action
  before every normal response that ends a SASE provider turn.
---

Use this skill whenever the current SASE turn is about to end with a normal response. It
is mandatory for final answers and incomplete-status responses; an unfinished turn still
declares so its work is committed. Never use it to wait for a command or to resume
later. Only a successfully executed plan, monitor, pipe, or questions handoff is exempt.

## Rules

- Never end a turn to wait for a command or promise to resume later. Nothing can wake
  you; hand long commands to `/sase_monitor` before starting them.
- Never submit a declaration while a command you started is still running. SASE stops
  the provider process shortly after your final declaration, killing anything still
  running — let the command finish and read its result first.
- Every repository you changed during this turn is yours to commit. This includes the
  primary workspace checkout and every linked, sidecar, or external repo you opened with
  `/sase_repo` and then edited. Give each one a `commit` decision; the only legal
  repository action is `commit`. A repository not being the main repo, not being the
  focus of the turn, or being outside a host prompt scoped to one repository's commit or
  conflict repair is not a reason to leave your own work uncommitted.
- Every dirty ACE or pager screenshot golden belongs in that repository's commit, even
  when the visible screenshot change appears unrelated to your authored source work.
  Inspect unrelated golden updates instead of silently discarding or deferring them. If
  they are genuinely unrelated, end the Conventional Commit message with the exact
  trailer `UNRELATED_SCREENSHOT_UPDATES=<reason>`, replacing `<reason>` with a concrete
  explanation. No trailer is required when the screenshot changes are part of the work
  described by the commit.
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

## Prepared Monitor Completion

`sase final prepare <manifest>` publishes a prepared host-completion intent reference
for monitor workflows. It does not submit a final declaration, commit, or end the turn.
Use it for final verification so passing work lands with no further turn.

1. Run `just fix` first so the verification monitor does not fail on avoidable
   formatting.
2. Get the host-issued context (`sase final context -f json`) and build one wrapper
   object from its `manifest_template`. The wrapper carries `success_message`, a
   `verification` command, and the `declaration`. The verification command may be an
   argv list or a shell string (see `src/sase/finalizers/prepare.py`); for the standard
   gate it is:

   ```json
   { "verification": { "command": ["just", "check"] } }
   ```

   When the assigned bead is done, set `bead_action: "close"` on the primary repository
   decision; use `"keep"` for intermediate work. See "Steps" below and
   `docs/monitors.md` ("Prepared host completion") for the full wrapper shape.

3. Publish the intent and keep the returned ref:

   ```bash
   sase final prepare <wrapper> -j
   ```

4. Bind the ref to the matching verification monitor:

   ```bash
   sase monitor start -p verify -f <ref> -r 'Verify before host completion' -- just check
   ```

The monitored argv must exactly match the intent's verification command or binding fails
and no monitor is created. The `verify` profile only supplies labels and evidence
defaults; the `-f/--completion` ref is what authorizes a successful monitor result to
hand completion back to the host. On green the host commits, closes the bead when
`bead_action` is `"close"`, and runs no successor. On red — a failed or timed-out
command, stale repository state, or another eligibility failure — the intent is
invalidated and one ordinary recovery successor launches instead.

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

   If the context has `assigned_bead` or the manifest template includes `bead_action`,
   every commit repository decision must replace the placeholder with `"keep"` or
   `"close"`. Use `"keep"` for intermediate commits, proposals, deferrals,
   linked/sidecar repositories, or any case where the assigned bead is not fully
   complete. Use `"close"` only for the primary repository decision after the whole
   assigned bead scope is complete and verified.

   Only add a typed `deferrals` entry when the repository tree itself must not be
   committed. Legal reasons are `protected_paths`, `foreign_work`, `unsafe_content`, and
   `belongs_to_another_turn`. Each deferral is an object in `payload.deferrals`
   alongside `payload.repositories`, and must name the affected `repo_id`, `reason`, and
   explicit `paths`. The host adjudicates every deferral at submit time and rejects one
   whose evidence points back to this turn's own work, naming the counter-evidence so
   you can repair the manifest and resubmit a commit. A deferral is a claim about
   authorship or safety, not a way to skip work. An upheld deferral leaves that
   repository's tree dirty on purpose and completes the run as `deferred`; someone has
   to finish the commit by hand afterward.

   When the turn has exactly one finalizer instance and one repository needing a
   decision, `sase final defer <repo-id> <reason>` submits that deferral for you instead
   of hand-writing the manifest. Anything wider still goes through `sase final submit`.

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
