---
type: reference
parent: AGENTS.md
description: Bob vault note conventions, git sync, and recovery runbooks.
---

# Obsidian

`~/bob/` is Bryan's Obsidian vault ("my notes"); zorg is retired. New Markdown notes
must include a `parent` frontmatter field linking to another Markdown note in the vault.

- **Sync:** `bob vault-sync` reconciles the vault with its Git remote across athena,
  apollo, and the MacBook. Inspect the last run with `bob vault-sync status --json`.
- **Automation:** athena/apollo use the user service `bob-vault-sync.service`; the
  MacBook uses LaunchAgent `com.bbugyi.bob-vault-sync`. athena's `bob nightly` syncs,
  runs `bob move-done-tasks`, then syncs again; both commands share `bob_sync.lock`.
- **Conflicts:** supported conflicts keep the remote version in place and preserve local
  copies under `_conflicts/`, logged in `_conflicts/sync_conflicts.md`.
- **Coverage:** `lit_review/` and `xlib/` are gitignored; git sync does not transfer
  them. Custom `bob-*` plugins are also gitignored; deploy from the `bob-plugins` source
  repo with `bob plugins sync`.

Obsidian Sync is retired. Keep exactly one sync engine active: before re-enabling Sync,
stop the git sync services/LaunchAgent and gate `bob nightly`. Bryan decides when to
unlink Sync and remove its retained files.

In the **bob-cli repo**, consult `docs/vault-git-sync.md` for operations, recovery, and
Highlights intake; use `docs/obsidian-sync-exclusions.md` only for historical Obsidian
Sync exclusion procedures.
