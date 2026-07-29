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

3. Report the `id:`, stored `path:`, and durable `ref:` printed by the command. The `ref:` line (`file:<id>`) is the
   copyable name to hand to the user or to another agent.

Options:

- `-p, --path` is required and points to the file you created.
- `-l, --label` sets the artifact-file display name (defaults to the source file name).
- `-k, --kind` may be one of `chat`, `plan`, `image`, `markdown`, `pdf`, or `file`. Omit it to infer from the file
  extension.

The command moves the file into SASE artifact-file storage, so do not edit the original path after registration.

## Find Prior Artifacts

`sase artifact list` prints a table of KIND, REF, LABEL, PROJECT, AGENT, SIZE, and CREATED, newest first. Filters:
`-a/--agent`, `-e/--explicit`, `-k/--kind` (repeatable), `-l/--limit` (default 50; `0` means unlimited), `-p/--project`
(display name, alias, or key), `-q/--query` (substring over label and paths), and `-s/--since` (`YYYY-MM-DD`, `YYYY-MM`,
`YYYYMM`, or a relative `14d` / `3w` / `2m`).

```bash
# Images this project produced in the last two weeks.
sase artifact list -p sase -k image -s 14d

# Everything a given agent registered explicitly, as JSON.
sase artifact list -a bbugyi200.athena.ov -e -j
```

Add `-j/--json` for a stable machine-readable array; each record carries every index field, including `sha256`,
`size_bytes`, and `mime_type`, plus the rendered `ref`.

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

`path` exits 0 on success, 1 for a missing, ambiguous, or malformed reference (candidates are listed on stderr), and 2
for kinds with no filesystem identity (`commit:`, `bug:`) — use `show` for those. `open` pages text through `bat`,
renders images inline when kitty graphics are available, plays video with a bounded `mpv`, falls back to `xdg-open`, and
opens `bug:` references in a browser.

## Check Index Health

`sase artifact doctor` reports index health and exits 1 when it finds problems. Add `-f/--fix` to backfill missing
`sha256` / `size_bytes` / `mime_type` fields, and `-v/--verify` to re-hash live stored files against their recorded
digests.
