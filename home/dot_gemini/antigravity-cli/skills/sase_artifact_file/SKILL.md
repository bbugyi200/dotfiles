---
name: sase_artifact_file
description:
  Create and read SASE artifact files with `sase artifact` (create, list, show, path, open, doctor). Use when you must
  register a file you produced as a durable artifact, discover artifacts an earlier agent left behind, or resolve an
  artifact reference someone handed you to a concrete path.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_artifact_file --reason "<one-line reason for using this skill>"
```

Use this skill when you need to produce an artifact file that should be available from the SASE Agents tab, or when you
need to find, inspect, resolve, or open an already indexed artifact.

The canonical command group is `sase artifact`. `sase artifact-file` remains a compatibility alias, and bare
`sase artifact` defaults to `sase artifact list`. Only `create` requires an agent run (`SASE_AGENT=1` and
`SASE_ARTIFACTS_DIR`); the read subcommands (`doctor`, `list`, `open`, `path`, `show`) work anywhere.

## Create an Artifact

1. Create the requested file in your workspace.
2. Register it as an explicit artifact file:

   ```bash
   sase artifact create -p <path> -l "<label>"
   ```

3. Report the `id:`, `source:`, stored `path:`, and durable `ref:` printed by the command. The `ref:` line (`file:<id>`)
   is the copyable name to hand to the user or to another agent.

Options:

- `-k, --kind` may be one of `chat`, `plan`, `image`, `markdown`, `pdf`, or `file`. Omit it to infer from the file
  extension.
- `-l, --label` sets the artifact-file display name (defaults to the source file name).
- `-m, --move` removes the source after storing it. Use this only for a scratch file that should not be left behind;
  using it on a tracked file leaves a deletion in the working tree.
- `-p, --path` is required and points to the file you created.

By default the command copies the file, so the source stays where you created it. The stored copy is a snapshot: later
edits to the source do not propagate to it. Run `create` again to register a fresh snapshot.

Explicit artifacts always keep their own bytes; the automatic-capture rules below never apply to `create`.

## VCS-Backed Artifacts

Automatic capture at agent finalization keeps bytes only for files the run authored that version control cannot
reproduce. When a candidate's exact content is already reachable from a durable (pushed) commit, SASE writes a byte-free
**reference** row carrying `vcs_repo`, `vcs_sha`, and `vcs_relpath` instead of copying the file. A file that is only
mentioned in a prompt, lives inside a known repo, and is not reproducible from version control gets no row at all.

Reference rows are ordinary artifacts everywhere except that they have no stored path:

- `sase artifact list` renders them normally; their JSON records carry `"path": null` plus the three `vcs_*` fields.
- `sase artifact show` reports `stored_path_status: vcs-backed (<repo>@<sha>:<relpath>)` and
  `resolution_status: vcs_backed`.
- `sase artifact path` and `sase artifact open` materialize the content on demand into a content-keyed cache under
  `~/.sase/artifacts/vcs-cache/` and then behave exactly as they do for a stored file. `@file:` references in a prompt
  expand the same way.
- Materialization is content-verified: bytes are only handed back after their SHA-256 matches the recorded digest. If no
  known checkout of the repo can produce them, `path` exits 1 with a diagnostic naming the repo, commit, and path rather
  than returning a wrong or empty file.

Deleting `vcs-cache/` is safe; it only costs re-materialization.

## Find Prior Artifacts

`sase artifact list` prints a table of KIND, REF, LABEL, PROJECT, AGENT, SIZE, and CREATED, newest first. Filters:
`-a/--agent`, `-e/--explicit`, `-k/--kind` (repeatable), `-l/--limit` (default 50; `0` means unlimited), `-p/--project`
(display name, alias, or key), `-q/--query` (substring over label and paths), and `-s/--since` (`YYYY-MM-DD`, `YYYY-MM`,
`YYYYMM`, or a relative `14d` / `3w` / `2m`). Add `-u/--unused` to show only artifact files no agent has ever referenced
in a launch prompt.

```bash
# Images this project produced in the last two weeks.
sase artifact list -p sase -k image -s 14d

# Everything a given agent registered explicitly, as JSON.
sase artifact list -a bbugyi200.athena.ov -e -j

# Artifacts that have not been referenced by any agent prompt.
sase artifact list -u -l 20
```

Add `-j/--json` for a stable machine-readable array; each record carries every index field, including `sha256`,
`size_bytes`, and `mime_type`, plus the rendered `ref`.

## Consumption Tracking

When an agent launch prompt contains `@` artifact references, SASE automatically records each successfully expanded
canonical reference in `~/.sase/artifacts/consumption.jsonl`. The ledger records the consuming agent, timestamp,
reference kind, optional fragment, resolution status, and a v1 role: `report`, `image`, `source`, or reserved
`test-result`. Videos are grouped under `image` because the role means visual media.

Use `sase artifact show <ref>` to see `consumption_count`, `consumed_by_agents`, `consuming_agents`, and
`last_consumed_at` for any resolved reference. Use `sase artifact list --unused` to find indexed `file:` artifacts with
no recorded consumption. Once a canonical, fragment-free `file:` reference is recorded, the shared artifact lifecycle
collector protects its ID from `sase artifact prune`, `sase artifact reclaim`, and opt-in automatic retention, even if
no ProjectSpec, plan, bead, or research document persistently names it. A missing ledger is harmless; if the ledger
exists but cannot be queried, destructive apply is refused and automatic enforcement is skipped rather than risking the
artifact.

## Resolve a Reference You Were Handed

`show`, `path`, and `open` accept any artifact reference — `file:`, `chat:`, `bug:`, `commit:`, and document roles such
as `plans:`, `research:`, and `designs:` — plus `#L`, `#page=`, and `#t=` fragments. A bare `default:<hash>` or
`explicit:<hash>` id is accepted as sugar for `file:<id>`.

```bash
# Full metadata plus a resolution report (add -j for JSON).
sase artifact show file:explicit:0123456789abcdef01234567

# Exactly one absolute path on stdout — use this to compose with other tools.
sase artifact path plans:202607/artifact_read_cli.md

# Open with the right viewer for the kind and mime type.
sase artifact open file:default:0123456789abcdef01234567
```

`show` also reports consumption from the ledger. In JSON mode the `consumption` field is an object with the full
summary, or `null` when the reference has never been consumed.

`path` exits 0 on success, 1 for a missing, ambiguous, or malformed reference (candidates are listed on stderr), and 2
for kinds with no filesystem identity (`commit:`, `bug:`) — use `show` for those. `open` pages text through `bat`,
renders images inline when kitty graphics are available, plays video with a bounded `mpv`, falls back to `xdg-open`, and
opens `bug:` references in a browser.

## Check Index Health

`sase artifact doctor` reports index health and exits 1 when it finds problems. Add `-f/--fix` to backfill missing
`sha256` / `size_bytes` / `mime_type` fields, and `-v/--verify` to re-hash live stored files against their recorded
digests.

Byte-free VCS-backed rows are healthy, not missing. Doctor counts them under `VCS reference rows`, flags rows with a
partial `vcs_*` triple under `Incomplete VCS provenance`, and — with `-v/--verify` — materializes each one and reports
any that cannot be reproduced under `Unresolvable VCS references`.
