---
name: sase_new_task
description:
  Use before creating, filing, proposing, or otherwise recording any new SASE task bead or
  discovered follow-up. Checks for semantic duplicates and causally related active epics, records
  corroboration in the right place, and requires an intentional task size when a genuinely new task
  is warranted.
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

2. Form a candidate title and scope, then gather reproducible evidence. If a file materially
   supports the report, use `/sase_artifact_file` to register it and retain the canonical artifact
   reference.

3. Inspect every existing task status, then show plausible matches:

   ```bash
   sase bead list --type task --format full --limit 0 --status open --status claimed --status ready --status in_progress --status closed
   sase bead show <plausible-task-id>
   ```

   A semantic duplicate has the same underlying defect/root cause or desired remediation, not merely
   the same subsystem or a similar symptom. For a duplicate, record independent reproduction or
   impact evidence and any artifact refs:

   ```bash
   sase bead +1 <task-id> --note "<independent reproduction and impact>" --ref <artifact-ref>
   ```

   Do not create a task. A reporter counts at most once; use `sase bead note` for later
   supplementary evidence.

4. Independently inspect in-progress epic plans and their plausible children:

   ```bash
   sase bead list --type plan --tier epic --status in_progress --format full --limit 0
   sase bead show <plausible-epic-id>
   sase bead show <plausible-child-id>
   ```

   When an epic has a credible causal link to the issue—not merely topical overlap—append the
   evidence to the epic:

   ```bash
   sase bead note <epic-id> "DISCOVERED ISSUE: <reproduction, impact, and artifact refs>"
   ```

   Do not create a task. If both the duplicate and active-epic branches apply, record both.

5. Only when neither branch applies, choose a size and create an evidence-rich draft, attach refs,
   refine its scope and dependencies, then mark it ready:

   ```bash
   sase bead create -T task -t "<title>" -d "<reproduction, impact, and scope>" --size <size> --ref <artifact-ref>
   sase bead dep add <task-id> <blocking-bead-id>
   sase bead update <task-id> --status ready
   ```

   Omit `--ref` and the dependency command when they do not apply. Sizes: `xsmall` is nearly
   mechanical; `small` is focused and straightforward; `medium` is substantial but bounded with a
   known design; `large` needs its own planning handoff; `xlarge` is rare and likely needs epic
   decomposition or deliberately deferred planning.
