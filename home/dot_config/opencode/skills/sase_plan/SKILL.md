---
name: sase_plan
description: Create an implementation plan. Use instead of plan mode (which is disabled).
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skills log sase_plan --reason "<one-line reason for using this skill>"
```

Use this skill when you need to plan before implementing. This replaces OpenCode's native plan mode, which is disabled.

## Instructions

1. **Explore and understand** the problem thoroughly.

2. **Write a self-contained plan** to `sase_plan_<name>.md` (descriptive underscore name).
   - You should construct the same type of implementation plan that you would have written in OpenCode's native plan
     mode.
   - Be ambitious about scope, but stay focused on product context and high-level technical design rather than detailed
     technical implementation.

3. **Submit the plan**:
   ```bash
   sase plan propose sase_plan_<name>.md
   ```
