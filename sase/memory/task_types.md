---
web: true
roster: list
strand_noun: task type
---

# Task Bead Types

Every task bead can carry a `task_type` drawn from this project's catalog.
`sase bead task-type list` always shows the live catalog; read
`sase memory read task_types:<slug> -r "<why>"` for one generated type in full. This
note is the generated, always-current snapshot of the agent-creatable types below.

<!-- sase:strands -->

1. **Bug** (`bug`) - A defect an agent found while doing unrelated work, not an external
   tracker bug.
2. **CI failure** (`ci`) - A confirmed true test or lint failure you did not cause, not
   a flake.
3. **Feature** (`feature`) - An out-of-scope product or tooling idea that should not
   become a wish list.
4. **Flaky test** (`flake`) - A test that fails and then passes on an unchanged tree.
5. **Memory** (`memory`) - A sase memory note or skill that is out of date.

<!-- /sase:strands -->

## File Discovered Work As Task Beads

Unless your prompt explicitly forbids creating beads (epic phase workers, for example,
must record `PROPOSED FOLLOW-UP:` notes on their own bead instead), you can and SHOULD
capture discovered follow-up work as sase task beads. Before creating any task bead, you
MUST use `/sase_new_task`.
