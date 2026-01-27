---
name: fix_hook
input:
  - name: hook_command
    type: string
  - name: output_file
    type: string
---

The command "{{ hook_command }}" is failing. The output of the last run can be found in the @{{ output_file }} file. Can
you help me fix this command by making the appropriate file changes? Verify that your fix worked when you are done by
re-running that command.

IMPORTANT: Do NOT commit or amend any changes. Only make file edits and leave them uncommitted.
