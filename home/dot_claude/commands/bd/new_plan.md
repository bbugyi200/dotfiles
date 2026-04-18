---
description: Create beads for every phase in a plan file under a new plan bead
argument-hint: <plan_file_path>
---

Can you help me create one bead for every phase in the @$1 plan file?

These beads should all be children of a new plan bead that you should also create. The plan bead should be linked to the
plan file using the `sase bead create` command's `--type plan(<plan_file>)` option. Also, add the bead ID of the plan to
a new frontmatter field called `bead_id` in the plan file.

Make sure that each phase bead has the appropriate dependencies set up.
