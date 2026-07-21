---
name: sase_plan
description: Create an implementation plan. Use instead of plan mode (which is disabled).
---

Use this skill when you need to plan before implementing. This replaces Codex's native plan mode, which is disabled.

## Instructions

1. **Explore and understand** the problem thoroughly.

2. **Choose the plan tier** before writing:
   - Use `tale` for work that one follow-up coding agent can implement as a single plan.
   - Use `epic` when the work should be split into ordered phases that distinct agents can complete. Declare every
     dependency explicitly; use `depends_on: []` for a phase with no dependencies.

3. **Write a self-contained plan** to `sase_plan_<name>.md` (descriptive underscore name).
   - You should construct the same type of implementation plan that you would have written in Codex's native plan mode.
   - Be ambitious about scope, but stay focused on product context and high-level technical design rather than detailed
     technical implementation.
   - The file must start at byte 0 with valid YAML frontmatter and have a non-empty Markdown body.

   Both tiers require a non-empty frontmatter `title`. A tale requires this frontmatter shape:

   ```yaml
   ---
   tier: tale
   title: Focused capability rollout
   goal: Describe the outcome this plan will achieve.
   ---
   # Plan: Descriptive title

   Describe the implementation.
   ```

   An epic requires a title and a non-empty ordered phase list:

   ```yaml
   ---
   tier: epic
   title: Workspace GC rewrite
   goal: >
     Stale workspace checkouts are garbage-collected safely, and reclaim progress is visible.
   phases:
     - id: core
       title: GC planner and safety checks
       depends_on: []
       size: medium
       description: "'GC planner and safety checks' section: implement workspace selection and safety guards."
     - id: cli
       title: sase workspace gc command
       depends_on: [core]
       size: small
       description: "'sase workspace gc command' section: add the CLI flow and progress reporting."
     - id: smoke
       title: End-to-end GC smoke exercises
       depends_on: [cli]
       size: small
       description: "'End-to-end GC smoke exercises' section: exercise successful and guarded cleanup."
       model: haiku
   ---
   # Plan: Workspace GC rewrite

   Describe the context, design, phase goals, testing, and risks.
   ```

   Phase IDs must be unique slugs. Dependencies may only name earlier-listed phases; do not use self, duplicate,
   unknown, or forward references. Give every phase a `description` that names its section in the plan body and briefly
   summarizes that section; do not reference the plan file itself because `sase bead show` already displays it. Every
   phase must declare `size: small | medium | large`. Use `medium` when the phase is potentially a lot of work and
   justifies its own plan file. Use `large` when you suspect that plan file would itself be large enough to merit an
   epic tier. Use `small` otherwise. Medium and large phase agents plan before implementation. A phase with no explicit
   model routes through the alias matching its size: `@small_phase_worker`, `@medium_phase_worker`, or
   `@large_phase_worker`. Each size alias falls back to the shared `@phase_worker` alias.

   A phase's `model` is optional. Only set it when the user's prompt requested a specific model, or when that phase's
   agent does not do real consequential work (for example, a phase that exercises or tests the feature itself). An
   explicit phase model always wins over size-derived routing. `@smartest` remains available for explicit use but is not
   selected automatically. The optional top-level `model` selects the tale's coder follow-up or the epic's land agent.

4. **Validate, edit, and revalidate** with the same tier authored in the file:

   ```bash
   sase plan validate sase_plan_<name>.md --tier tale
   # or: sase plan validate sase_plan_<name>.md --tier epic
   ```

   If validation fails, use all reported diagnostics and the printed expected schema to edit the file, then rerun the
   command. Continue until validation exits successfully. Do not propose a plan that has not passed validation.

5. **Submit the validated plan**:

   ```bash
   sase plan propose sase_plan_<name>.md
   ```

   Submission consumes the scratch plan into SASE's durable plan archive, writes a handoff marker, and sends `SIGTERM`
   to the current agent runner process group. The runner treats that signal as an intentional handoff: it creates the
   tier-specific `PlanApproval` or `EpicApproval` gate, waits mechanically for a terminal response, and continues with
   feedback or the approved follow-up. Do not expect the current provider turn to return normally after a successful
   proposal, and do not poll response files yourself.
