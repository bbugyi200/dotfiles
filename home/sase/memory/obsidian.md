---
type: reference
parent: AGENTS.md
description: Obsidian vault, notes workflow, and obsidian-headless/ob usage.
---

# Obsidian

`~/bob/` is my Obsidian vault. When I refer to "my notes", I usually mean Markdown notes
in this vault.

Vault sync is git-only now. `bob vault-sync` reconciles `~/bob` against the vault Git
remote and is the live sync channel between athena, apollo, and the MacBook. athena and
apollo run `bob-vault-sync.service`, which executes `~/bin/bob_vault_sync_watch`; the
MacBook runs the `com.bbugyi.bob-vault-sync` LaunchAgent. athena's 03:30 `bob nightly`
cron runs `bob vault-sync`, `bob move-done-tasks`, then `bob vault-sync`.
`bob vault-sync` shares `bob_sync.lock` with `bob nightly`, so these maintenance paths
do not mutate the vault concurrently. See bob-cli's `docs/vault-git-sync.md` for the
full runbook.

Obsidian Sync is retired as the automation path for `~/bob`, but some files are kept
until Bryan chooses to unlink it. On athena, `ob-sync-bob.service` used to run
`~/.local/bin/ob-sync-bob-poll`, a bash loop that started
`ob sync --path /home/bryan/bob` in a fresh process every 30 seconds with a 120-second
timeout; that meant config was re-read every cycle. That service did not participate in
`bob_sync.lock`, so any future Sync relink must stop the git sync services/LaunchAgent
and gate `bob nightly` first. Exactly one sync engine should run against `~/bob`.

Obsidian Sync exclusions are device-local. The headless client stores `ignoreFolders`
under `~/.config/obsidian-headless/sync/<vault-id>/config.json`, set with
`ob sync-config --excluded-folders` as a whole-list replacement. Desktop Obsidian stores
its own exclusions in app IndexedDB outside the vault, not in `.obsidian/sync.json`. The
value is prefix-matched and case-sensitive; athena's retained exclusion was
`["old_lib"]`. Exclusions never delete already-synced remote data, so remote deletions
must be pushed before excluding a folder. Obsidian Sync Standard was limited to 1 GB
total storage, 5 MB max file size, about 1 month of version history, and 1 synced vault;
version history and attachments counted toward the 1 GB ceiling. The headless client's
offline remote inventory lives in `~/.config/obsidian-headless/sync/<vault-id>/state.db`
table `server_files`, whose JSON `data` includes `path`, `size`, `folder`, and
`deleted`. See bob-cli's `docs/obsidian-sync-exclusions.md` for the retained historical
procedure.

The previous zorg migration is useful historical context, but Bryan has fully switched
to Obsidian and does not use zorg anymore.

When creating new Markdown notes under `~/bob/`, include a `parent` frontmatter field
that links to another Markdown file in `~/bob/`.
