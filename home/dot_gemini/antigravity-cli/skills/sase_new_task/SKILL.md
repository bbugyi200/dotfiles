---
name: sase_new_task
description:
  Use before creating, filing, proposing, or otherwise recording any new SASE task bead
  or discovered follow-up. Checks for semantic duplicates and causally related active
  epics, records corroboration in the right place, and requires an intentional task size
  when a genuinely new task is warranted.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_new_task --reason "<one-line reason for using this skill>"
```

Use this skill before creating any task bead.

1. Read the task-bead policy:

   ```bash
   sase memory read sase_beads.md --reason "Need task-bead lifecycle and duplicate policy before recording discovered work"
   ```

2. Read the canonical task-size guidance:

   ```bash
   sase memory read sase_sizes.md --reason "Need SASE size guidance before choosing a task bead size"
   ```

3. Form a candidate title and scope, then gather reproducible evidence. If a file
   materially supports the report, read `sase_artifacts.md` with `/sase_memory_read`,
   register it with `sase artifact create`, and retain the canonical artifact reference.

4. Search existing task beads for prior reports, then show plausible matches:

   ```bash
   sase bead search 'symbol|filename|command|error-fragment' --regex --type task
   sase bead show <plausible-task-id>
   ```

   Search is case-insensitive across every status, closed and snoozed included. When
   several clues are available, combine a few short, distinctive terms -- a symbol,
   filename, command, or error fragment -- with `--regex` alternation and escape
   metacharacters that should match literally. When one substring is sufficient, use the
   default literal search. Do not list every task bead.

   When you already know which catalog type the report is (`sase bead task-type list`
   shows the current set), add `--task-type <slug>` to the search first: a semantic
   duplicate almost always shares the same type. Broaden to an all-types search only
   when the same-type search comes up empty, since a report can legitimately cross
   types. A search may also surface feature-flag task beads; that is harmless. Do not
   create a flag through this skill — run `sase flag new <key>` instead.

   A semantic duplicate has the same underlying defect/root cause or desired
   remediation, not merely the same subsystem or a similar symptom. Before corroborating
   a duplicate, check whether the candidate is a retired umbrella: a closed task whose
   close reason declares it retired and forbids `+1`. Retired umbrellas are tracking
   patterns that intentionally stop accepting corroboration. Do not `+1` or reopen them.
   Route the report to step 7 instead, create a node-specific task bead named for the
   failing node ID, and add a typed related artifact link:

   ```bash
   sase artifact link add bead:<new-task-id> related bead:<retired-task-id> "<how it bears on this task>"
   ```

   For any other duplicate, record independent reproduction or impact evidence and any
   artifact refs:

   ```bash
   sase bead +1 <task-id> --note "<independent reproduction and impact>" --ref <artifact-ref>
   ```

   If the duplicate bead is closed, read the command output before moving on. When it
   says the reopen was withheld because the report's observation window started before
   the close, do not reflexively retry with an override. Use
   `sase bead +1 <task-id> --verified-after-close ...` only when you actually reproduced
   the defect on a tree that already contains the close; otherwise the recorded +1 is
   the correct durable corroboration.

   Do not create a task. A reporter counts at most once; use `sase bead note` for later
   supplementary evidence.

5. Sweep every task bead created in the last week, then show plausible matches:

   ```bash
   sase bead list --type task --since 1w --status all
   sase bead show <plausible-task-id>
   ```

   A duplicate filed hours ago by another agent often shares no term with your queries,
   so this sweep is not redundant with step 3. `--since` bounds creation time and lifts
   the newest-20 closed default, and `--status all` matters because most recent task
   beads are already closed. Keep the sweep in the default compact format; never run it
   with `--format full`. Judge each row by the semantic-duplicate test above and
   corroborate with `sase bead +1` instead of creating a task when one matches.

   As in step 4, add `--task-type <slug>` when you already know the type to sweep the
   same-type set first, then broaden to every type if nothing plausible turns up.

6. Independently inspect in-progress epic plans and their plausible children:

   ```bash
   sase bead list --type plan --tier epic --status in_progress --format full --limit 0
   sase bead show <plausible-epic-id>
   sase bead show <plausible-child-id>
   ```

   When an epic has a credible causal link to the issue—not merely topical
   overlap—append the evidence to the epic:

   ```bash
   sase bead note <epic-id> "DISCOVERED ISSUE: <reproduction, impact, and artifact refs>"
   ```

   Do not create a task. If both the duplicate and active-epic branches apply, record
   both.

7. Only when neither branch applies, choose a size and a type, create an evidence-rich
   draft, attach refs, refine its scope and dependencies, then mark it ready. Default to
   `large` unless the size memory note's narrower or wider criteria clearly apply. Pick
   the `task_type` whose `when_to_use` matches what you found -- run
   `sase bead task-type list` for the current catalog and
   `sase bead task-type show <slug>` for one type's fields in full -- and supply a
   repeatable `-f/--field name=value` for each of its required fields (`-d @<path>` and
   `-f name=@<path>` read a value from a file, for prose too long to survive shell
   quoting):

   ```bash
   sase bead create -T "task(<slug>)" -t "<title>" -d @<path> --size <size> -f <field>=<value> --ref <artifact-ref>
   sase bead dep add <task-id> <blocking-bead-id>
   sase bead update <task-id> --status ready
   ```

   `task_type` is immutable once set, so pick the closest match rather than the first
   plausible one. Bare `-T task` is an error; every new task must use a catalog slug.
   Feature flags are not created here: `sase flag new <key>` is the only door, and
   `task(flag)` is not agent-creatable.

   When the search or the sweep surfaced beads that are related but are not duplicates —
   an adjacent defect, a shared root file, a bead whose fix could collide — record one
   typed related link per bead on the new task so its worker inherits that context:

   ```bash
   sase artifact link add bead:<task-id> related bead:<bead-id> "<how it bears on this task>"
   ```

   Omit `--ref` and the dependency command when they do not apply.
