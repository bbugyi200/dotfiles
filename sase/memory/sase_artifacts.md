---
type: reference
parent: AGENTS.md
description:
  Read before creating, consuming, resolving, linking, or managing retention for SASE
  artifact references and indexed files.
---

# SASE Artifacts

`sase artifact <cmd> -h` documents the exhaustive flags; this note covers the domain
boundaries and safety rules agents must remember.

## Model

An artifact is any durable record with a canonical `<kind>:<argument>` identity: sidecar
documents, beads, agents, Patches, stitches, and indexed files all count. The leading
`@` belongs to prompt citations and prompt expansion, not to stored identities or
ordinary CLI arguments.

Artifact references provide identity, resolution, prompt expansion, publication, and
consumption tracking. `sase artifact list` is narrower: it inventories indexed files
only, not every plan, bead, Patch, stitch, or agent artifact. Canonical archived prompts
live in the agents sidecar and are inspected with `sase agent prompts`, not by treating
the file index as the prompt archive.

Indexed files are explicit snapshots created by an agent with `sase artifact create`, or
automatic captures from agent finalization. Automatic captures may keep bytes in the
artifact store or become verified VCS-backed locators when the same content is
reproducible from version control. Explicit snapshots are immutable and permanent.

## Read And Resolve

Use an audited read whenever an artifact is context for your work:

```bash
sase artifact read plan:202608/example.md "Need the design context"
```

Use `show` for metadata and resolution details, `path` when another command needs a
filesystem path, and `open` when a viewer is the right interface:

```bash
sase artifact show file:explicit:0123456789abcdef01234567
sase artifact path plan:202608/example.md
sase artifact open file:explicit:0123456789abcdef01234567
```

## Create And Discover Files

Register produced deliverables as explicit snapshots:

```bash
sase artifact create -p report.md -l "Investigation report"
sase artifact create -p report.md -l "Investigation report" --bead sase-a1
```

By default the source file is copied and remains in place. Use `--move` only when the
source is disposable, because the stored artifact is the permanent copy and removing a
tracked source leaves a deletion in the working tree.

Discover indexed files with `list`; do not present it as a universe-wide artifact
search:

```bash
sase artifact list --kind markdown --project sase
```

## Links

Typed links connect durable artifacts and project into artifact Markdown pages. Add
deliberate manual links with bare canonical refs and a one-line reason:

```bash
sase artifact link add plan:202608/example.md related bead:sase-a1 "tracks the same failure"
sase artifact link add plan:202608/example.md supersedes plan:202607/old-example.md "replaces the older plan"
sase artifact link add plan:202608/example.md implements bead:sase-a1 "lands the approved design"
sase artifact link add plan:202608/example.md derives-from research:202608/source.md "uses its measurements"
```

Typed links use a closed relation registry:

- `cites`: inverse `cited-by`, directed yes, written by `prompt_ref`.
- `read`: inverse `read-by`, directed yes, written by `read`.
- `related`: inverse `related`, directed no, written by `cli`.
- `supersedes`: inverse `superseded-by`, directed yes, written by `cli`.
- `implements`: inverse `implemented-by`, directed yes, written by `cli`.
- `derives-from`: inverse `derived-into`, directed yes, written by `cli`.
- `produced-by`: inverse `produced`, directed yes, written by `projection`.
- `launched`: inverse `launched-by`, directed yes, written by `projection`.

Manual `link add` writes only the `cli` relations; `cites` is written by prompt-ref
expansion and `read` by audited reads. These slugs are scheduling concepts, not artifact
links, and remain `sase bead dep`:

- `blocks`: use `sase bead dep` instead.
- `depends-on`: use `sase bead dep` instead.

## Retention

Explicit snapshots and files with persistent recorded references or consumption are
protected. Automatic captures can be reclaimed into verified VCS locators or pruned by
retention policy. `prune` and `reclaim` are previews unless `--apply` is passed. Removal
moves rows to restorable trash; purge is irreversible.

Agents must not apply lifecycle mutations or purge trash without explicit user
authorization.
