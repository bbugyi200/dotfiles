---
name: bob_ref
description:
  Check Bryan's Bob reference library (what he has read, is reading, or plans to read)
  and read his annotations through `bob ref`. Use before recommending articles, papers,
  or other reading to Bryan, and whenever you need his notes on a reference.
---

Before doing anything else, run this command to record that you are using this skill:

```bash
sase skill use bob_ref --reason "<one-line reason for using this skill>"
```

Use this skill when you recommend reading to Bryan or need his notes on a reference.
Check the library first, label what you find honestly, and never write to the vault.

## Rules

- Batch the lookup. Before recommending reading, put every candidate (URL, arXiv ID,
  DOI, or title) into **one** call:

  ```bash
  printf '%s\n' CANDIDATE1 CANDIDATE2 | bob ref find - -f json
  ```

- Interpret each result by its `verdict` first, then by `reading_state`:
  - `in_library` with `reading_state: finished`: drop it, or cite it as already read.
  - `in_library` with `reading_state: dropped`: drop it unless there is a new reason to
    reopen it.
  - `in_library` with `reading_state: queued` or `started`: keep it only if relevant,
    labeled "already in your library (queued since …)". `era: legacy` means the 2025
    zorg backlog. A row with `superseded_by` set was replaced by a newer capture; prefer
    the newer note.
  - `possible`: only title candidates. Confirm with `bob ref show <path>` before calling
    one a duplicate.
  - `in_intake`: captured, not yet scanned into the library.
  - `not_found`: absent from `ref/` only. Never claim Bryan has not read it.
- For taste, list what he finished from outside sources:

  ```bash
  bob ref list -o external -R finished -g -f json
  ```

  `agent-report` notes (`ref/chat`) are SASE research reports: a topic-interest signal,
  not reading history.

- For Bryan's own thoughts on one reference:

  ```bash
  bob ref show <REF> -c -f markdown
  ```

- Respect the cap. Honor `truncated` in the envelope, page with `--limit` instead of
  dumping everything, and never paste `list -A` output into a prompt.
- Read-only. Never edit `~/bob`. Never run `bob ref clip`, `create`, `scan`, or `sync`
  unless Bryan asks. Propose `bob ref create <URL>` lines (add `-L` to also narrate) for
  him instead.
- End reading-list reports with: "Library check: N of M candidates already in your
  library (K finished)."

## Example

```bash
printf '%s\n' https://hugobowne.substack.com/p/harness-engineering-why-agent-context \
  https://arxiv.org/abs/1706.03762 | bob ref find - -f json
```

The first query returns `in_library` with `reading_state: queued` and `era: legacy`; the
second returns `not_found`. Recommend only Attention Is All You Need, note the Harness
engineering piece as "already in your library (queued since 2026-03-29, legacy
backlog)", and close with: "Library check: 1 of 2 candidates already in your library (0
finished)."
