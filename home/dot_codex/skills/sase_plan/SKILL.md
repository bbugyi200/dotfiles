---
name: sase_plan
description:
  Create an implementation plan. Use instead of plan mode (which is disabled).
---

Use this skill when you need to plan before implementing. This replaces Codex's native
plan mode, which is disabled.

SASE derives your plan's links from the artifacts you read this turn; use
`sase artifact read` for context you actually used.

## Instructions

1. **Explore and understand** the problem thoroughly. Before choosing a plan or phase
   size, read the canonical SASE size guidance:

   ```bash
   sase memory read sase_sizes.md --reason "Need SASE size guidance before authoring a plan"
   ```

2. **Choose the plan tier** before writing:
   - Use `tale` for work that one follow-up coding agent can implement as a single plan.
   - Use `epic` when the work should be split into phases that distinct agents can
     complete. Declare every phase dependency explicitly (so we can support parallel
     work if needed/desirable). Every phase in an epic plan file MUST have a unique slug
     ID.
   - Authoring a tale plan is `large` work; authoring an epic plan is `xlarge` work.

3. **Write a self-contained plan** to `sase_plan_<name>.md` (descriptive underscore
   name).
   - The file must start at byte 0 with valid YAML frontmatter that contains a single
     `tier: <tier>` property, where `<tier>` is either `tale` or `epic`.
   - Tale frontmatter must declare `size: xsmall | small | medium`.
   - Epic frontmatter must omit top-level `size`; each epic phase declares its own
     `size`.

4. **Plan Decisions**: embed reviewer choices instead of asking now when you can. Ask
   now with `/sase_questions` only when the answer changes the tier, size, phase graph,
   or architecture. Embed a `decisions:` frontmatter entry when you can write one
   complete plan that covers every answer, the difference each answer makes is local,
   and you would defend your default. Never embed a decision you should make yourself.
   Prefer decisions over questions whenever that does not degrade the plan.

   ```yaml
   decisions:
     grouping:
       ask: How should the overlay group bindings?
       choices:
         pane: By pane, matching the footer hints
         mode: By leader mode; denser, but splits pane actions
       default: pane
       why: pane keeps the footer's order
   ```

   Use readable ids. Phrase `ask` as a question where yes means do the work. State
   consequences in choice labels. Do not restate the choice key, or a `Yes:`/`No:`
   prefix, at the start of its label; the label states the consequence. Add a one-line
   `why` for the default. Order decisions by importance with memory decisions last. If
   the planned work would leave a memory note stating something false, plan that
   correction too, under a memory decision authored with your `/sase_memory_write`
   skill. Add `> [!decision] <id> = <key>` callouts when branches differ by more than a
   sentence. Inside an epic phase, do not re-ask the epic's DECISIONS; `sase bead read`
   shows them as final.

5. **Validate (with `--explain`), edit, and revalidate (without `--explain`)**:

   The first validation run with `--explain` prints the expected schema and all
   diagnostics. Use that information to edit the plan file. Then rerun validation
   without `--explain` to check that the file is now valid. Continue until validation
   exits successfully. Do not propose a plan that has not passed validation.

   ```bash
   sase plan validate sase_plan_<name>.md --explain
   # ... edit the file to fix all reported issues ...
   sase plan validate sase_plan_<name>.md
   # ... repeat until validation exits successfully ...
   ```

6. **Submit the validated plan**:

   ```bash
   sase plan propose sase_plan_<name>.md
   ```

   If the command reports **Staged**, it archived the proposal and staged approval for
   host completion. Nothing starts until your turn ends: finish through `/sase_final`,
   submitting only when its context says a declaration is required. Stage before you
   declare, do not mutate files after a successful declaration, and never wait for your
   own staged proposal. Otherwise the legacy command has ended your turn mechanically;
   the runner creates the tier-specific `PlanApproval` or `EpicApproval` gate turn,
   which owns review settlement and launches the feedback replanner or approved tale
   coder. Do not poll response files yourself.
