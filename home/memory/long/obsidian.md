---
description: Obsidian vault, notes workflow, and obsidian-headless/ob usage.
---

# Obsidian

`~/bob/` is my Obsidian vault. When I refer to "my notes", I usually mean Markdown notes in this vault.

This machine uses `obsidian-headless` through the `ob` command to support Obsidian Sync without requiring a full GUI
Obsidian session for local workflows.

The previous zorg migration is useful historical context, but Bryan has fully switched to Obsidian and does not use zorg
anymore.

When creating new Markdown notes under `~/bob/`, include a `parent` frontmatter field that links to another Markdown
file in `~/bob/`.
