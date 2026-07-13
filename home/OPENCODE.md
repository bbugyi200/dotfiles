# athena - Bryan Bugyi's Home Server

IMPORTANT: You should not modify any of these memory files without approval from the user.

## Tier 1 (short-term) Memory

The following memories contains core (always loaded) context:

### 1. SASE = Structured Agentic Software Engineering (sase)

#### Linked Repositories

Configured linked repositories for this context:

- `chezmoi`: Chezmoi-managed dotfiles and global SASE configuration source. Use `sase repo open` to access a private
  linked workspace when running from a numbered host workspace.

When you need to make changes to files in a numbered-workspace linked repo or need to review numbered-workspace linked
repo code, agents MUST run:

```bash
sase repo open <linked_repo> -r "<reason>"
```

Run it from your workspace directory (the workspace number is inferred from where you run it; pass `-w <workspace_num>`
only when running from outside the workspace). Use the path printed by `sase repo open` as the only linked repo path for
numbered-workspace linked reads/writes.

IMPORTANT REMINDER: Do NOT attempt to look for a linked repo in any other way than by using `sase repo open`!

## Tier 2 (long-term) Memory

The below files contain detailed reference material. When working in their domain, you MUST use your `/sase_memory_read`
skill to review their contents. Do not read canonical memory files directly.

**`memory/obsidian.md`**  
Obsidian vault, notes workflow, and obsidian-headless/ob usage.
