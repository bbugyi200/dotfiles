# Agent Instructions

### 1. SASE = Structured Agentic Software Engineering (sase)

#### Ephemeral `dotfiles_<N>` Workspace Directories

SASE runs agents (like you) from ephemeral workspace directories, which are full clones of the dotfiles repo. These
directories are named `dotfiles_<N>` where `<N>` is some integer. You need to be mindful not to run commands outside of
these workspace directories, since they have their own isolated virtual environments.

IMPORTANT: Do NOT mention your workspace directory (or any sibling workspace directory) in any plan files that you
generate using your `/sase_plan` skill. The agent(s) that implement the plan might not run in the same workspace
directory as you!

#### Linked Repositories

No linked repositories are configured for this context.
