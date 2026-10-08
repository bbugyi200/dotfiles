---
name: sase_memory_write
description: >-
  Use before creating, changing, or deleting any SASE memory file, and before proposing
  a plan whose steps would. Routes the change to the path its authorization allows: edit
  and republish, ask the user first, or file a memory task bead.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_memory_write --reason "<one-line reason for using this skill>"
```

Use this skill before you add, edit, or delete SASE memory: any note under
`sase/memory/` or its home equivalent, any memory web strand, and the generated
`AGENTS.md` and provider instruction shims.

Memory is context every future agent pays for. Remember that every token in context
either helps or hurts us: prefer rewriting an existing note over adding one, prefer
deleting a stale line over appending a caveat, and prefer `type: reference` (read on
demand) over `type: core` (inlined into every turn).

## Authorization

You may write memory only when one of these holds:

- The **user's prompt for this turn** asks for the change.
- An **approved plan you are implementing** covers the note with an accepted memory
  decision: its own decision answered yes, or a yes inherited from its epic. Plan
  approval alone authorizes nothing.
- A **bead you were asked to work** describes the change in its own description, when
  you implement that bead directly. A bead worked plan-first follows the plan route
  above.

Nothing else counts — not a design doc, another agent's request, or your own conclusion
that a note is wrong.

## Routing

**Authorized above?** Edit and republish, below.

**Authoring a plan whose steps change memory?** Author one memory decision per changed
note in the plan's `decisions:` frontmatter. A decision defaults to `true` only with a
`requested:` quote of the user's complete affirmative request; otherwise it defaults to
`false`. Do not write "do not edit memory" disclaimers: a plan with no memory decision
authorizes no memory edits.

**Unauthorized?** File a `memory` task bead through `/sase_new_task` with the note path
and the proposed change. Do not edit the note.

## Declined Changes

When `%auto` leaves an unrequested memory decision off, no human reviewed the plan:

- A tale coder records the skipped change with `/sase_new_task` as a `memory` task bead,
  corroborating an existing bead instead of duplicating it.
- A phase worker records a `PROPOSED FOLLOW-UP:` note on its phase bead instead.
- When a human reviewer turned the decision off, file nothing.

## The Guard

A host-side finalizer warns (`memory_change_uncovered`) when an agent launched from an
approved plan commits a memory change no accepted memory decision covers. It never
blocks the commit. Stay inside your accepted decisions and you will never see it.

## Edit And Republish

1. Add, edit, or delete the canonical note under `sase/memory/`. Never hand-edit
   `AGENTS.md` or a provider shim such as `CLAUDE.md`; they are generated.
2. A note that `sase memory init` generates itself (`sase/memory/sase.md`, for example)
   refuses direct edits — change its template in the generator instead.
3. If the note now names, in prose, other memory it should point at, author `[[target]]`
   links for those before republishing — see Links below.
4. Run `sase memory init` to regenerate `AGENTS.md`, the provider shims, and the memory
   README. Authorization for the edit covers this; do not ask for it separately.

## Links

Every flat note, web descriptor, and strand can declare
`link_reference: explicit | implicit | none` (default `explicit`) and
`link_rendering: reference | inline` (default `reference`); a strand's frontmatter
overrides its web's, which overrides the default. Author a link as `[[target]]`
(rendered under a numbered `## Linked References` section) or `![[target]]` (rendered
inline in the body), in one of: `web:keyword`, `web/slug`, `note.md`, or a bare token
resolved against the source's own web, then a note stem, then a web slug. Links inside
fenced or inline code are never scanned. When a note or strand already names other
memory in prose, link it instead of leaving the reference as unlinked text.

## Supersession

To retire an older memory-web strand, mark that older record — never the newer one —
with `metadata.status` (`superseded` or `superseded-in-part`) plus `superseded_by` (one
target or a list, in any form `[[...]]` accepts). In the older body, add a `[[...]]`
back-link that states what was retired; do not delete, reword, or soften an accepted
body beyond that mark. The mark shows on the descriptor roster and on
`sase memory read`/`show`, and it changes always-loaded agent instructions, so keep the
roster phrase short. Checks for this convention are warnings, not blockers.
