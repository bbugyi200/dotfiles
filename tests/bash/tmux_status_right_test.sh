#!/bin/bash

#################################################################################
# Regression tests for the tmux status-right CPU/memory/battery guarantee.    #
#                                                                               #
# The right side of the tmux status bar must end with the full                 #
# `cpu N% mem N% <battery>` readout whenever the client is wider than          #
# status-left plus about 27 columns.                                           #
# Lower-priority right-side text (Pomodoro, ping, hostname) gives way first,   #
# elided from the left with a "…" marker.                                       #
#                                                                               #
# The test renders the real `home/dot_config/tmux/tmux.conf` in an isolated   #
# nested tmux (an outer `tmux -L <outer>` whose pane runs an inner tmux on the #
# real config) and asserts on the status line drawn in the outer capture. The  #
# `#()` helpers are stubbed on a hermetic PATH so the suite never depends on  #
# live Pomodoro state, ping results, the host's hostname, or system load. The  #
# `tmux_load_avg` stub keeps the real script's `#[…]` markup shape so style    #
# markup crosses the trim point, just like production. The `tmux_battery`      #
# stub prints the default dim battery segment unless FAKE_BATTERY says         #
# otherwise; an empty FAKE_BATTERY models a host without a battery.            #
#################################################################################

TMUX_CONF="${PWD}/home/dot_config/tmux/tmux.conf"
THEME_CONF="${PWD}/home/dot_config/tmux/theme.conf"

DEFAULT_POMODORO='[<7m] 1545-1610 — SASE V18 · plan 2/3 · 6/10 | '
LONG_POMODORO='[<7m] 1545-1610 — Refactor the capture grammar for the Bob Mac Capture thin client · plan 2/3 · 6/10 | '
UNNAMED_DERIVED_POMODORO='[<13m] 0950-1015 sase | '

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_HOME="${TEST_TMP}/home"
  FAKE_BIN="${TEST_TMP}/bin"
  OUTER_SOCKET="tmux_status_right_test_$$_outer"
  INNER_SOCKET="tmux_status_right_test_$$_inner"

  mkdir -p "${FAKE_BIN}" "${FAKE_HOME}/.config/tmux" "${FAKE_HOME}/.tmux/plugins/tpm"

  cp "${THEME_CONF}" "${FAKE_HOME}/.config/tmux/theme.conf"

  cat > "${FAKE_HOME}/.tmux/plugins/tpm/tpm" <<'EOF'
#!/bin/bash
exit 0
EOF
  chmod +x "${FAKE_HOME}/.tmux/plugins/tpm/tpm"

  cat > "${FAKE_BIN}/bob" <<'EOF'
#!/bin/bash
printf '%s' "${FAKE_POMODORO:-[<7m] 1545-1610 — SASE V18 · plan 2/3 · 6/10 | }"
EOF
  chmod +x "${FAKE_BIN}/bob"

  cat > "${FAKE_BIN}/tmux_ping" <<'EOF'
#!/bin/bash
printf '%s' '#[fg=green]✓#[default] | '
EOF
  chmod +x "${FAKE_BIN}/tmux_ping"

  cat > "${FAKE_BIN}/hostname" <<'EOF'
#!/bin/bash
printf '%s' 'Kellys-MacBook-Pro.local'
EOF
  chmod +x "${FAKE_BIN}/hostname"

  cat > "${FAKE_BIN}/tmux_load_avg" <<'EOF'
#!/bin/bash
printf '%s' ' #[fg=#828bb8]cpu #[fg=#ff757f]40% #[fg=#828bb8]mem #[default]65%#[default]'
EOF
  chmod +x "${FAKE_BIN}/tmux_load_avg"

  cat > "${FAKE_BIN}/tmux_battery" <<'EOF'
#!/bin/bash
GLYPH=$'\xf3\xb0\x82\x80'
DEFAULT=" #[fg=#828bb8]${GLYPH} #[default]72%#[default]"
printf '%s' "${FAKE_BATTERY-${DEFAULT}}"
EOF
  chmod +x "${FAKE_BIN}/tmux_battery"

  cat > "${FAKE_BIN}/tm-sessions" <<'EOF'
#!/bin/bash
printf '%s' '[sase]'
EOF
  chmod +x "${FAKE_BIN}/tm-sessions"

  export FAKE_POMODORO="${DEFAULT_POMODORO}"
  unset FAKE_BATTERY
}

BATTERY_70=$'\xf3\xb0\x82\x80'
BATTERY_SUFFIX="cpu 40% mem 65% ${BATTERY_70} 72%"

function tear_down() {
  tmux -L "${OUTER_SOCKET}" kill-server 2>/dev/null || true
  tmux -L "${INNER_SOCKET}" kill-server 2>/dev/null || true
  rm -rf "${TEST_TMP}"
}

