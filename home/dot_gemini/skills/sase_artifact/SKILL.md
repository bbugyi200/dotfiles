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
- `sase artifact list -j -q '<text>' -l 50` - text search across indexed artifact fields.
- `sase artifact list -j -L parent -r <root_id> -l 50` - artifacts reachable under a root through parent links.
- `sase artifact list -j -P manual -l 50` - manually-created artifacts.

If the list is empty, say "no matching artifacts found" plainly. Do not infer artifact details from names alone.

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
sase artifact rebuild -j
sase artifact doctor -j
```

`rebuild` mutates derived graph rows in the artifact index. Use it for stale-index troubleshooting, not for routine
read-only discovery.

Common doctor issues:

- `fallback_agent_id` - a legacy unnamed agent was indexed with a deterministic fallback ID.
- `unresolved_timestamp_link` - retry, question, or follow-up metadata references an agent timestamp that was not
  indexed.
- `unresolved_changespec_reference` - metadata or a bead references a missing ChangeSpec.
- `unresolved_bead_reference` - metadata references a missing bead.
- `stale_derived` - stale cleanup marked a derived row whose source disappeared.

For missing current context, prefer targeted rebuilds over full rebuilds:

- `sase artifact rebuild -j -t <project_or_file_path>` - refresh one project or file path.
- `sase artifact rebuild -j -b <workspace>/sdd/beads -S bead_store` - refresh a bead store.
- `sase artifact rebuild -j -a <artifact_dir> -S agent_artifact -S agent_created_file` - refresh one agent directory.
- `sase artifact rebuild -j -c mark` - mark stale derived rows after intentional source removal.

## Mutating Commands

These commands change the artifact index and require explicit user intent:

- `sase artifact add -j -a <id> -k <kind> -t '<title>'` - add or update a manual artifact node.
- `sase artifact add -j -l 'parent|<child_id>|<parent_id>'` - add a manual link.
- `sase artifact remove -j -a <artifact_id> -r '<reason>'` - remove or tombstone an artifact.
- `sase artifact remove -j -T <type> -S <source_id> -D <target_id> -r '<reason>'` - remove or tombstone a link tuple.
- `sase artifact rebuild -j` - rebuild derived graph rows.

When mutating, prefer `-j`, report affected node/link IDs and tombstone IDs, and stop if the command reports errors.
Tombstones suppress graph rows or links; they do not delete the source project file, bead record, marker file, response,
diff, or transcript.
