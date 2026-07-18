# athena - Bryan Bugyi's Home Server

IMPORTANT: You should not modify any of these memory files without approval from the user. However, when the user
explicitly asks you to update a SASE memory file, that request already carries the required approval for the full
workflow: make the requested edit to the canonical note under `sase/memory/`, then you MUST run `sase memory init` to
regenerate `AGENTS.md`, the provider instruction shims, and the memory README. Do NOT ask for separate permission to
initialize sase memory in that case.

## Tier 1 (short-term) Memory

The following memories contains core (always loaded) context:

### 1. SASE = Structured Agentic Software Engineering (sase)

#### Repositories

Configured linked and sidecar repositories for this context:

- `chezmoi`: Chezmoi-managed dotfiles and global SASE configuration source. Use `sase repo open` to access a private
  linked workspace when running from a numbered host workspace.

When you need to read or modify files in any repository other than your own workspace checkout, agents MUST use your
`/sase_repo` skill first. This includes configured linked repos and sidecars, another SASE project's repo, and any
GitHub repo not linked to the current project. Open different-project and unlinked GitHub repos as external repos
through the skill. Use the path it prints as the only path for reads and writes.

This rule applies regardless of transport. Fetching a repository's files or history over the web — github.com
file/blob/raw URLs, raw.githubusercontent.com, repo tarballs, or GitHub-API/`gh` file-content reads — counts as reading
that repo: open it with `/sase_repo` (unlinked GitHub repos open as external repos, e.g. `gh:<owner>/<repo>`) and read
the local checkout instead. Web tools remain appropriate only for content a checkout does not contain, such as blog
posts, docs sites, and GitHub issue/PR discussions.

IMPORTANT REMINDER: Do NOT locate, clone, or web-fetch another repo's contents any other way than by using `/sase_repo`!

## Tier 2 (long-term) Memory

The below files contain detailed reference material. When working in their domain, you MUST use your `/sase_memory_read`
skill to review their contents. Do not read canonical memory files directly.

**`sase/memory/obsidian.md`**  
Obsidian vault, notes workflow, and obsidian-headless/ob usage.
