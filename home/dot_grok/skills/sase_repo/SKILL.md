---
name: sase_repo
description: >-
  Work with repos through `sase repo` (list, open, log). MUST be used to open any repo
  other than your own workspace checkout before reading or modifying its files: linked
  repos, sidecars, other SASE projects, or any GitHub repo not linked to the current
  project (opened on demand as an external repo). Also required instead of web-fetching
  a repo's files or history (github.com / raw.githubusercontent.com / GitHub API).
---

Use this skill before reading or modifying files in any repository other than your own
workspace checkout.

## Open A Repository

Run `sase repo open` from your workspace directory with a specific audit reason. It
resolves references in three tiers:

```bash
# A repository in the current project's inventory (linked repo, sidecar, or primary)
sase repo open sase-github -r "Review the workspace-provider implementation"

# Another registered SASE project's primary repository
sase repo open dotdrop -r "Port the launcher fix requested by the user"

# A GitHub repository not linked to the current project
sase repo open gh:pallets/click -r "Study upstream option parsing"
```

Bare `owner/repo` is shorthand for `gh:owner/repo`.

The command prints the prepared path to stdout. Use that printed path as the only path
for subsequent reads and writes. Never locate or clone a linked repo, sidecar, different
SASE project, or unlinked GitHub repo another way. Pass `-w <workspace_num>` only when
running outside the workspace whose repo clone you need.

Use `sase repo open` when you need to modify a repository or explore a repo tree. Use
`sase artifact read <ref> "<reason>"` when you need one artifact as recorded context;
that path prints the artifact content, strips managed link tables, and records the read
instead of silently opening files.

## Commit Obligation For Opened Repositories

If you modify a repository opened with this skill, that repository becomes part of this
turn's final declaration. `/sase_final` will surface it as a repository obligation, and
it needs a `commit` decision exactly like the primary workspace checkout.

Long-running turns may open a repo early and only see its dirty obligation much later.
If you do not recognize the paths, check `sase repo log` and the run's tool-call
history; do not treat "not the main repo" or "I do not recognize it" as a reason to
decline your own changes.

## Researching External GitHub Projects

Open an unlinked GitHub project as an external repo before studying its files or
history:

```bash
sase repo open gh:steveyegge/beads -r "Research how upstream beads evolved"
```

Use the printed path to read files such as `README.md` and `CHANGELOG.md` and to run
`git log`. Do not web-fetch github.com or raw.githubusercontent.com file URLs as a
substitute. The checkout provides the full tree and history, and the open is recorded in
the `sase repo log` audit trail.

Web tools remain appropriate for content the checkout does not contain, such as GitHub
issue and PR discussions, blog posts, and docs sites.

## Inspect Repositories

- `sase repo list` shows the current project's primary, sidecar, linked, and opened
  external repositories. Add `--json` for machine-readable inventory data or `--all` for
  every registered project.
- `sase repo log` shows the durable repository-open audit trail. Filter with `--repo`,
  `--agent`, `--workspace`, or `--id`; add `--json` for machine-readable output.
