---
name: sase_patches
description:
  Analyze and work with SASE Patches. Use when inspecting PR status, dependencies,
  stitches, hooks, comments, mentors, or `.sase` project files.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_patches --reason "<one-line reason for using this skill>"
```

Quick reference for inspecting and reasoning about SASE Patches.

## Current Patch

When the task concerns the current PR or checkout, start with:

```bash
sase patch current -f markdown
```

This resolves by current PR URL first, then by branch/bookmark name, and prints the
matching Patch with its project, status, parent, PR, and file location. Use `-f json`
when a script or automation step needs structured fields.

## Primary Command

```bash
sase patch search '<query>' -f markdown
```

This prints agent-friendly markdown with each Patch's name, project, status, parent, PR,
and the file/line where it lives.

## Exact Lookup

```bash
sase patch search '&<patch_name>' -f markdown
```

`&name` (alias `name:name`) is an exact-name match. Prefer it over substring search when
you know the name.

## When You Need Raw Detail

```bash
sase patch search '&<patch_name>' -f plain
```

`-f plain` exposes file paths, line numbers, drawer entries (`STITCHES`, `HOOKS`,
`COMMENTS`, `MENTORS`), and full descriptions. Use it when Markdown is too summarized.
Legacy `COMMITS` drawers are displayed as stitch data when present.

## Query Shortcuts

- `&name` / `name:name` — exact Patch lookup.
- `+project` / `project:project` — filter by project.
- `^parent` / `ancestor:parent` — filter by parent chain and return descendants.
- `~name` / `sibling:name` — sibling / reverted-family filtering.
- `%w`, `%d`, `%y`, `%m`, `%s`, `%r` — status filters for WIP, Draft, Ready, Mailed,
  Submitted, and Reverted.
- `!!!`, `@@@`, `$$$`, `*` — error suffixes, running agents, running processes, or any
  of those.
- `!!`, `!@`, `!$` — negations for no errors, no running agents, or no running
  processes.

Boolean queries work too: `'"feature" AND %r'`, `'+myproject AND (!!! OR @@@)'`.

## How To Summarize

- Lead with `name`, `project`, `status`, `parent`, PR, and the file location when
  available.
- Call out blockers explicitly: non-terminal parent, failed hooks, unresolved comments,
  running agents/processes, rejected proposals, or new proposals.
- For multi-result queries, group by project and status, and surface the most relevant
  Patches first.
- If the result set is empty, say so plainly. Do not fabricate Patches.

## Common Workflows

### What Is Blocking This Patch?

```bash
sase patch search '&<name>' -f plain
```

Inspect for: a non-terminal `PARENT`, error suffixes (`- (!: ...)`) under `HOOKS`,
`COMMENTS`, or `MENTORS`, running agents (`@@@`), or running processes (`$$$`). To scan
the whole subtree for any blocking state:

```bash
sase patch search '^<name> AND *' -f markdown
```

### What Changed In The Latest Stitch Or Proposal?

```bash
sase patch search '&<name>' -f plain
```

The `STITCHES` drawer lists every stitch/proposal with its `CHAT` and `DIFF` paths; the
highest-numbered entry is the most recent. Numeric stitches are created for real VCS
commits. Proposal stitches such as `(2a)` are commitless until accepted.

### Manage Durable Artifact References

Patches can carry a `REFS:` section between `STATUS:` and `STITCHES:`. Store one
canonical artifact reference per 2-space-indented line, without the prompt-time `@`
sigil:

```bash
sase patch ref add --patch <name> research:202607/report.md
sase patch ref list --patch <name> --resolve
sase patch ref rm --patch <name> research:202607/report.md
```

Omit `--patch` to target the Patch for the current checkout. `add` normalizes and
deduplicates entries; `rm` detaches normalized entries; `list --json` emits
machine-readable reference data. Use `sase doctor -C project.patch_refs` when you need
to audit malformed, unresolvable, or ambiguous `REFS` entries.

### Find Children Or Descendants Of A Patch

```bash
sase patch search '^<name>' -f markdown
```

`^name` returns every Patch whose parent chain contains `<name>`. There is no inverse
`children:` operator; descendants are reached via this ancestor query.

### Is It Ready To Mail Or Submit?

A Patch is ready when `STATUS` is `Ready` (or `Mailed` for submit) with no errors and no
running agents/processes. Confirm against one Patch, or scan a subtree:

```bash
sase patch search '&<name>' -f markdown
sase patch search '^<name> AND %y AND !! AND !@ AND !$' -f markdown
```

### Inspect Failed Hooks, Review Comments, And Mentor State

```bash
sase patch search '&<name>' -f plain
```

- `HOOKS` lines ending in `- (!: ...)` are failed hook attempts.
- `COMMENTS` lines ending in `- (!: ...)` are unresolved review comments.
- `MENTORS` lines ending in `- (!: ...)` flag mentor errors.

For mentor-profile diagnostics:

```bash
sase config mentor-match <name>
```

## Lifecycle

`WIP -> Draft -> Ready -> Mailed -> Submitted`. `Submitted`, `Archived`, and `Reverted`
are terminal. Terminal Patches live in `<project>-archive.sase`; active Patches live in
`<project>.sase` under `~/.sase/projects/<project>/`. Legacy `.gp` files from earlier
releases remain readable until migrated via `sase patch migrate-extension`.

## Safe Modification Rules

- Do not manually edit `STITCHES` or `TIMESTAMPS`; they are managed by
  `sase stitch create` and lifecycle operations.
- Do not set `PARENT` to a VCS ref like `origin/main`, `origin/master`, or `p4head`.
  `PARENT` must be another Patch name, or omitted.
- Prefer `sase patch ref add` and `sase patch ref rm` over direct `REFS:` edits.
- Prefer `sase stitch create`, `sase revert <name>`, and `sase restore <name>` over
  direct `.sase` surgery for tracked workflow changes.
- If you must edit a `.sase` file directly, preserve two blank lines between Patches and
  2-space indentation for multiline fields.

## Compatibility Notes

- `sase changespec ...` remains an alias for `sase patch ...`.
- `-c`/`--changespec` remains an alias for `--patch` where Patch-targeting commands
  accept it.
- Legacy `COMMITS:` sections are still readable; new sections use `STITCHES:`.
- Legacy `CL:` fields are readable during the compatibility window; new and touched
  records use `PR:`.

## Other Useful Forms

- `sase ace` — interactive Patch browser and agent control surface.
- `sase stitch create` — make real commits, proposals, or PRs and update `STITCHES`
  automatically.
- `sase revert <name>` / `sase restore <name>` — lifecycle-level destructive/recovery
  operations.
- `sase config mentor-match <name>` — diagnose mentor-profile matching for a Patch.

## Implementation Notes

Patch sections: `NAME`, `DESCRIPTION`, `PARENT`, `PR`, `BUG`, `STATUS`, `REFS`,
`STITCHES`, `DELTAS`, `HOOKS`, `COMMENTS`, `MENTORS`, `TIMESTAMPS`. Search reads both
`<project>.sase` and `<project>-archive.sase` (and their legacy `.gp` siblings during
the migration window), so submitted and archived Patches are reachable via the same
queries.
