---
name: crontab
description:
  Read or change any machine's user crontab (athena, apollo, mac) from any machine
  through the chezmoi cron data and cronctl. Use whenever a task inspects, adds,
  changes, removes, or debugs a cron job.
skill: true
---

Every chezmoi-managed cron job lives in one place: the `cron:` key of
`home/.chezmoidata.yaml` in the chezmoi repo (`bbugyi200/dotfiles`). Each enrolled
machine's crontab holds one marked block that `cronctl sync` installs from that data:

```text
# BEGIN chezmoi-cron (machine: <name>; source: cron: in home/.chezmoidata.yaml; manage with cronctl)
...
# END chezmoi-cron
```

Sync never touches lines outside the block. Machines are named by their `cron.machines`
key, which is also their SSH alias. Every cronctl command has `--help`. Exit codes are
`0` ok, `1` failure, `2` usage or validation error, and `3` when a machine was
unreachable (`pending`) and none failed.

## Read

Never describe a machine's live crontab from memory or from the data alone. Ask:

```bash
cronctl status --all              # live state, unmanaged lines, last run of each job
cronctl list                      # job x machine matrix from the data (offline)
cronctl render <machine>          # the block the data wants there (offline)
cronctl diff <machine>            # wanted block vs live block, plus outside lines
cronctl logs <job> --machine <m>  # tail a job's log (~/.local/state/cron/<job>.log)
```

`status` states are `in_sync`, `drifted` (the live block was hand-edited), `pending`,
`unmanaged` (enrolled, no block yet), `identity_mismatch`, and `failed`. `pending` means
unreachable or not yet applied, not broken. The Mac is often asleep, so expect it to be
`pending`. `cronctl status --all-schedulers` also lists systemd user timers and
LaunchAgents, read-only; cronctl never manages them.

## Write

1. Open the repo: `sase repo open chezmoi -r "<why>"`. Call the printed path
   `<checkout>`. Inside the chezmoi project, your workspace is the checkout.
2. Edit only the `cron:` data in `<checkout>/home/.chezmoidata.yaml`. A job is `name`,
   `machines` (names or `[all]`), `schedule`, `command`, and optionally `description`
   and `enabled: false`. Use `$HOME`, never `/home/...`, `/Users/...`, or
   `/run/user/...`; cronrun derives PATH and the runtime variables.
3. Check the change before committing:

   ```bash
   cronctl check --source <checkout>
   cronctl diff <machine> --source <checkout>   # once per affected machine
   ```

   When a command is new, dry-run it on its machine. Stream the checkout's cronrun so
   the target needs no deployed copy:

   ```bash
   ssh -o BatchMode=yes <machine> "bash -s -- --dry-run <job> '<command>'" < <checkout>/home/bin/executable_cronrun
   ```

   For this machine, run the quoted `bash -s ...` part without `ssh`. A dry run prints
   the resolved environment and never runs the command.

4. Stage post-commit convergence with `/sase_monitor`. The host starts the monitor only
   after your commit is pushed. Run the checkout's cronctl, because this machine's
   `~/bin/cronctl` may predate your commit:

   ```bash
   sase monitor start \
     --reason 'Converge <machines> crontabs to the pushed cron: change' \
     --timeout 15m \
     --start-status 'APPLYING CRONTAB' \
     --stop-status 'APPLIED CRONTAB' \
     --next 'Run `<checkout>/home/bin/executable_cronctl status <machines>` and report each machine as in_sync, pending, or failed. A pending mac converges at its next `chezmoi update -a`.' \
     -- <checkout>/home/bin/executable_cronctl apply <machines>
   ```

   Exit `3` means a machine was unreachable, which is normal for a sleeping Mac. When a
   Mac install fails with "Operation not permitted", Remote Login lacks Full Disk
   Access; Bryan can grant it or run `chezmoi update -a` on the Mac.

5. Finish through `/sase_final` with an explicit commit decision for the chezmoi repo.

Humans run `cronctl edit`, commit and push, then run `chezmoi update -a` on each
affected machine (or `cronctl apply <machine>...` from any machine).

## Rules

- Never write a persistent job with `crontab -e`, `crontab -`, or `ssh ... crontab`.
- Never edit inside the `# BEGIN/END chezmoi-cron` block; sync overwrites it.
- Ephemeral, self-removing automation (such as an epic watchdog) may add marker-tagged
  lines below the block, through a verified safe edit: back up `crontab -l`, append,
  then read the table back.
- A user crontab never needs `sase sudo`.
- The repo is public: no secrets in a job. Reference encrypted files by path only.
- Schedules run in each machine's local time: athena and the Mac use New York, apollo
  uses UTC.
- Time-of-day jobs on `mac` may be skipped while it sleeps.
- Different behaviour on two machines means two jobs; there are no per-machine
  overrides.
- `cron.retire:` is a temporary migration aid listing legacy lines that sync removes.
  Delete it once `cronctl status --all` prints `cron.retire can be deleted`.
