---
name: sase_changespecs
description:
  Analyze and work with SASE ChangeSpecs. Use when inspecting CL/PR status, dependencies, commits, hooks, comments,
  mentors, or `.gp` project files.
---

Quick reference for inspecting and reasoning about SASE ChangeSpecs.

## Current ChangeSpec

When the task concerns the current CL/PR or checkout, start with:

```bash
sase changespec current -f markdown
```

This resolves by current PR/CL URL first, then by branch/bookmark name, and prints the matching ChangeSpec with its
project, status, parent, PR/CL, and file location. Use `-f json` when a script or automation step needs structured
fields.

## Primary command

```bash
sase changespec search '<query>' -f markdown
```

This prints agent-friendly markdown with each ChangeSpec's name, project, status, parent, PR/CL, and the file/line where
it lives.

## Exact lookup

```bash
sase changespec search '&<changespec_name>' -f markdown
```

`&name` (alias `name:name`) is an exact-name match — prefer it over substring search when you know the name.

## When you need raw detail

```bash
sase changespec search '&<changespec_name>' -f plain
```

`-f plain` exposes file paths, line numbers, drawer entries (`COMMITS`, `HOOKS`, `COMMENTS`, `MENTORS`), and full
descriptions. Use it when markdown is too summarized.

## Query shortcuts

- `&name` / `name:name` — exact ChangeSpec lookup.
- `+project` / `project:project` — filter by project.
- `^parent` / `ancestor:parent` — filter by parent chain (returns descendants of `parent`).
- `~name` / `sibling:name` — sibling / reverted-family filtering.
- `%w`, `%d`, `%y`, `%m`, `%s`, `%r` — status filters (WIP, Draft, Ready, Mailed, Submitted, Reverted).
- `!!!`, `@@@`, `$$$`, `*` — error suffixes, running agents, running processes, any of those.
- `!!`, `!@`, `!$` — negations of `!!!`, `@@@`, `$$$` (no errors / no running agents / no running processes).

Boolean queries work too: `'"feature" AND %r'`, `'+myproject AND (!!! OR @@@)'`.

## How to summarize

- Lead with `name`, `project`, `status`, `parent`, PR/CL, and the file location when available.
- Call out blockers explicitly: non-terminal parent, failed hooks, unresolved comments, running agents/processes,
  rejected or new proposals.
- For multi-result queries, group by project and status, and surface the most relevant ChangeSpecs first.
- If the result set is empty, say so plainly — do not fabricate ChangeSpecs.

## Common workflows

### What is blocking this ChangeSpec?

```bash
sase changespec search '&<name>' -f plain
```

Inspect for: a non-terminal `PARENT`, error suffixes (`- (!: ...)`) under `HOOKS` / `COMMENTS` / `MENTORS`, running
agents (`@@@`), or running processes (`$$$`). To scan the whole subtree for any blocking state:

```bash
sase changespec search '^<name> AND *' -f markdown
```

### What changed in the latest commit/proposal?

```bash
sase changespec search '&<name>' -f plain
```

The `COMMITS` drawer lists every commit/proposal with its `CHAT` and `DIFF` paths; the highest-numbered entry is the
most recent.

### Find children/descendants of a ChangeSpec

```bash
sase changespec search '^<name>' -f markdown
```

`^name` returns every ChangeSpec whose parent chain contains `<name>`. There is no inverse `children:` operator —
descendants are reached via this ancestor query.

### Is it ready to mail / submit?

A spec is ready when `STATUS` is `Ready` (or `Mailed` for submit) with no errors and no running agents/processes.
Confirm against one spec, or scan a subtree:

```bash
sase changespec search '&<name>' -f markdown
sase changespec search '^<name> AND %y AND !! AND !@ AND !$' -f markdown
```

### Inspect failed hooks, review comments, and mentor state

```bash
sase changespec search '&<name>' -f plain
```

- `HOOKS` lines ending in `- (!: ...)` are failed hook attempts.
- `COMMENTS` lines ending in `- (!: ...)` are unresolved review comments.
- `MENTORS` lines ending in `- (!: ...)` flag mentor errors.

For mentor-profile diagnostics (which profile matched, why, and any errors):

```bash
sase config mentor-match <name>
```

## Lifecycle

`WIP -> Draft -> Ready -> Mailed -> Submitted`. `Submitted`, `Archived`, and `Reverted` are terminal — terminal specs
live in `<project>-archive.gp`; active specs live in `<project>.gp` under `~/.sase/projects/<project>/`.

## Safe modification rules

- **Do not** manually edit `COMMITS` or `TIMESTAMPS` drawers — they are managed by `sase commit` and lifecycle
  operations.
- **Do not** set `PARENT` to a VCS ref like `origin/main`, `origin/master`, or `p4head`. `PARENT` must be another
  ChangeSpec name, or omitted.
- Prefer `sase commit`, `sase revert <name>`, and `sase restore <name>` over direct `.gp` surgery for tracked workflow
  changes.
- If you must edit a `.gp` file directly, preserve two blank lines between ChangeSpecs and 2-space indentation for
  multiline fields.

## Other useful forms

- `sase ace` — interactive ChangeSpec browser (terminal use, not for machine consumption).
- `sase commit` — make commits / proposals / PRs and update `COMMITS` automatically.
- `sase revert <name>` / `sase restore <name>` — lifecycle-level destructive / recovery operations.
- `sase config mentor-match <name>` — diagnose mentor-profile matching for a ChangeSpec.

## Implementation notes

ChangeSpec sections: `NAME`, `DESCRIPTION`, `PARENT`, `CL` / `PR`, `BUG`, `TEST TARGETS`, `STATUS`, `COMMITS`,
`TIMESTAMPS`, `HOOKS`, `COMMENTS`, `MENTORS`. Search reads both `<project>.gp` and `<project>-archive.gp`, so submitted
and archived specs are reachable via the same queries.