# Render the real tmux.conf at the given client width and print the drawn
# status line (the last line of the outer capture). The `#()` jobs finish
# asynchronously, so poll until the readout the case expects appears (at
# most about 5 s). The explicit `sleep 60` window commands keep the test
# independent of `default-shell /bin/zsh`, since CI has no zsh.
function render_status_line() {
  local width="$1"
  local expect="${2:-mem 65%}"

  tmux -L "${OUTER_SOCKET}" kill-server 2>/dev/null || true
  tmux -L "${INNER_SOCKET}" kill-server 2>/dev/null || true

  local battery_assign=()
  if [[ -n "${FAKE_BATTERY+set}" ]]; then
    battery_assign=("FAKE_BATTERY=${FAKE_BATTERY}")
  fi

  local inner_cmd="tmux -L ${INNER_SOCKET} -f '${TMUX_CONF}' new-session -s t -n one 'sleep 60' \\; new-window -n two 'sleep 60' \\; new-window -n three 'sleep 60'"
  env -u TMUX HOME="${FAKE_HOME}" PATH="${FAKE_BIN}:${PATH}" FAKE_POMODORO="${FAKE_POMODORO}" \
    "${battery_assign[@]}" \
    tmux -L "${OUTER_SOCKET}" -f /dev/null new-session -d -x "${width}" -y 6 "${inner_cmd}" 2>/dev/null

  local line=""
  local i
  for i in $(seq 1 50); do
    sleep 0.1
    line="$(tmux -L "${OUTER_SOCKET}" capture-pane -p 2>/dev/null | tail -n 1 | sed -e 's/[[:space:]]*$//')"
    if [[ "${line}" == *"${expect}"* ]]; then
      break
    fi
  done
  printf '%s' "${line}"
}

function assert_ends_with() {
  local suffix="$1"
  local text="$2"

  case "${text}" in
  *"${suffix}")
    ;;
  *)
    printf 'expected status line to end with <%s>, got: <%s>\n' "${suffix}" "${text}" >&2
    return 1
    ;;
  esac
}

function require_tmux() {
  command -v tmux >/dev/null || { bashunit::skip "tmux is required to render the status line"; return 1; }
}

function test_wide_terminal_shows_the_whole_right_side() {
  require_tmux || return 0
  FAKE_POMODORO="${DEFAULT_POMODORO}"

  local line
  line="$(render_status_line 285)"

  assert_contains "[<7m] 1545-1610 — SASE V18" "${line}"
  assert_ends_with "Kellys-MacBook-Pro.local ${BATTERY_SUFFIX}" "${line}"
  assert_ends_with "${BATTERY_SUFFIX}" "${line}"
}

function test_cpu_and_mem_survive_narrow_terminals() {
  require_tmux || return 0
  FAKE_POMODORO="${DEFAULT_POMODORO}"

  local width line
  for width in 160 120 90 60 40; do
    line="$(render_status_line "${width}")"
    assert_contains "${BATTERY_SUFFIX}" "${line}"
    assert_ends_with "${BATTERY_SUFFIX}" "width ${width}: ${line}"
  done
}

function test_overflow_is_elided_from_the_left_with_a_marker() {
  require_tmux || return 0
  FAKE_POMODORO="${LONG_POMODORO}"

  local line
  line="$(render_status_line 120)"

  assert_contains "…" "${line}"
  assert_not_contains "[<7m]" "${line}"
  assert_ends_with "${BATTERY_SUFFIX}" "${line}"
}

function test_window_list_keeps_room_at_mid_width() {
  require_tmux || return 0
  FAKE_POMODORO="${DEFAULT_POMODORO}"

  local line
  line="$(render_status_line 90)"

  assert_contains "one" "${line}"
  assert_contains "two" "${line}"
  assert_contains "three" "${line}"
  assert_contains "…" "${line}"
  assert_ends_with "${BATTERY_SUFFIX}" "${line}"
}

function test_wide_terminal_fits_a_long_pomodoro() {
  require_tmux || return 0
  FAKE_POMODORO="${LONG_POMODORO}"

  local line
  line="$(render_status_line 285)"

  assert_contains "[<7m]" "${line}"
  assert_ends_with "${BATTERY_SUFFIX}" "${line}"
}

function test_wide_terminal_shows_unnamed_derived_label() {
  require_tmux || return 0
  FAKE_POMODORO="${UNNAMED_DERIVED_POMODORO}"

  local line
  line="$(render_status_line 285)"

  assert_contains "[<13m] 0950-1015 sase" "${line}"
  assert_ends_with "${BATTERY_SUFFIX}" "${line}"
}

function test_host_without_battery_still_ends_with_cpu_and_mem() {
  require_tmux || return 0
  FAKE_POMODORO="${DEFAULT_POMODORO}"
  FAKE_BATTERY=''

  local line
  line="$(render_status_line 285)"

  assert_contains "cpu 40% mem 65%" "${line}"
  assert_ends_with "Kellys-MacBook-Pro.local cpu 40% mem 65%" "${line}"
  assert_ends_with "cpu 40% mem 65%" "${line}"
}

function test_worst_case_readout_survives_narrow_widths() {
  require_tmux || return 0
  FAKE_POMODORO="${DEFAULT_POMODORO}"

  local alert=$'\xf3\xb0\x82\x83'
  FAKE_BATTERY=" #[fg=white,bg=red,bold] ${alert} 10% #[default]"

  cat > "${FAKE_BIN}/tmux_load_avg" <<'EOF'
#!/bin/bash
printf '%s' ' #[fg=#828bb8]cpu #[fg=#ff757f]100% #[fg=#828bb8]mem #[default]100%#[default]'
EOF
  chmod +x "${FAKE_BIN}/tmux_load_avg"

  local width line
  for width in 40 60 87 88 120; do
    line="$(render_status_line "${width}" '10%')"
    assert_contains "cpu 100% mem 100%" "${line}"
    assert_ends_with "cpu 100% mem 100%  ${alert} 10%" "width ${width}: ${line}"
  done
}
