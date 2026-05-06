---
name: sase_artifact
description:
  Inspect the SASE unified artifact graph with stable JSON commands, and mutate it only when explicitly asked.
---

Quick reference for inspecting SASE unified artifacts. Prefer JSON for discovery and summaries. Do not add, remove, or
rebuild artifacts unless the user explicitly asks for a mutating operation.

## Mental Model

The artifact graph is an index over existing SASE state. It does not own or delete source files. Rebuilds refresh
derived rows from project files, bead stores, workspace paths, and agent artifact directories.

`sase ace` startup must not run broad unified artifact sync, rebuild, list, show, search, or summary operations before
first paint. Treat historical index repair as an explicit user-requested operation.

Important IDs and link directions:

- `/` is the root artifact.
- Files and directories use absolute normalized paths.
- ChangeSpecs use the ChangeSpec `NAME`; commits use `<changespec_name>:<commit_number>`.
- Beads use bead IDs such as `sase-23.5.6`.
- Agents use stable agent names when present. Legacy unnamed agents use `agent:<project>:<workflow>:<timestamp>`.
- Thoughts use `thought:<sha256-prefix>`.
- `parent` points child -> parent, `created` points agent -> created artifact, `worker` points bead -> agent, and
  `related` connects non-owning relationships.

## Primary Discovery

```bash
sase artifact list -j -l 50
```

This prints a stable-shape JSON array of artifact nodes. Each node has: `id`, `kind`, `display_title`, `subtitle`,
`provenance`, `source_kind`, `source_id`, `source_version`, `search_text`, `metadata`, `created_at`, and `updated_at`.

Useful filters:

- `sase artifact list -j -k file -l 50` - file artifacts.
- `sase artifact list -j -k file -F plan -F diff -l 50` - file artifacts by semantic file type.
- `sase artifact list -j -q '<text>' -l 50` - text search across indexed artifact fields.
- `sase artifact search -j -q '<text>' -F plan -l 50` - interactive global artifact search.
- `sase artifact list -j -L parent -r <root_id> -l 50` - artifacts reachable under a root through parent links.
- `sase artifact list -j -P manual -l 50` - manually-created artifacts.

File artifacts keep `kind = "file"` and store the semantic type in `metadata.artifact_type`. Canonical file types are
`plan`, `diff`, `chat`, `project`, `prompt`, and `misc`; missing or unknown metadata reads as `misc`.

Directory artifacts are sparse: `/` is always present, and non-root directories exist only as containers for visible
non-directory artifacts.

If the list is empty, say "no matching artifacts found" plainly. Do not infer artifact details from names alone.

## TUI Panel Contract

In `sase ace`, `A` opens the artifact panel for the current row. Panel behavior to preserve when advising users or
debugging regressions:

- `j`/`k` move rows; `enter` opens an artifact row or loads a `show more` page.
- `/` is a local filter over loaded rows and should not call `artifact_search`.
- `S` is bounded global search through `sase artifact search`.
- Apostrophe starts row-jump mode for relationship rows, search rows, and `show more` rows.
- `b`/`f` navigate panel history, `p` opens the parent, `r` opens `/`, and `g`/`G` preview or export a bounded graph.

Missing artifacts may trigger one targeted refresh for the current context. Do not imply that opening the panel runs a
broad historical `sync` or `rebuild`; advise manual repair commands when the targeted refresh still misses.

CL and Agent rows use compact artifact indicators from one batched summary query per visible-list refresh. The counts
summarize linked artifacts by semantic file type and non-file kind, and hot `j`/`k` navigation should use cached rows
without issuing artifact summary queries.

## Exact Inspection

After choosing an artifact ID, inspect it directly:

```bash
sase artifact show -j -a <artifact_id>
```

The JSON detail object has: `schema_version`, `node`, `payloads`, `outbound_links`, `inbound_links`, `children`,
`path_to_root`, and `diagnostics`.

Link rows have: `id`, `link_type`, `source_id`, `target_id`, `provenance`, source fields, `metadata`, `created_at`, and
`updated_at`. Payload rows have: `artifact_id`, `payload_type`, `provenance`, source fields, `payload`, and
`updated_at`.

Use direct inspection before summarizing relationships, payloads, or diagnostics.

## Graph Views

Use a bounded JSON graph when relationships matter:

```bash
sase artifact graph -j -a <artifact_id> -d 2
```

The graph JSON has: `schema_version`, `root_id`, `nodes`, `links`, `node_count`, `link_count`, `truncated`, and `limit`.
If `truncated` is true, say the graph was limited and avoid presenting it as complete.

Other useful formats:

- `sase artifact graph -f text -a <artifact_id> -d 2` - compact human edge list.
- `sase artifact graph -f dot -a <artifact_id> -d 2` - DOT output.
- `sase artifact graph -f mermaid -a <artifact_id> -d 2` - Mermaid output.
- `sase artifact graph -j -F -l 500` - bounded full-graph JSON.

## Doctor And Stale Indexes

Check graph consistency with:

```bash
sase artifact doctor -j
```

The doctor JSON has `ok` and `issues`. Issue rows include `issue_type`, `severity`, `artifact_id`, `link_id`, and
`message`. If `ok` is false or issues are present, summarize the issue rows and cite affected IDs.

For stale or missing index data, run troubleshooting in this order only when the user asks to refresh the index:

```bash
sase artifact sync -j
sase artifact doctor -j
```

`sync` is an explicit historical sync/backfill alias for `rebuild`; it mutates derived graph rows in the artifact index
and is not run on `sase ace` startup. Use it for stale-index troubleshooting, not for routine read-only discovery.

New artifact writes are indexed by existing targeted refresh paths where SASE knows the changed source. Historical
backfill still requires explicit `sync` or `rebuild`.

Common doctor issues:

- `fallback_agent_id` - a legacy unnamed agent was indexed with a deterministic fallback ID.
- `unresolved_timestamp_link` - retry, question, or follow-up metadata references an agent timestamp that was not
  indexed.
- `unresolved_changespec_reference` - metadata or a bead references a missing ChangeSpec.
- `unresolved_bead_reference` - metadata references a missing bead.
- `orphan_directory` - a non-root directory artifact has no visible non-directory descendants.
- `stale_derived` - stale cleanup marked a derived row whose source disappeared.

For missing current context, prefer targeted rebuilds over full rebuilds:

- `sase artifact sync -j -t <project_or_file_path>` - refresh one project or file path.
- `sase artifact rebuild -j -b <workspace>/sdd/beads -S bead_store` - refresh a bead store.
- `sase artifact sync -j -a <artifact_dir> -S agent_artifact -S agent_created_file` - refresh one agent directory.
- `sase artifact rebuild -j -c mark` - mark stale derived rows after intentional source removal.

## Mutating Commands

These commands change the artifact index and require explicit user intent:

- `sase artifact add -j -a <id> -k <kind> -t '<title>'` - add or update a manual artifact node.
- `sase artifact add -j -l 'parent|<child_id>|<parent_id>'` - add a manual link.
- `sase artifact remove -j -a <artifact_id> -r '<reason>'` - remove or tombstone an artifact.
- `sase artifact remove -j -T <type> -S <source_id> -D <target_id> -r '<reason>'` - remove or tombstone a link tuple.
- `sase artifact rebuild -j` - rebuild derived graph rows.
- `sase artifact sync -j` - explicit historical sync/backfill alias for rebuild.

When mutating, prefer `-j`, report affected node/link IDs and tombstone IDs, and stop if the command reports errors.
Tombstones suppress graph rows or links; they do not delete the source project file, bead record, marker file, response,
diff, or transcript.
