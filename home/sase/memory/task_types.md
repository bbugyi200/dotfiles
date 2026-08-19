---
type: short
parent: AGENTS.md
---

# Task Bead Types

Every task bead can carry a `task_type` drawn from this project's catalog.
`sase bead task-type list` always shows the live catalog and
`sase bead task-type show <slug>` shows one type in full; this note is the generated,
always-current snapshot of the agent-creatable types below.

## Types

### `bug` — Bug

File one when you found a defect while doing unrelated work and it is not an external
tracker issue. Record where it lives, how to reproduce it, and who it hurts. Do not use
this for a flake, a confirmed CI failure, or a GitHub-mirrored bug.

- Required fields: `location`, `repro`
- Optional fields: `impact`

Run `sase bead task-type show bug` for the full field list, validators, and body
template.

### `ci` — CI failure

File one when a test or lint failed and you confirmed it is a true failure, not a flake.
Record the pytest node ID, the failing SHA if known, and why this is not intermittent.
Use flake instead when a rerun on the same tree passed.

- Required fields: `node_id`, `why_not_flake`
- Optional fields: `sha`

Run `sase bead task-type show ci` for the full field list, validators, and body
template.

### `flake` — Flaky test

File one when a test or lint failed, a rerun on the same tree passed, and you did not
cause the failure. Record the fail rate and whether it reproduces serially. Use ci
instead when the failure is confirmed and reproducible.

- Required fields: `node_id`, `evidence`
- Optional fields: `repro_cmd`

Run `sase bead task-type show flake` for the full field list, validators, and body
template.

### `memory` — Memory

File one when a sase memory file or skill contains out-of-date information that should
be updated. Closing still requires explicit user permission plus `sase memory init`.
Record the memory path and the proposed change.

- Required fields: `path`, `proposed_change`

Run `sase bead task-type show memory` for the full field list, validators, and body
template.

## File Discovered Work As Task Beads

Unless your prompt explicitly forbids creating beads (epic phase workers, for example,
must record `PROPOSED FOLLOW-UP:` notes on their own bead instead), you can and SHOULD
capture discovered follow-up work as sase task beads. Pick the type above whose
`when_to_use` matches what you found:

- A linter or test is flaky or failing and you did not cause it: file a task bead
  instead of ignoring the failure.
- A sase memory file or skill contains out-of-date information that should be updated:
  file a task bead proposing the update.
- A tool, command, or script this project is responsible for has a bug or a clear,
  objective improvement that would help future agents: file a task bead to fix or
  improve it.

Before creating any task bead, you MUST use `/sase_new_task`. That skill checks every
task status for semantic duplicates, checks in-progress epics for a credible causal
link, and records the issue in the right place. Only a genuinely new task becomes an
`open` draft, and every new task requires an intentional `--size` plus
`-T "task(<slug>)"` and `-f/--field` values for that type's required fields. Ready task
beads are proposed to the project owner, who either launches an agent to work them or
closes them with a reason.
