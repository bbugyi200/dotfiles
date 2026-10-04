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
red. `NO POMODORO` is green (`#30d158`) with no tomato. It flashes for its first minute
on screen, then for one minute every ten minutes while it stays up: bold green text
alternates at 1 Hz with a filled pill of dark forest-green `#062E14` on `#30d158`, the
same cadence as `OVERDUE`. The cycle re-anchors when the label appears (after a session
ends, after a command or parse failure hides the item, or after a Hammerspoon reload)
and when the Mac wakes or unlocks while it is showing. Both idle frames pad the text
with a no-break space on each side so the item never changes width. Theme, duration,
separator, arrow, stop time, and the tomato stay in the ordinary foreground. A mid-tone
wallpaper directly under a transparent menu bar can undercut any fixed color, including
the system's own labels; turning on Accessibility › Display › Reduce transparency
restores a uniform surface.

Long themes are bounded to 24 Unicode code points including the final ellipsis; the full
theme stays in the tooltip and dropdown. The tooltip leads with `full theme (duration)`
and `Stops at HH:MM`, and the dropdown first item is `full theme (duration) → HH:MM`;
without a known duration they stay as `full theme` and `full theme → HH:MM`. The tooltip
and dropdown carry no tomato and keep the raw `bob pomodoro` line and `Last sync`
details. At and after ten minutes overdue, only the `OVERDUE` badge flashes between red
text and white-on-red. The menu polls `bob pomodoro --show-stale` every 15 seconds,
refreshes on wake and unlock, offers a manual Refresh item, and re-syncs once when
crossing zero. An empty result shows `NO POMODORO`; command or parse failures hide the
item.

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
