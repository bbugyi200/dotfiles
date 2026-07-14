# athena - Bryan Bugyi's Home Server

IMPORTANT: You should not modify any of these memory files without approval from the user.

## Tier 1 (short-term) Memory

The following memories contains core (always loaded) context:

### 1. SASE = Structured Agentic Software Engineering (sase)

#### Repositories

Configured linked repositories for this context:

- `chezmoi`: Chezmoi-managed dotfiles and global SASE configuration source. Use `sase repo open` to access a private
  linked workspace when running from a numbered host workspace.

When you need to read or modify files in any repository other than your own workspace checkout, agents MUST use your
`/sase_repo` skill first. This includes configured linked repos and sidecars, another SASE project's repo, and any
GitHub repo not linked to the current project. Open different-project and unlinked GitHub repos as external repos
through the skill. Use the path it prints as the only path for reads and writes.

IMPORTANT REMINDER: Do NOT locate or clone another repo any other way than by using `/sase_repo`!

## Tier 2 (long-term) Memory

The below files contain detailed reference material. When working in their domain, you MUST use your `/sase_memory_read`
skill to review their contents. Do not read canonical memory files directly.

**`memory/obsidian.md`**  
Obsidian vault, notes workflow, and obsidian-headless/ob usage.
