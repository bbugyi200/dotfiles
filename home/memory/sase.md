---
type: short
parent: AGENTS.md
---

# SASE = Structured Agentic Software Engineering

## Linked Repositories

Configured linked repositories for this context:

- `chezmoi`: Chezmoi-managed dotfiles and global SASE configuration source. Use `sase workspace open` to access a
  private linked workspace when running from a numbered host workspace.

When you need to make changes to files in a numbered-workspace linked repo or need to review numbered-workspace linked
repo code, agents MUST run:

```bash
sase workspace open -p <linked_repo> -r "<reason>" <workspace_num>
```

`<workspace_num>` must be the workspace number assigned to the primary repo (check what directory you were started in to
figure this out). Use the path printed by `sase workspace open` as the only linked repo path for numbered-workspace
linked reads/writes.

IMPORTANT REMINDER: Do NOT attempt to look for a linked repo in any other way than by using `sase workspace open`!
