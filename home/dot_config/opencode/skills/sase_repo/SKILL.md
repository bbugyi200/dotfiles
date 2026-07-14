---
name: sase_repo
description: >-
  Work with repos through `sase repo` (list, open, log). MUST be used to open any repo other than your own workspace
  checkout before reading or modifying its files: linked repos, sidecars, other SASE projects, or any GitHub repo not
  linked to the current project (opened on demand as an external repo). Also required instead of web-fetching a repo's
  files or history (github.com / raw.githubusercontent.com / GitHub API).
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

## Researching External GitHub Projects

Open an unlinked GitHub project as an external repo before studying its files or history:

```bash
sase repo open gh:steveyegge/beads -r "Research how upstream beads evolved"
```

Use the printed path to read files such as `README.md` and `CHANGELOG.md` and to run `git log`. Do not web-fetch
github.com or raw.githubusercontent.com file URLs as a substitute. The checkout provides the full tree and history, and
the open is recorded in the `sase repo log` audit trail.

Web tools remain appropriate for content the checkout does not contain, such as GitHub issue and PR discussions, blog
posts, and docs sites.

## Inspect Repositories

- `sase repo list` shows the current project's primary, sidecar, linked, and opened external repositories. Add `--json`
  for machine-readable inventory data or `--all` for every registered project.
- `sase repo log` shows the durable repository-open audit trail. Filter with `--repo`, `--agent`, `--workspace`, or
  `--id`; add `--json` for machine-readable output.
