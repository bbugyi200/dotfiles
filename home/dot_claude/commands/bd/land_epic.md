---
description: Close an epic bead after verifying that all the work associated with it is complete.
argument-hint: <bead_id>
---

Can you help me verify that all the work associated with the bead with ID @$1 is complete? Don't just check to make sure
that all child beads are closed. Actually, read through the source code and the git commits that are associated with
that bead's work (they should have the bead ID in the commit message) and ensure all of the work that the previous
agents say is complete, is actually complete. If not, plan out the remaining work and complete it. Otherwise, close the
bead using the `bd close` command.
