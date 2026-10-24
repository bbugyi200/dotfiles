#!/bin/bash

#################################################################################
# Regression tests for the Amethyst shortcut chezmoi hook.                       #
#################################################################################

REPO_ROOT="${PWD}"
HOOK_TEMPLATE="${REPO_ROOT}/home/.chezmoiscripts/run_onchange_after_disable_amethyst_swap_screen_cw.tmpl"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  EMPTY_CONFIG="${TEST_TMP}/empty.yaml"
  HOOK_SCRIPT="${TEST_TMP}/amethyst-hook.sh"
  FAKE_BIN="${TEST_TMP}/bin"
  STATE_FILE="${TEST_TMP}/state.txt"
  PROCESS_FILE="${TEST_TMP}/process.txt"
  CALLS_FILE="${TEST_TMP}/calls.txt"
  STDOUT_FILE="${TEST_TMP}/stdout.txt"
  STDERR_FILE="${TEST_TMP}/stderr.txt"

  mkdir -p "${FAKE_BIN}"
  : >"${EMPTY_CONFIG}"
  : >"${STATE_FILE}"
  printf 'stopped\n' >"${PROCESS_FILE}"
  : >"${CALLS_FILE}"
  FAKE_RUNNING=0
  FAKE_SURVIVES_TERM=0
  FAKE_SURVIVES_KILL=0
  FAKE_OPEN_RC=0
  write_host_stubs
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function require_chezmoi() {
  if ! command -v chezmoi >/dev/null 2>&1; then
    bashunit::skip "chezmoi is required to render the hook template"
    return 1
  fi
}

function write_host_stubs() {
  cat >"${FAKE_BIN}/defaults" <<'EOF'
#!/bin/bash
printf 'defaults %s\n' "$*" >>"${CALLS_FILE}"
case "$1" in
  read)
    if [[ -s "${STATE_FILE}" ]]; then
      cat "${STATE_FILE}"
    else
      exit 1
    fi
    ;;
  delete)
    : >"${STATE_FILE}"
    ;;
esac
EOF
  chmod +x "${FAKE_BIN}/defaults"

  cat >"${FAKE_BIN}/pgrep" <<'EOF'
#!/bin/bash
printf 'pgrep %s\n' "$*" >>"${CALLS_FILE}"
[[ "$(cat "${PROCESS_FILE}")" == "running" ]]
EOF
  chmod +x "${FAKE_BIN}/pgrep"

  cat >"${FAKE_BIN}/pkill" <<'EOF'
#!/bin/bash
printf 'pkill %s\n' "$*" >>"${CALLS_FILE}"
if [[ "$*" == *"-KILL"* ]]; then
  survives="${FAKE_SURVIVES_KILL}"
else
  survives="${FAKE_SURVIVES_TERM}"
fi
if [[ "${survives}" == "0" ]]; then
  printf 'stopped\n' >"${PROCESS_FILE}"
fi
EOF
  chmod +x "${FAKE_BIN}/pkill"

  cat >"${FAKE_BIN}/open" <<'EOF'
#!/bin/bash
printf 'open %s\n' "$*" >>"${CALLS_FILE}"
exit "${FAKE_OPEN_RC}"
EOF
  chmod +x "${FAKE_BIN}/open"

  cat >"${FAKE_BIN}/sleep" <<'EOF'
#!/bin/bash
exit 0
EOF
  chmod +x "${FAKE_BIN}/sleep"
}

function render_darwin_hook() {
  sed 's/eq \.chezmoi\.os "darwin"/true/' "${HOOK_TEMPLATE}" \
    | chezmoi --config "${EMPTY_CONFIG}" --source "${REPO_ROOT}" \
      execute-template >"${HOOK_SCRIPT}"
}

function run_hook() {
  PATH="${FAKE_BIN}:/usr/bin:/bin" \
    STATE_FILE="${STATE_FILE}" \
    PROCESS_FILE="${PROCESS_FILE}" \
    CALLS_FILE="${CALLS_FILE}" \
    FAKE_SURVIVES_TERM="${FAKE_SURVIVES_TERM}" \
    FAKE_SURVIVES_KILL="${FAKE_SURVIVES_KILL}" \
    FAKE_OPEN_RC="${FAKE_OPEN_RC}" \
    bash "${HOOK_SCRIPT}" >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
}

function stdout_text() { cat "${STDOUT_FILE}"; }
function stderr_text() { cat "${STDERR_FILE}"; }
function calls_text() { cat "${CALLS_FILE}"; }
function set_binding() { printf '%s\n' "$1" >"${STATE_FILE}"; }

