---
name: sase_repo
description: >-
  Work with repos through `sase repo` (list, open, log). MUST be used to open any repo other than your own workspace
  checkout before reading or modifying its files: linked repos, sidecars, other SASE projects, or any GitHub repo not
  linked to the current project (opened on demand as an external repo).
---

Use this skill before reading or modifying files in any repository other than your own workspace checkout.

## Open A Repository

Run `sase repo open` from your workspace directory with a specific audit reason. It resolves references in three tiers:

```bash
# A repository in the current project's inventory (linked repo, sidecar, or primary)
sase repo open sase-github -r "Review the workspace-provider implementation"

# Another registered SASE project's primary repository
sase repo open dotdrop -r "Port the launcher fix requested by the user"

# A GitHub repository not linked to the current project
sase repo open gh:pallets/click -r "Study upstream option parsing"
```

Bare `owner/repo` is shorthand for `gh:owner/repo`.

The command prints the prepared path to stdout. Use that printed path as the only path for subsequent reads and writes.
Never locate or clone a linked repo, sidecar, different SASE project, or unlinked GitHub repo another way. Pass
`-w <workspace_num>` only when running outside the workspace whose repo clone you need.

## Inspect Repositories

- `sase repo list` shows the current project's primary, sidecar, linked, and opened external repositories. Add `--json`
  for machine-readable inventory data or `--all` for every registered project.
- `sase repo log` shows the durable repository-open audit trail. Filter with `--repo`, `--agent`, `--workspace`, or
  `--id`; add `--json` for machine-readable output.
