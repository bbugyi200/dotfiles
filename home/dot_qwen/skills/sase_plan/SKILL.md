---
name: sase_plan
description: Create an implementation plan. Use instead of plan mode (which is disabled).
---

Use this skill when you need to plan before implementing. This replaces Qwen's native plan mode, which is disabled.

## Instructions

1. **Explore and understand** the problem thoroughly.

2. **Choose the plan tier** before writing:
   - Use `tale` for work that one follow-up coding agent can implement as a single plan.
   - Use `epic` when the work should be split into ordered phases that distinct agents can complete. Declare every
     dependency explicitly; use `depends_on: []` for a phase with no dependencies.

3. **Write a self-contained plan** to `sase_plan_<name>.md` (descriptive underscore name).
   - You should construct the same type of implementation plan that you would have written in Qwen's native plan mode.
   - Be ambitious about scope, but stay focused on product context and high-level technical design rather than detailed
     technical implementation.
   - The file must start at byte 0 with valid YAML frontmatter and have a non-empty Markdown body.

   A tale requires this frontmatter shape:

   ```yaml
   ---
   tier: tale
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
     - id: cli
       title: sase workspace gc command
       depends_on: [core]
     - id: smoke
       title: End-to-end GC smoke exercises
       depends_on: [cli]
       model: haiku
   ---
   # Plan: Workspace GC rewrite

   Describe the context, design, phase goals, testing, and risks.
   ```

   Phase IDs must be unique slugs. Dependencies may only name earlier-listed phases; do not use self, duplicate,
   unknown, or forward references. A phase's `description` and `model` are optional. Only set a phase `model` when the
   user's prompt requested a specific model, or when that phase's agent does not do real consequential work (for
   example, a phase that exercises or tests the feature itself). Otherwise omit it so the configured `@phase_worker`
   role alias applies. The optional top-level `model` selects the tale's coder follow-up or the epic's land agent.

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
