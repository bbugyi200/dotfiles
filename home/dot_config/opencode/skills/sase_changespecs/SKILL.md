---
name: sase_changespecs
description:
  Compatibility shim for /sase_patches. Use when a task specifically mentions the legacy
  ChangeSpec name or asks to validate legacy `sase changespec` aliases.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use sase_changespecs --reason "<one-line reason for using this skill>"
```

Compatibility reference for the legacy `/sase_changespecs` skill.

Use `/sase_patches` for normal Patch work. The canonical command group is `sase patch`;
`sase changespec` remains a compatibility alias with the same behavior, exit codes, and
machine-readable output shape.

## Legacy To Canonical Map

| Legacy form                           | Canonical form                       |
| ------------------------------------- | ------------------------------------ |
| `/sase_changespecs`                   | `/sase_patches`                      |
| `sase changespec current -f markdown` | `sase patch current -f markdown`     |
| `sase changespec search '<query>'`    | `sase patch search '<query>'`        |
| `sase changespec search '&<name>'`    | `sase patch search '&<name>'`        |
| `sase changespec ref add -c <name>`   | `sase patch ref add --patch <name>`  |
| `sase changespec ref list -c <name>`  | `sase patch ref list --patch <name>` |
| `sase changespec ref rm -c <name>`    | `sase patch ref rm --patch <name>`   |
| `sase changespec migrate-extension`   | `sase patch migrate-extension`       |
| `-c` / `--changespec` Patch target    | `--patch`                            |
| `COMMITS:` section                    | `STITCHES:` section                  |

Legacy `COMMITS:` sections are read as stitches. New Patch sections use `STITCHES:`. Use
"commit" only for real Git/Mercurial commits, SHAs, VCS logs, commit statistics, the
`sase commit` command, and the act of committing.
