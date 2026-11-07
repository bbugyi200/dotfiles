---
type: reference
parent: AGENTS.md
description:
  Read before reading or changing any machine's crontab - the chezmoi cron data is the
  only source of truth; use cronctl and the /crontab skill.
---

# Crontabs

The `cron:` key of `home/.chezmoidata.yaml` in the chezmoi repo is the only source of
truth for every enrolled machine's user crontab (athena, apollo, and mac, named by their
SSH aliases in [[tailnet.md]]). Use the `/crontab` skill for the full read and write
flow.

- **Block:** each machine's crontab holds one block between `# BEGIN chezmoi-cron` and
  `# END chezmoi-cron`. `cronctl sync` installs it from `~/.config/cron/managed.crontab`
  and never touches lines outside it. `chezmoi update -a` runs sync when the machine's
  block changes, and `cronctl apply` converges any machine from any machine.
- **Jobs:** every job runs through `~/bin/cronrun`, which derives PATH and the runtime
  variables, guards overlaps, logs to `~/.local/state/cron/<job>.log`, and mails only
  failures.

| Command                                   | Use                                     |
| ----------------------------------------- | --------------------------------------- |
| `cronctl status --all`                    | Live state of every machine (read-only) |
| `cronctl list` / `cronctl render <m>`     | The data, offline                       |
| `cronctl check --source <checkout>`       | Validate an uncommitted change          |
| `cronctl diff <m> [--source <checkout>]`  | Wanted vs live block                    |
| `cronctl logs <job> --machine <m>`        | Tail a job's log                        |
| `cronctl apply <m>...`                    | Converge machines to the pushed source  |
| `cronctl run <job>` / `cronrun --dry-run` | Run now (real side effects) / check     |
| `cronctl edit`                            | Human replacement for `crontab -e`      |

## Rules

- Never describe a live crontab from memory; run `cronctl status` or `cronctl diff`.
- Never write a persistent job with `crontab -e`, `crontab -`, or `ssh ... crontab`, and
  never edit inside the managed block.
- Ephemeral, self-removing automation may add marker-tagged lines below the block
  through a verified safe edit.
- No secrets in job definitions; the repo is public.
- Schedules use each machine's local time, and `mac` skips time-of-day jobs while it
  sleeps. `pending` means unreachable or not yet applied.
- Different per-machine behaviour means two jobs.
