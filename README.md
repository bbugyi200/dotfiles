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
