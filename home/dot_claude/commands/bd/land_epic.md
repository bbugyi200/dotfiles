---
description: Close an epic bead after verifying that all the work associated with it is complete.
argument-hint: <bead_id>
---

Can you help me verify that all the work associated with the bead with ID @$1 is complete?

Actually read through the source code and the git commits that are associated with that bead's work (they should have
the bead ID in the commit message) and ensure all of the work that the previous agents say is complete, is actually
complete. Also, run `bd show` on every child bead an ensure that any notes on those beads have been addressed.

If not, plan out the remaining work and complete it. Otherwise, close the bead using the `bd close` command. Finally,
run the `just pyvision` command AFTER closing the epic bead (some symbols can be ignored while an epic is open) to make
sure we didn't leave any unused code behind.
