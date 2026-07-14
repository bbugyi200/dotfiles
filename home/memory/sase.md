---
type: short
parent: AGENTS.md
---

# SASE = Structured Agentic Software Engineering

## Repositories

Configured linked repositories for this context:

- `chezmoi`: Chezmoi-managed dotfiles and global SASE configuration source. Use `sase repo open` to access a private
  linked workspace when running from a numbered host workspace.

When you need to read or modify files in any repository other than your own workspace checkout, agents MUST use your
`/sase_repo` skill first. This includes configured linked repos and sidecars, another SASE project's repo, and any
GitHub repo not linked to the current project. Open different-project and unlinked GitHub repos as external repos
through the skill. Use the path it prints as the only path for reads and writes.

IMPORTANT REMINDER: Do NOT locate or clone another repo any other way than by using `/sase_repo`!
