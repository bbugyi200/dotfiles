---
name: sase_plan
description: Create an implementation plan. Use instead of plan mode (which is disabled).
---

Use this skill when you need to plan before implementing. This replaces Codex's native plan mode, which is disabled.

## Instructions

1. **Explore and understand** the problem thoroughly.

2. **Choose the plan tier** before writing:
   - Use `tale` for work that one follow-up coding agent can implement as a single plan.
   - Use `epic` when the work should be split into phases that distinct agents can complete. Declare every phase
     dependency explicitly (so we can support parallel work if needed/desirable). Every phase in an epic plan file MUST
     have a unique slug ID.

3. **Write a self-contained plan** to `sase_plan_<name>.md` (descriptive underscore name).
   - The file must start at byte 0 with valid YAML frontmatter that contains a single `tier: <tier>` property, where
     `<tier>` is either `tale` or `epic`.

4. **Validate (with `--explain`), edit, and revalidate (without `--explain`)**:

   The first validation run with `--explain` prints the expected schema and all diagnostics. Use that information to
   edit the plan file. Then rerun validation without `--explain` to check that the file is now valid. Continue until
   validation exits successfully. Do not propose a plan that has not passed validation.

   ```bash
   sase plan validate sase_plan_<name>.md --explain
   # ... edit the file to fix all reported issues ...
   sase plan validate sase_plan_<name>.md
   # ... repeat until validation exits successfully ...
   ```

5. **Submit the validated plan**:

   ```bash
   sase plan propose sase_plan_<name>.md
   ```

   Submission consumes the scratch plan into SASE's durable plan archive, writes a handoff marker, and sends `SIGTERM`
   to the current agent runner process group. The runner treats that signal as an intentional handoff: it creates the
   tier-specific `PlanApproval` or `EpicApproval` gate, waits mechanically for a terminal response, and continues with
   feedback or the approved follow-up. Do not expect the current provider turn to return normally after a successful
   proposal, and do not poll response files yourself.
