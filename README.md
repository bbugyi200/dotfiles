**My configuration files... These files are synced across multiple dev machines using
[chezmoi].**

[![CI Workflow](https://github.com/bbugyi200/dotfiles/actions/workflows/ci.yml/badge.svg)](https://github.com/bbugyi200/dotfiles/actions/workflows/ci.yml)

[chezmoi]: https://www.chezmoi.io

## SSH clipboard

On athena and apollo, remote copies in tmux go through the local tmux buffer and OSC 52
to the attached terminal. Use xc to copy, xp to read the Mac clipboard over SSH, and
clip2mac to push the last remote tmux copy manually. X11 forwarding is opt-in for GUI
apps with BAS_X11=1 bas athena. Run ssh_clip_doctor in a broken pane before restarting
anything. See the
[tailnet SSH clipboard runbook](https://github.com/bbugyi200/tailnet/blob/main/mac/ssh-clipboard-2026-11.md).

## DigitalOcean doctl on athena

On athena, `doctl_login` sets up or re-checks the token used for Apollo recovery. Run
`doctl_login` to check the connection, `doctl_login -r` to rotate the token, or
`doctl_login -l` to remove it. Removal does not revoke the token; revoke it in the
DigitalOcean control panel. Agents may run bare `doctl_login`; without a terminal, it
performs a read-only connection check.

## Agent video tools

On athena and apollo, agents probe, view, OCR, transcribe, and edit video with a shared
`/video` skill. `whisper_run` wraps `whisper-ctranslate2` (CUDA on athena, CPU on
apollo, default model `large-v3-turbo`). The monthly `run_onchange_install_video_tools`
installer keeps `yt-dlp`, Whisper, and PySceneDetect current via `uv tool`; system
packages (ffmpeg, tesseract, mediainfo, exiftool, mkvtoolnix, auto-editor) come from
reviewed `/sase_sudo` requests. Both hosts get the extras (PySceneDetect and
auto-editor); apollo also gets ffmpeg and tesseract, which athena already had.

## Bob Mac Capture cutover

Control-Shift-Command-I (capture) and Control-Shift-Command-O (Bob Refs) are owned by
the native Bob Mac Capture app. Hammerspoon no longer registers the capture shortcut or
carries the retired WebView capture workflow and Lua capture grammar.

The last known-good pre-cutover chezmoi revision is
`3d841c1e9c6dac9f558709a6ba6ef36082c2c4d4`. To roll back, first turn off **Use
production Control-Shift-Command-I** in Bob Mac Capture Settings so the app returns to
the Control-Shift-Command-R development capture shortcut. Then restore and deploy the
old Hammerspoon feature:

```sh
git restore --source=3d841c1e9c6dac9f558709a6ba6ef36082c2c4d4 -- \
  home/dot_hammerspoon/init.lua \
  home/dot_hammerspoon/task_capture.lua \
  tests/hammerspoon/task_capture_spec.lua
chezmoi apply ~/.hammerspoon
```

Never leave both production hotkeys active during rollback. A targeted
`chezmoi apply ~/.hammerspoon` does not run chezmoi scripts, so follow it with
Hammerspoon's menu-bar **Reload Config** or a full apply.

## Hammerspoon config restarts

A full `chezmoi apply`/`chezmoi update` on macOS restarts Hammerspoon when any Lua file
under `home/dot_hammerspoon/` changed. The hook is
`home/.chezmoiscripts/run_onchange_after_restart_hammerspoon.tmpl`. It does nothing when
Hammerspoon is not running, since the new files load on its next launch. After stopping
Hammerspoon, the hook waits for LaunchServices to release the old instance and retries
the relaunch a few times; only if all attempts fail does the apply report an error, in
which case you start Hammerspoon manually. A new Hammerspoon Lua module must be added to
the hook's hash list: `tests/bash/hammerspoon_restart_hook_test.sh` fails until it is. A
targeted `chezmoi apply ~/.hammerspoon` does not run scripts, so use Hammerspoon's
menu-bar **Reload Config** or run a full apply instead.

## Region screen recording

Press **⌃⌥⇧V** to record a selected screen region. The selector is the same drag /
⌘-drag / corner-handle picker as the screenshot chord (**⌃⌥⇧S**), drawn in recording
red. Enter starts the recording; ⌘Enter also saves that rectangle as the default. **M**
toggles the microphone (off by default). Esc or ⌃⌥⇧V cancels the selector. Press ⌃⌥⇧V
again while recording to stop and upload.

Selector keys:

| Key     | Action                                            |
| ------- | ------------------------------------------------- |
| Drag    | Draw a new box                                    |
| ⌘-drag  | Move the box                                      |
| Corners | Resize                                            |
| F       | Select the whole screen                           |
| W       | Snap to the frontmost window under the pointer    |
| ⏎       | Start recording                                   |
| ⌘⏎      | Start and save this rectangle as the default      |
| M       | Toggle microphone for this clip                   |
| K       | Cycle key overlay: all → chords → off (this clip) |
| Esc     | Cancel                                            |
| ⌃⌥⇧V    | Cancel (same chord)                               |

While the screenshot picker is open, ⌃⌥⇧V starts a recording of that exact region. While
the recording picker is open, ⌃⌥⇧S captures a still of that exact region.

The recording chrome (corner brackets, hairline, and timer pill) sits outside the
recorded pixels. Cursor and click flashes are on; system audio is not captured. A
10-minute cap stops the clip automatically, with an orange warning from 9:00. The menu
bar shows the timer, a spinner while the clip encodes and uploads, then a green check
for 3 seconds.

Every live, non-probe recording also shows a fading line of the keys you type, inside
the recorded region at the bottom-right. This is an explicit exception to the
chrome-outside rule: the keycast is content, not chrome. It shows all keys by default,
with printable runs coalesced, repeats collapsed, and entries expiring after about 2 s.
The **Show Keys** menu row cycles all → chords → off for the current clip. The recorder
chords (⌃⌥⇧V, ⌃⌥⇧S) are never shown. Secure input and password apps (1Password, Keychain
Access, Passwords, Bitwarden) blank the overlay and show a dim `🔒 secure` chip instead.

Privacy warning: shown keys are baked into the video pixels and copied to apollo and
athena with the clip. Use K → off, the **Show Keys** menu row, or Discard for sensitive
clips. If passwords are routinely typed in clips, flip `KEYS_DEFAULT` to `"chords"` in
`screen_recording_model.lua`.

Clips land at `~/tmp/screencasts/YYYYMMDD_HHMMSS.mp4` on the Mac, apollo, and athena.
Apollo is skipped below 5 GiB free and pruned to at most 2 GiB of clips. Agents fetch
clips with `svid_fetch` or the `#svid` macro.

`macrec` is the detached recorder. Useful commands:

| Command          | What it does                              |
| ---------------- | ----------------------------------------- |
| `macrec status`  | Live session plus recent clips            |
| `macrec retry`   | Re-upload the newest failed session       |
| `macrec recover` | Take over an orphaned session and ship it |
| `macrec doctor`  | Run the on-device capture probes          |

A recording survives a Hammerspoon restart: `screen_recorder.lua` re-adopts a live
session from `macrec status`, or recovers an orphan, and never overwrites newer
clipboard content.

A failed upload leaves `⚠ rec` in the menu bar with Retry, Reveal, Show Log, and
Dismiss. Dismiss records `macrec ack ID dismissed`, so that failure stays resolved
across status refreshes and Hammerspoon restarts. `macrec doctor` probe sessions are
self-tests: they never draw recording chrome, notify, or count as failed or orphaned
recordings, and `macrec retry`/`recover` skip them when picking the newest session.

See the
[tailnet screen recording runbook](https://github.com/bbugyi200/tailnet/blob/main/mac/screen-recording-2026-11.md).

## Pomodoro menu bar

Hammerspoon shows the current Bob Pomodoro as one status item in the fixed order
**swatches theme (duration) · 🍅 status**, with `→ stop time` inserted once overdue and
`⇥ last end · worked total` while idle. The `⇥` mark is the end of today's last closed
Pomodoro, from bob's `[LAST HHMM-HHMM]` token; any closed timed row counts, including
off-clock sessions. It uses the stop time's ordinary-foreground, monospaced, zero-padded
24-hour style, and it never flashes. Each non-exempt theme of the running session gets a
colored `■` (`hs.styledtext`) before the name, using that hue's light or dark hex for
the menu-bar appearance. Composite names such as `BOB + DECKS` get one square per
component. The title text itself is never tinted: red and green already mean overdue and
worked. Hue comes from `bob themes list -a -f json` on the same re-sync as
`bob pomodoro --show-stale --worked --last` and is cached until the next re-sync. An
exempt theme, a name the catalog does not know, or a failed/unparsable themes call means
no swatch and an unchanged title. The 🍅 sits immediately before the countdown,
separated by exactly one ordinary space (plus the padded overdue status's own
no-break-space margin), so it identifies the digits to its right. The 🍅 accompanies
current-session countdowns and overdue status only; the idle item has no tomato. While
running, the duration names the session's scheduled length; the stop time returns once
the session is overdue, when the scheduled endpoint is the useful fact. The stop time is
zero-padded 24-hour `HH:MM`, matching the ledger convention.

| State                               | Example title                            |
| ----------------------------------- | ---------------------------------------- |
| Running                             | `■ DEEP WORK (50m) · 🍅 12:34`           |
| Composite running                   | `■ ■ BOB + DECKS (50m) · 🍅 12:34`       |
| At the stop time                    | `■ DEEP WORK (50m) · 🍅 00:00`           |
| Recently overdue                    | `■ DEEP WORK (50m) → 10:15 · 🍅 +00:01`  |
| Last second before escalation       | `■ DEEP WORK (50m) → 10:15 · 🍅 +09:59`  |
| Ten minutes overdue and later       | `■ DEEP WORK (50m) → 10:15 · 🍅 OVERDUE` |
| Exempt or unknown theme             | `GTD (50m) · 🍅 12:34`                   |
| Session without a name              | `UNTITLED (50m) · 🍅 12:34`              |
| Unnamed session with linked tasks   | `sase (50m) · 🍅 12:34`                  |
| Duration unknown (degenerate range) | `■ DEEP WORK → 10:15 · 🍅 12:34`         |
| No session yet today                | `0h0m`                                   |
| No current session                  | `⇥ 14:35 · 1h35m`                        |
| No session, reminder step           | `⇥ 14:35 · 1h35m φ 5m`                   |

The duration is the scheduled session length in whole minutes (`5m`, `25m`, `50m`,
`90m`, `120m`), derived from the ledger range with midnight wrap (`2330-0020` → `50m`).
It renders in the ordinary menu-bar foreground, matching the surrounding context. A
zero-length range or invalid input means unknown: the duration is omitted and the
running title falls back to `→ HH:MM`, so every current-session title keeps at least one
time anchor plus the status.

The running countdown digits stay in the ordinary menu-bar foreground for the whole
session, including `00:00` and a session whose duration is unknown. They use a bold
monospaced face, falling back to the regular monospaced face when bold is unavailable.
From `+00:01` through `+09:59`, the `+MM:SS` countdown is alert red (`#E3413B`). For the
first ten seconds of every overdue minute — `+00:01`–`+00:10`, then `+01:00`–`+01:10`,
`+02:00`–`+02:10`, …, `+09:00`–`+09:10` — it flashes at 1 Hz like the `OVERDUE` badge:
red text alternating with white (`#FFFFFF`) on the same red, in the countdown's
monospaced face. For the rest of each minute (from `:11`) it holds steady red. The count
carries one no-break space on each side in every overdue frame, the same padding as the
`OVERDUE` badge, so the item keeps one width from `+00:01` through `+09:59` and never
shifts when a pulse starts or stops. At and after ten minutes overdue, the status is
`OVERDUE` and that badge flashes between red text and white on the same red. Without a
session, the item shows today's worked total as `<H>h<M>m`, supplied by bob's
`[WORKED <minutes>m]` line from today's closed Pomodoros. The label is green (`#30d158`)
with no tomato; for example, `95m` is `1h35m`. Between each 10-second flash step it
rests for a Fibonacci number of minutes — 1m, 1m, 2m, 3m, 5m, 8m, … uncapped — so the
steps fall at 1:00, 2:10, 4:20, 7:30, 12:40, 20:50, … counted from when it appeared
while it stays up: bold green text alternates at 1 Hz with a filled pill of dark
forest-green `#062E14` on `#30d158`, the same cadence as `OVERDUE`. Each step names the
rest it just took as `φ Nm` (`⇥ 14:35 · 1h35m φ 5m`), shown through the whole step in
both frames and gone between steps. The whole label is one pill with a regular-weight
`φ` separator. Its width changes at reminder-step boundaries and when today's worked
total changes, which only happens when the ledger changes. The sequence re-anchors when
the label appears (after a session ends, after a command or parse failure hides the
item, or after a Hammerspoon reload) and when the Mac wakes or unlocks while it is
showing, always restarting at `φ 1m`. Both idle frames pad the pill with a no-break
space at its outer edges so the item never changes width mid-step. Theme, duration,
separator, arrow, stop time, `⇥` mark, and the tomato stay in the ordinary foreground.
Theme swatches are the one exception: they use the catalog hue's light/dark hex and
never color the name. A mid-tone wallpaper directly under a transparent menu bar can
undercut any fixed color, including the system's own labels; turning on Accessibility ›
Display › Reduce transparency restores a uniform surface.

Long themes are bounded to 24 Unicode code points including the final ellipsis; the full
theme stays in the tooltip and dropdown. The tooltip leads with `full theme (duration)`
and `Stops at HH:MM`, and the dropdown first item is `full theme (duration) → HH:MM`;
without a known duration they stay as `full theme` and `full theme → HH:MM`. The tooltip
and dropdown carry no tomato and keep the raw `bob pomodoro` line and `Last sync`
details. Without a session, the tooltip is `No current Pomodoro · 3h50m worked today`
plus a second line `BUILD (5m) ended at 14:35` when a last end is known (without a known
duration it reads `BUILD ended at 14:35`). Without a session, the dropdown's first row
names today's worked total, the second row names the last closed session as
`BUILD (5m) ended at 14:35`, and it also shows a disabled
`Next reminder at HH:MM · φ Nm` row previewing the next flash step. At and after ten
minutes overdue, the `OVERDUE` badge flashes between red text and white-on-red; in every
state only the status run ever flashes, and the swatches, theme, duration, arrow, stop
time, separator, `⇥` mark, and tomato never do. The menu re-syncs within about a second
when today's daily note changes on disk (an Obsidian edit, a `bob` command, or a
vault-sync pull), polls `bob pomodoro --show-stale --worked --last` every 60 seconds as
a safety net (every 15 seconds if the file watcher cannot start), refreshes on wake and
unlock, offers a manual Refresh item, and re-syncs once when crossing zero. A
`[WORKED <minutes>m]` result shows the worked total, an empty result falls back to
`NO POMODORO`, and command or parse failures hide the item. The dropdown shows a
snapshot taken when it opens, stays open while the title keeps updating, and shows fresh
details when reopened. The Mac's installed `bob` must support `--worked` before this
config is applied; a `bob` that rejects `--last` (exit 2) gets one retry without it, so
the item keeps the worked-only title until `bob` is upgraded.

## Highlights tab keys

While Highlights is frontmost, a `\` leader closes tabs in its focused window:

| Keys | Action                                           |
| ---- | ------------------------------------------------ |
| `\\` | Close every other tab, keeping the selected tab  |
| `\<` | Close every tab to the left of the selected tab  |
| `\>` | Close every tab to the right of the selected tab |
| `\u` | Reopen the last batch these keys closed          |

Press `\`, then the second key within 1 s. The leader stays active only while Highlights
is frontmost and only touches the focused window; other Highlights windows stay open.
`\` types normally in text fields and in the Bob Refs panel. A save dialog stops the run
with the dialog left up. These closes skip Bob Refs' ⇧⌘T closed-tab stack, and `\u`
reopens only the last batch (in memory only; a reload forgets it). Hammerspoon owns this
binding instead of Bob Mac Capture because the leader needs an active event tap, and
because a full apply restarts Hammerspoon while the app would need a signed rebuild.

## Highlights page keys

While the PDF view in Highlights has focus, use these keys to move between physical PDF
pages and scroll through the document:

| Keys   | Action                        |
| ------ | ----------------------------- |
| `gg`   | Jump to the first page        |
| `G`    | Jump to the last page         |
| `<N>g` | Jump to page N                |
| `<N>G` | Jump to page N                |
| `⌃O`   | Jump back through jumps       |
| `⌃I`   | Jump forward again after `⌃O` |

Each jump goes to the top of the page. N is the physical page number shown in
Highlights' `Page N of M` title, not a printed page label. A count outside `1–M` shows
an alert and does not move. Finish a sequence within 1 s of its previous key.

For example, on page 30, `2g` jumps to page 2 and `⌃O` returns to page 30. `⌃O` keeps
walking back through earlier jumps; when there are no earlier jumps it shows
`No earlier page`. `⌃I` goes forward again through the pages `⌃O` walked back over; when
there are no later pages it shows `No later page`. A new `gg`, `G`, or `<N>g` jump
clears the pages ahead. The history is per PDF, records only jumps made with these keys,
and lives in memory, so a Hammerspoon reload or restart may forget it. `⌃I` is
Control-I, so Highlights' `⌃⇥` tab switching still works.

These keys type normally in text fields, the Bob Refs panel, and windows without a PDF.
Keep Bob Mac Capture's “In Highlights, open Bob Refs with” setting at Command-O or Off;
Control-O would collide with `⌃O`.

### Scroll keys

| Keys        | Action                                       |
| ----------- | -------------------------------------------- |
| `⌃D` / `⌃U` | Scroll down or up half the visible height    |
| `⌃E` / `⌃Y` | Scroll down or up about one line (20 points) |

Holding a key keeps scrolling. The top and bottom stop scrolling quietly. These scrolls
are not jumps, so `⌃O` does not return across them. A count before a scroll key is
ignored, and scroll keys do nothing while a page jump or tab close is running.

Scroll keys pass through in text fields, the Bob Refs panel, and windows without a PDF.
Control-D, Control-E, and Control-Y keep their usual text-editing meaning there.

### Open at a page from Obsidian

Obsidian can request a physical page with
`hammerspoon://bob-highlights-page?path=<encoded absolute PDF path>&page=<N>`. The
handler acts only on that exact PDF when it is already in front in Highlights; it never
opens files or launches apps. After the verified jump, Highlights alerts `Page 4 of 44`.
When the jump moved from another page, the alert adds ` · ⌃O back to p. 30`, and `⌃O`
returns to the page Highlights had restored before the request.

## Internet ping menu bar

Hammerspoon shows internet connectivity as one status item beside the Pomodoro item. The
glyph is the verdict (`✓` usable, `✗` not, `◌` unknown), color is quality (green good,
amber impaired, red broken, gray unknown), and the text is the one fact that explains
the color: a ping count, a latency, or `web`. The red pill means pings are dark and the
web check failed. Counts are always ping evidence; the copy never claims ICMP is
blocked, and it never uses offline wording for the web tier. A single dropped ping never
flips the title, a web verdict stands until the next one lands, and nothing is bold
except the pill, so the Pomodoro item stays primary.

One ping stream feeds both this item and the tmux status bar. Hammerspoon is the
preferred producer: it pings 8.8.8.8 every 2 s with `-W 500` (about 1.5 s on this
macOS), records each reply's RTT, and both displays render the same shared 30-sample
window, so they always agree. `tmux_ping` only reads while a fresh Hammerspoon heartbeat
exists and falls back to pinging when Hammerspoon is not running, broken, or unable to
write. That fallback is ping-only: it can show the slow tier from recorded RTTs, and it
never runs a web check. Handover is self-healing in both directions: Hammerspoon claims
the stream by writing its heartbeat and tmux backs off on its next redraw, while tmux
resumes pinging within about 6 s when Hammerspoon stops. At most one extra ping happens
during a handover. Nobody pings while the Mac is locked: Hammerspoon stops pinging but
keeps refreshing its heartbeat, so tmux does not take over either. With Hammerspoon not
running, tmux keeps working on its own.

The title is a glyph plus a field padded to five code points whenever it shows a count
or a latency (`✓ 27/30`, `✓ 1.4s`), so those titles never jitter. When every one of the
last 30 pings answered and the window is online, the title is just a green `✓` and the
item narrows. The count comes back as soon as a miss enters the window, and it also
shows while a fresh window is still filling (after start or a sleep reset). `web` is a
fixed word, so it is not padded and the item narrows the same way. The count and latency
use Menlo regular; the glyph uses the default menu bar face. Latency uses one decimal
under 10 s (`0.5s`–`9.9s`) and whole seconds above (`10s`). The tooltip names the
header, the ping score (`N of M pings answered (P%)`), and the last round-trip time when
the newest sample was a reply.

Opening the item shows a snapshot taken when it opens: a tier-colored header glyph, a
colored 30-cell history strip (`●` fast, `◐` slow, `○` no reply, `·` empty), the ping
score over its span, the last ping, a web-check row when a verdict is at most 300 s old,
a Network Settings shortcut that opens System Settings → Network, and Copy Diagnostics.
The dropdown stays open while the title keeps updating, and shows fresh details when
reopened. If styled text fails, rows fall back to plain text. If the shortcut cannot
open Settings, it shows a brief alert naming the manual fallback and logs the failure.

To change the size, edit `window_size` in `~/.config/ping_window/config` (chezmoi source
`home/dot_config/ping_window/config`), keep it in 3–99, and both displays switch within
one 2 s tick with no reload. A window older than the new span is not reset by a size
change.

### Title vocabulary

| Tier            | Menu bar                                                         | tmux (exact)                                            |
| --------------- | ---------------------------------------------------------------- | ------------------------------------------------------- |
| online, perfect | green `✓`                                                        | `#[fg=green]✓#[default] \| `                            |
| online          | green `✓` + `29/30` (Menlo, label color)                         | `#[fg=green]✓#[default] 29/30 \| `                      |
| slow            | amber `✓` + `1.4s` (Menlo, label color, padded to 5 code points) | `#[fg=#ffc777]✓#[default] 1.4s \| `                     |
| web             | green `✓` + `web` (menu bar font, secondary label, no padding)   | `#[fg=green]✓#[default] #[fg=#828bb8]web#[default] \| ` |
| lossy           | amber `✓` + `26/30`                                              | `#[fg=#ffc777]✓#[default] 26/30 \| `                    |
| down            | red `✗` + red `29/30`                                            | `#[fg=red]✗#[default] 29/30 \| `                        |
| offline         | white bold `✗ 0/30` on a red pill                                | `#[fg=white,bg=red,bold] ✗ 0/30 #[default] \| `         |
| stale           | gray `◌` + gray `27/30` (or `–`)                                 | `#[fg=#828bb8]◌ 27/30#[default] \| `                    |

Slow is the upper median of the last 3–5 reply RTTs at or above 500 ms, or a fresh
`web=ok` whose TCP handshake is at or above 500 ms while pings are dark. Web is a dark
or lossy ping window with a fresh `ok` web verdict (a single dropped ping stays a green
count; the title says `web` only below 90%). Offline is 3 or more trailing misses once
the web check has failed, or in tmux-only mode where no web checker runs.

### Web check

When Hammerspoon records a missed ping and the session is not paused, it starts an HTTP
check against `http://captive.apple.com/hotspot-detect.html` unless a check is already
in flight or one started in the last 10 s. The check is `/usr/bin/curl` with an 8 s
overall deadline, a 6 s connect timeout, no redirects, and no proxy. A 200 response
whose body contains `Success` is `ok`; any other HTTP response is treated as a captive
portal (`sign-in required?` in the header); a timeout, connect failure, or DNS failure
is `fail`. The handshake time (`time_connect − time_namelookup`) is the web RTT,
comparable to a ping RTT, so `✓ 2.1s` means the same thing on either channel. A verdict
stays current for 15 s, and an in-flight `check=` token lets the last verdict stand
until the next one lands so a re-check never opens a gap that would flash the pill.

### Traffic

| Situation                             | Traffic                                                              |
| ------------------------------------- | -------------------------------------------------------------------- |
| Unlocked, tmux client attached        | 1 ping / 2 s                                                         |
| Unlocked, pings failing (Hammerspoon) | 1 ping / 2 s + at most 1 web check / ~10 s (~1–2 KB, under 0.7 MB/h) |
| Locked, tmux client attached          | none                                                                 |
| Unlocked, no tmux client              | 1 ping / 2 s                                                         |
| Hammerspoon not running (ping-only)   | tmux pings 8.8.8.8 every 2 s; no web checks                          |
| Mac asleep                            | none                                                                 |

Web-check traffic is zero on a healthy network. Checks run only after a missed ping, and
never while the Mac is locked or asleep.

### State v2

The shared window lives in `~/tmp/tmux_ping_state`: one LF-terminated line of

```text
<heartbeat> <producer> <sampled> <results>[ <key>=<value>]...
```

`heartbeat` is the producer's latest write, `producer` is `hammerspoon` or `tmux`,
`sampled` is when the newest sample was sent (`0` when empty), and `results` is 1–99
characters of `1` (fast reply), `s` (reply at or above 500 ms), or `0` (no reply),
oldest first (`-` when empty). Optional tokens, emitted in this order and omitted when
absent:

```text
rtt=<ms>[,<ms>]…       1–5 integers: the newest reply RTTs, oldest first
web=<v>,<at>,<ms|->    v ∈ ok|fail|portal; at = epoch the verdict landed;
                       ms = TCP handshake ms
check=<epoch>          a web check started at <epoch> and has not landed yet
```

Unknown keys are ignored. A known key with a malformed value counts as absent; the line
stays valid, and the last occurrence wins. Every write carries `web=` and `check=`
forward unchanged unless that writer is the one setting them. Writers replace the file
atomically, so readers never lock. A window older than the window span (size × 2 s, 60 s
by default) is dropped on the next sample, so no window spans a sleep or a long pause. A
v1 four-field line is a valid v2 line.

### Events log and diagnostics

Hammerspoon appends every start, tier change, web-verdict change, and ping/curl tool
error to `~/tmp/ping_window_events.tsv`. Each line is `<time>\t<event>\t<detail>`
(ISO-8601 local time with offset). The file is capped at 2000 lines and trimmed to the
newest 1000 at startup and whenever it grows past the cap. Every event is also mirrored
to the Hammerspoon console.

**Copy Diagnostics** copies a plain-text report to the pasteboard and alerts
`Ping diagnostics copied`. The report is a timestamp, the tier, title, and header, the
raw state line, the ping argv and last ping exit/RTT, the web verdict and its detail,
and the last 20 event lines.

Hold ⌥ while opening the menu for **Preview All States**. It steps the title through
perfect, count, slow, web, lossy, down/checking, offline, offline/portal, and stale for
2.5 s each with an alert naming the label, then restores the live title. The preview
never writes the state file or the events log.

### Troubleshooting

If the title looks wrong while pages still load, run these before the condition clears:

```sh
gw=$(route -n get default | awk '/gateway/{print $2}')
ping -n -c 5 -W 5000 8.8.8.8 | tail -3     # replies 1200+ ms → late; none → lost
ping -n -c 3 -W 1500 "$gw"   | tail -2     # the Wi-Fi/hotspot hop itself
curl -s -o /dev/null --max-time 10 \
  -w 'http %{http_code} connect %{time_connect}s total %{time_total}s\n' \
  http://captive.apple.com/hotspot-detect.html
# 200+fast → ICMP-blind; 200+slow → slow; 000 → outage
```

Then Copy Diagnostics and keep `~/tmp/ping_window_events.tsv`.

### Limits

- tmux-only mode is ping-only: the slow tier works from RTTs, there is no web tier, and
  the pill still fires after 3 trailing misses.
- An outage that starts while showing `✓ web` stays `✓ web` until the next check fails
  (within about 20 s).
- Links with RTT above about 3 s may fail the 8 s web check and show red.
- The cause of ICMP silence (late replies versus a path that drops ICMP) cannot be
  determined from here.

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

## Crontabs

Every machine's user crontab comes from one place: the `cron:` key in
`home/.chezmoidata.yaml`. Each enrolled machine's crontab holds one block between
`# BEGIN chezmoi-cron` and `# END chezmoi-cron`; `chezmoi update -a` reinstalls that
block when it changes and never touches the lines outside it. Every job runs through
`~/bin/cronrun`, which logs to `~/.local/state/cron/<job>.log` and mails only failures.
Run `cronctl --help` for the full command list.

To change a job:

1. Run `cronctl edit` (or `vcron`). It opens the data in `$EDITOR`, then checks it and
   shows the diff for this machine.
2. Commit and push.
3. Run `chezmoi update -a` on each affected machine, or `cronctl apply <machine>...`
   from any machine.

Check the result with `cronctl status --all`, and read a job's output with
`cronctl logs <job> --machine <machine>`. Never use `crontab -e` for a lasting job, and
never edit inside the managed block: the next sync overwrites it.
