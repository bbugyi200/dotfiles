---
type: core
parent: AGENTS.md
---

# Chezmoi Apply After Commit

After making any commits to this repository (including after a SASE finalizer lands a
commit) you MUST run `chezmoi update -a --force` to apply the source tree to the home
directory.

See https://github.com/twpayne/chezmoi and https://www.chezmoi.io/ for chezmoi
documentation.
