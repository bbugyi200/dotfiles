---
name: sase_notify
description:
  Inspect SASE notifications and notification inbox entries. Use when the user asks about SASE notifications, the
  notification inbox, axe notifications/errors, plan or question notifications, or "the notification I just got".
---

Quick reference for inspecting SASE notifications. This skill is read-only: do not dismiss, mute, snooze, mark read, or
otherwise mutate notifications unless the user explicitly asks and a SASE CLI command exists for that action.

## Primary command

```bash
sase notify list -j -l 20
```

This prints a stable-shape JSON array of recent notifications, newest first. Each row has: `id`, `timestamp`, `age`,
`sender`, `priority`, `notes`, `files`, `action`, `action_data`, `read`, `dismissed`, `silent`, `muted`, and
`snooze_until`.

Prefer JSON for discovery and filtering. Useful examples:

- `sase notify list -j -l 20 --sender axe` — recent axe notifications.
- `sase notify list -j -l 20 --unread` — unread notifications only.
- `sase notify list -j -l 20 --sender axe --unread` — unread axe notifications.
- `sase notify list -j -l 20 -q '<text>'` — search notification ids, senders, notes, files, actions, and action data.
- `sase notify list -j -l 20 --all` — include dismissed notifications.

If the list is empty, say "no matching notifications found" plainly. Do not fabricate notification context.

## Exact inspection

After choosing a notification id, inspect it directly:

```bash
sase notify show --id <notification_id>
```

The default output is markdown and includes the notification id, timestamp, age, sender, priority, notes, attached
files, action, action data, and state flags. Use JSON when automation needs the exact projection:

```bash
sase notify show --id <notification_id> -f json
```

If `show` reports that the notification was not found, say so plainly instead of falling back to an unrelated
notification.

## Axe digest notifications

For axe digest or error notifications, the actionable details are usually in an attached digest file. After identifying
the notification:

1. Check `files` for an error digest path.
2. Check `action_data.error_report_path` if `files` is empty or ambiguous.
3. Read the attached file before summarizing the actual error details.

Distinguish notification notes from attached file contents. The notification notes are the inbox summary; the digest
file is the detailed report.

## How to summarize

- Cite the notification `id`, `sender`, and `timestamp` you used.
- Mention whether the notification is unread, dismissed, silent, muted, snoozed, or priority when that state affects the
  answer.
- For axe digests, cite the attached file path you read and summarize only what it contains.
- Keep direct quotes short; prefer concise paraphrases unless exact wording matters.
- Report uncertainty and missing data directly. Do not infer hidden notification contents from sender names or actions.
