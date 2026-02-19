---
description: Create beads for every phase in a plan file under a new epic
argument-hint: <plan_file_path>
---

Can you help me create one bead for every phase in the @$1 plan file?

These beads should all be children of a new epic bead (make sure this bead has a type of "epic" and not, for example,
"feature") that you should also create. The epic bead should be linked to the plan file using the `bd create` command's
`--design` option. Also, add the bead ID of the epic to a new frontmatter field called `bead_id` in the plan file.

Make sure that each phase bead has the appropriate dependencies set up.
