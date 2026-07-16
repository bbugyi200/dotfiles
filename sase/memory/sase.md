---
type: short
parent: AGENTS.md
---

# SASE = Structured Agentic Software Engineering

## Ephemeral `dotfiles_<N>` Workspace Directories

SASE runs agents (like you) from ephemeral workspace directories, which are full clones of the dotfiles repo. These
directories are named `dotfiles_<N>` where `<N>` is some integer. You need to be mindful not to run commands outside of
these workspace directories, since they have their own isolated virtual environments.

IMPORTANT: Do NOT mention your workspace directory (or any sibling workspace directory) in any plan files that you
generate using your `/sase_plan` skill. The agent(s) that implement the plan might not run in the same workspace
directory as you!

## Repositories

No linked repositories are configured for this context.

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