function test_hook_renders_empty_on_linux() {
  require_chezmoi || return 0
  if [[ "$(uname -s)" == "Darwin" ]]; then
    bashunit::skip "hook renders a body on Darwin"
    return 0
  fi
  local output
  output="$(chezmoi --config "${EMPTY_CONFIG}" --source "${REPO_ROOT}" \
    execute-template <"${HOOK_TEMPLATE}")"
  assert_same "" "$(printf '%s' "${output}" | tr -d '[:space:]')"
}

function test_rendered_darwin_hook_is_valid_bash() {
  require_chezmoi || return 0
  render_darwin_hook
  bash -n "${HOOK_SCRIPT}"
  assert_same "0" "$?"
}

function test_absent_key_is_noop() {
  require_chezmoi || return 0
  render_darwin_hook
  local rc
  if run_hook; then rc=0; else rc=$?; fi
  assert_same "0" "${rc}"
  assert_contains "unbound" "$(stdout_text)"
  assert_not_contains "defaults delete" "$(calls_text)"
  assert_not_contains "pkill" "$(calls_text)"
  assert_not_contains "open " "$(calls_text)"
}

function test_other_chord_is_left_alone() {
  require_chezmoi || return 0
  render_darwin_hook
  set_binding '{"carbonKeyCode":4,"carbonModifiers":6656}'
  local rc
  if run_hook; then rc=0; else rc=$?; fi
  assert_same "0" "${rc}"
  assert_contains "another chord" "$(stdout_text)"
  assert_not_contains "defaults delete" "$(calls_text)"
  assert_not_contains "pkill" "$(calls_text)"
}

function test_unbound_running_later_clears_key_without_restart() {
  require_chezmoi || return 0
  render_darwin_hook
  set_binding '{"carbonModifiers":6656,"carbonKeyCode":37}'
  local rc
  if run_hook; then rc=0; else rc=$?; fi
  assert_same "0" "${rc}"
  assert_same "" "$(cat "${STATE_FILE}")"
  assert_contains "defaults delete com.amethyst.Amethyst KeyboardShortcuts_swap-screen-cw" "$(calls_text)"
  assert_not_contains "pkill" "$(calls_text)"
  assert_not_contains "open " "$(calls_text)"
  assert_contains "next launch" "$(stdout_text)"
}

function test_running_amethyst_restarts_after_delete() {
  require_chezmoi || return 0
  render_darwin_hook
  set_binding '{"carbonKeyCode":37,"carbonModifiers":6656}'
  printf 'running\n' >"${PROCESS_FILE}"
  local rc
  if run_hook; then rc=0; else rc=$?; fi
  assert_same "0" "${rc}"
  local calls
  calls="$(calls_text)"
  local term kill delete open
  term="$(grep -n '^pkill -x Amethyst$' <<<"${calls}" | cut -d: -f1)"
  delete="$(grep -n '^defaults delete ' <<<"${calls}" | cut -d: -f1)"
  open="$(grep -n '^open -g -a Amethyst$' <<<"${calls}" | cut -d: -f1)"
  local order_rc=1
  if ((term < delete && delete < open)); then order_rc=0; fi
  assert_same "0" "${order_rc}"
  assert_contains "restarted" "$(stdout_text)"
}

function test_amethyst_surviving_term_and_kill_does_not_clear_key() {
  require_chezmoi || return 0
  render_darwin_hook
  set_binding '{"carbonKeyCode":37,"carbonModifiers":6656}'
  printf 'running\n' >"${PROCESS_FILE}"
  FAKE_SURVIVES_TERM=1
  FAKE_SURVIVES_KILL=1
  local rc
  if run_hook; then rc=0; else rc=$?; fi
  assert_same "1" "${rc}"
  assert_contains "did not exit" "$(stderr_text)"
  assert_not_contains "defaults delete" "$(calls_text)"
}

function test_failed_relaunch_reports_manual_action() {
  require_chezmoi || return 0
  render_darwin_hook
  set_binding '{"carbonKeyCode":37,"carbonModifiers":6656}'
  printf 'running\n' >"${PROCESS_FILE}"
  FAKE_OPEN_RC=1
  local rc
  if run_hook; then rc=0; else rc=$?; fi
  assert_same "1" "${rc}"
  assert_contains "start it manually" "$(stderr_text)"
}

function test_second_run_after_success_is_noop() {
  require_chezmoi || return 0
  render_darwin_hook
  set_binding '{"carbonKeyCode":37,"carbonModifiers":6656}'
  run_hook
  : >"${CALLS_FILE}"
  local rc
  if run_hook; then rc=0; else rc=$?; fi
  assert_same "0" "${rc}"
  assert_contains "unbound" "$(stdout_text)"
  assert_not_contains "defaults delete" "$(calls_text)"
}
