---
name: sase_plan
description: Create an implementation plan. Use instead of plan mode (which is disabled).
---

Use this skill when you need to plan before implementing. This replaces Claude's native plan mode, which is
disabled.

## Instructions

1. **Explore and understand** the problem thoroughly.

2. **Write a self-contained plan** to `sase_plan_<name>.md` (descriptive underscore name).
   - You should construct the same type of implementation plan that you would have written in Claude's
     native plan mode.
   - Be ambitious about scope, but stay focused on product context and high-level technical design rather than detailed
     technical implementation.

3. **Submit the plan**:
   ```bash
   sase plan sase_plan_<name>.md
   ```
