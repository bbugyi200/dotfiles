**My configuration files... These files are synced across multiple dev machines using
[chezmoi].**

[![CI Workflow](https://github.com/bbugyi200/dotfiles/actions/workflows/ci.yml/badge.svg)](https://github.com/bbugyi200/dotfiles/actions/workflows/ci.yml)

[chezmoi]: https://www.chezmoi.io

## Bob Mac Capture cutover

Control-Shift-Command-I is owned by the native Bob Mac Capture app. Hammerspoon no
longer registers that shortcut or carries the retired WebView capture workflow and Lua
capture grammar.

The last known-good pre-cutover chezmoi revision is
`3d841c1e9c6dac9f558709a6ba6ef36082c2c4d4`. To roll back, first turn off **Use
production Control-Shift-Command-I** in Bob Mac Capture Settings so the app returns to
the temporary Control-Shift-Command-O shortcut. Then restore and deploy the old
Hammerspoon feature:

```sh
git restore --source=3d841c1e9c6dac9f558709a6ba6ef36082c2c4d4 -- \
  home/dot_hammerspoon/init.lua \
  home/dot_hammerspoon/task_capture.lua \
  tests/hammerspoon/task_capture_spec.lua
chezmoi apply ~/.hammerspoon
```

Never leave both production hotkeys active during rollback.

## Pomodoro menu bar

Hammerspoon shows the current Bob Pomodoro as one status item in the fixed order **theme
(duration) · 🍅 status**, with `→ stop time` inserted once overdue. The 🍅 sits
immediately before the countdown, separated by exactly one ordinary space, so it
identifies the digits to its right. The 🍅 accompanies current-session countdowns and
overdue status only; the idle item has no tomato. While running, the duration names the
session's scheduled length; the stop time returns once the session is overdue, when the
scheduled endpoint is the useful fact. The stop time is zero-padded 24-hour `HH:MM`,
matching the ledger convention.

| State                               | Example title                          |
| ----------------------------------- | -------------------------------------- |
| Running                             | `DEEP WORK (50m) · 🍅 12:34`           |
| At the stop time                    | `DEEP WORK (50m) · 🍅 00:00`           |
| Recently overdue                    | `DEEP WORK (50m) → 10:15 · 🍅 +00:01`  |
| Last second before escalation       | `DEEP WORK (50m) → 10:15 · 🍅 +09:59`  |
| Ten minutes overdue and later       | `DEEP WORK (50m) → 10:15 · 🍅 OVERDUE` |
| Session without a name              | `UNTITLED (50m) · 🍅 12:34`            |
| Duration unknown (degenerate range) | `DEEP WORK → 10:15 · 🍅 12:34`         |
| No current session                  | `NO POMODORO`                          |
| No session, reminder step           | `NO POMODORO φ 5m`                     |

The duration is the scheduled session length in whole minutes (`5m`, `25m`, `50m`,
`90m`, `120m`), derived from the ledger range with midnight wrap (`2330-0020` → `50m`).
It renders in the ordinary menu-bar foreground, matching the surrounding context. A
zero-length range or invalid input means unknown: the duration is omitted and the
running title falls back to `→ HH:MM`, so every current-session title keeps at least one
time anchor plus the status.

The running countdown digits stay in the ordinary menu-bar foreground for the whole
session, including `00:00` and a session whose duration is unknown. They use a bold
monospaced face, falling back to the regular monospaced face when bold is unavailable.
From the first overdue second through `+09:59`, the `+MM:SS` countdown is alert red
(`#E3413B`) and does not flash. At and after ten minutes overdue, the status is
`OVERDUE` and only that badge flashes between red text and white (`#FFFFFF`) on the same
red. `NO POMODORO` is green (`#30d158`) with no tomato. Between each 60-second flash
step it rests for a Fibonacci number of minutes — 1m, 1m, 2m, 3m, 5m, 8m, … uncapped —
so the steps fall at 1:00, 3:00, 6:00, 10:00, 16:00, 25:00, … counted from when it
appeared while it stays up: bold green text alternates at 1 Hz with a filled pill of
dark forest-green `#062E14` on `#30d158`, the same cadence as `OVERDUE`. Each step names
the rest it just took as `φ Nm` (`NO POMODORO φ 5m`), shown through the whole step in
both frames and gone between steps. The whole label is one pill with a regular-weight
`φ` separator, and the item width changes only at step boundaries. The sequence
re-anchors when the label appears (after a session ends, after a command or parse
failure hides the item, or after a Hammerspoon reload) and when the Mac wakes or unlocks
while it is showing, always restarting at `φ 1m`. Both idle frames pad the pill with a
no-break space at its outer edges so the item never changes width mid-step. Theme,
duration, separator, arrow, stop time, and the tomato stay in the ordinary foreground. A
mid-tone wallpaper directly under a transparent menu bar can undercut any fixed color,
including the system's own labels; turning on Accessibility › Display › Reduce
transparency restores a uniform surface.

Long themes are bounded to 24 Unicode code points including the final ellipsis; the full
theme stays in the tooltip and dropdown. The tooltip leads with `full theme (duration)`
and `Stops at HH:MM`, and the dropdown first item is `full theme (duration) → HH:MM`;
without a known duration they stay as `full theme` and `full theme → HH:MM`. The tooltip
and dropdown carry no tomato and keep the raw `bob pomodoro` line and `Last sync`
details. Without a session the dropdown also shows a disabled
`Next reminder at HH:MM · φ Nm` row previewing the next flash step. At and after ten
minutes overdue, only the `OVERDUE` badge flashes between red text and white-on-red. The
menu re-syncs within about a second when today's daily note changes on disk (an Obsidian
edit, a `bob` command, or a vault-sync pull), polls `bob pomodoro --show-stale` every 60
seconds as a safety net (every 15 seconds if the file watcher cannot start), refreshes
on wake and unlock, offers a manual Refresh item, and re-syncs once when crossing zero.
An empty result shows `NO POMODORO`; command or parse failures hide the item. The
dropdown shows a snapshot taken when it opens, stays open while the title keeps
updating, and shows fresh details when reopened.

## Internet ping menu bar

Hammerspoon shows internet connectivity as one status item beside the Pomodoro item. The
title is a glyph plus a `successes/total` count over the last 20 pings (`✓ 17/20`),
padded to a fixed width so the item never changes size between ticks or tiers. The count
uses Menlo regular; the glyph uses the default menu bar face, and nothing is bold. The
tooltip names the score and the last round-trip time. Opening the item shows the tier, a
20-cell history strip, the score over its span, the last ping, and a Network Settings
shortcut that opens System Settings → Network. If the shortcut cannot open Settings, it
shows a brief alert naming the manual fallback and logs the failure. The dropdown shows
a snapshot taken when it opens, stays open while the title keeps updating, and shows
fresh details when reopened.

One ping stream feeds both this item and the tmux status bar. Hammerspoon is the
preferred producer: it pings 8.8.8.8 every 2 s, and both displays render the same shared
20-sample window, so they always agree. `tmux_ping` only reads while a fresh Hammerspoon
heartbeat exists and falls back to pinging when Hammerspoon is not running, broken, or
unable to write. Handover is self-healing in both directions: Hammerspoon claims the
stream by writing its heartbeat and tmux backs off on its next redraw, while tmux
resumes pinging within about 6 s when Hammerspoon stops. At most one extra ping happens
during a handover. Nobody pings while the Mac is locked: Hammerspoon stops pinging but
keeps refreshing its heartbeat, so tmux does not take over either. With Hammerspoon not
running, tmux keeps working on its own.

| Situation                      | Traffic              |
| ------------------------------ | -------------------- |
| Unlocked, tmux client attached | 1 ping / 2 s         |
| Locked, tmux client attached   | none                 |
| Unlocked, no tmux client       | 1 ping / 2 s         |
| Hammerspoon not running        | tmux pings as before |
| Mac asleep                     | none                 |

Health tiers, checked in this order from the newest sample backward:

| Tier      | Rule                                 | Menu bar              | tmux status            |
| --------- | ------------------------------------ | --------------------- | ---------------------- |
| `stale`   | empty window, or no sample for > 6 s | `◌ 17/20` in gray     | `◌ 17/20` in blue-gray |
| `offline` | 3 or more trailing misses            | white `✗ 0/20` on red | white `✗ 0/20` on red  |
| `down`    | newest ping missed, under 3 trailing | red `✗ 19/20`         | red `✗ 19/20`          |
| `lossy`   | newest answered, under 90% answered  | orange `✓ 17/20`      | amber `✓ 17/20`        |
| `online`  | newest answered, 90%+ answered       | green `✓ 20/20`       | green `✓ 20/20`        |

The shared window lives in `~/tmp/tmux_ping_state`: one LF-terminated line of
`<heartbeat> <producer> <sampled> <results>`, where `heartbeat` is the producer's latest
write, `producer` is `hammerspoon` or `tmux`, `sampled` is when the newest sample was
sent (`0` when empty), and `results` is 1–20 `0` / `1` characters, oldest first (`-`
when empty). Writers replace the file atomically, so readers never lock. A window older
than 40 s is dropped on the next sample, so no window spans a sleep or a long pause.

## Deleting things under `/tmp`

On `athena`, `/tmp` is a **32G tmpfs** — RAM-backed, shared by every numbered sase
workspace, and it has hit `ENOSPC` in practice. Two rules follow from that, and they
matter most for agents, whose shells are initialized from this repo's `~/.profile` and
`~/.config/aliases.sh`.

**1. A cleanup aimed at `/tmp` must reach the real `rm`.** The XDG trash spec requires
the trash to live on the _same filesystem_ as the file, so "trashing" something under
`/tmp` just moves it to `/tmp/.Trash-$UID` and frees zero bytes. There is no longer an
`rm` → `trash` alias in `aliases.sh`, so a plain `rm -rf /tmp/…` is fine today. But
`trash`, `trash-put`, and nvim's file-delete mapping still trash things, and any future
shell that re-aliases `rm` would silently turn every `/tmp` cleanup into a no-op for
space. When in doubt, use `/usr/bin/rm` or `command rm` so no alias or function can
intercept it. `alias r='/bin/rm'` is the shorthand for this.

**2. Trash that does land on a temp filesystem gets purged automatically.**
`~/bin/tmp_trash_empty` empties the trash directories under `/tmp` and `$TMPDIR`;
`~/.profile` runs it in the background with `--periodic` (at most once every 24h). Run
it by hand — `tmp_trash_empty -n -v` to preview, `tmp_trash_empty` to purge — if you
need the space back now.
