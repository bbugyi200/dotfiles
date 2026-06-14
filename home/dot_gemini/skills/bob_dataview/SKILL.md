---
name: bob_dataview
description: Run read-only Obsidian Dataview queries against Bryan's Bob vault via `bob dataview`.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skills log bob_dataview --reason "<one-line reason for using this skill>"
```

Use this skill when you need read-only Dataview access to Bryan's Bob vault (`~/bob`).

## Rules

- Use `bob dataview` instead of manually parsing large parts of the vault.
- Treat this skill as read-only. Do not modify Bob vault files.
- Prefer `--query-file -` or a temporary query file for multiline DQL.
- Use `--format markdown` when the result is going into a prompt, transcript, or human-readable answer.
- Use `--format paths` only when you need source expression results or path-only output.
- Omit `--bob-dir` for Bryan's default vault. Include `--bob-dir <path>` only when the user asks for a nondefault vault.
- Treat command failures as actionable diagnostics. Fix the DQL, vault path, or command invocation; do not use failure
  as permission to scan and parse the whole vault ad hoc.

## Example

Put the query in a file:

```dataview
TABLE WITHOUT ID title AS Title, url AS URL
FROM #ai/reference
WHERE url
SORT title ASC
```

Run it as Markdown:

```bash
bob dataview --format markdown --query-file /path/to/query.dql
```
