---
name: sase_plan
description: Create an implementation plan. Use instead of plan mode (which is disabled). Only available inside sase.
---

# /sase_plan - Create an Implementation Plan

Use this skill when you need to plan before implementing. This replaces Claude's native plan mode, which is disabled.

**IMPORTANT**: Only available when running inside sase (via `sase ace` TUI or `sase run`).

## How It Works

When you use this skill, the current claude instance will be **terminated** and a NEW "coder" agent will be spawned with
ONLY your plan file as context. The coder will not have your conversation history, exploration notes, or any other
context -- only the plan file.

## Instructions

1. **Explore and understand** the problem thoroughly.

2. **Write a self-contained plan** to `sase_plan_<name>.md` (descriptive underscore name). The plan MUST include:
   - All relevant file paths (absolute)
   - Key code snippets the implementer needs
   - Architectural context and design decisions
   - Step-by-step implementation instructions
   - Edge cases and gotchas

3. **Submit the plan**:
   ```bash
   .venv/bin/sase plan sase_plan_<name>.md
   ```

## Critical Rules

- Plan must be COMPLETELY self-contained (no "as discussed above")
- Include actual code snippets, not just descriptions
- Write the plan file to the current working directory
- Always use `.venv/bin/sase plan`, never bare `sase plan`
