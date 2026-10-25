#!/bin/bash

#################################################################################
# Regression tests for the Hammerspoon restart chezmoi hook.                    #
#################################################################################

REPO_ROOT="${PWD}"
HOOK_TEMPLATE="${REPO_ROOT}/home/.chezmoiscripts/run_onchange_after_restart_hammerspoon.tmpl"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  EMPTY_CONFIG="${TEST_TMP}/empty.yaml"
  HOOK_SCRIPT="${TEST_TMP}/restart-hook.sh"
  FAKE_BIN="${TEST_TMP}/bin"
  STATE_FILE="${TEST_TMP}/state.txt"
  CALLS_FILE="${TEST_TMP}/calls.txt"
  STDOUT_FILE="${TEST_TMP}/stdout.txt"
  STDERR_FILE="${TEST_TMP}/stderr.txt"

  mkdir -p "${FAKE_BIN}"
  : >"${EMPTY_CONFIG}"
  printf 'stopped\n' >"${STATE_FILE}"
  : >"${CALLS_FILE}"
  FAKE_SURVIVES_TERM=0
  FAKE_SURVIVES_KILL=0
  FAKE_OPEN_FAILS=0
  FAKE_LS_LINGER=0
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
  cat >"${FAKE_BIN}/pgrep" <<'EOF'
#!/bin/bash
printf 'pgrep %s\n' "$*" >>"${CALLS_FILE}"
if [[ "$(cat "${STATE_FILE}")" == "running" ]]; then
  exit 0
else
  exit 1
fi
EOF
  chmod +x "${FAKE_BIN}/pgrep"

  cat >"${FAKE_BIN}/pkill" <<'EOF'
#!/bin/bash
printf 'pkill %s\n' "$*" >>"${CALLS_FILE}"
if [[ "$*" == *"-KILL"* ]]; then
  survives="${FAKE_SURVIVES_KILL:-0}"
else
  survives="${FAKE_SURVIVES_TERM:-0}"
fi
if [[ "${survives}" == "0" ]]; then
  printf 'stopped\n' >"${STATE_FILE}"
fi
exit 0
EOF
  chmod +x "${FAKE_BIN}/pkill"

  cat >"${FAKE_BIN}/open" <<'EOF'
#!/bin/bash
printf 'open %s\n' "$*" >>"${CALLS_FILE}"
count_file="${TEST_TMP}/open.count"
count=0
if [[ -f "${count_file}" ]]; then
  count="$(cat "${count_file}")"
fi
count=$((count + 1))
printf '%s\n' "${count}" >"${count_file}"
fails="${FAKE_OPEN_FAILS:-0}"
if ((count <= fails)); then
  printf '_LSOpenURLsWithCompletionHandler() failed for the application /Applications/Hammerspoon.app with error -600.\n' >&2
  exit 1
fi
printf 'running\n' >"${STATE_FILE}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/open"

  cat >"${FAKE_BIN}/lsappinfo" <<'EOF'
#!/bin/bash
printf 'lsappinfo %s\n' "$*" >>"${CALLS_FILE}"
if [[ "$(cat "${STATE_FILE}")" == "running" ]]; then
  printf 'ASN:0x0-0x1-"Hammerspoon":\n'
  exit 0
fi
count_file="${TEST_TMP}/lsappinfo.count"
count=0
if [[ -f "${count_file}" ]]; then
  count="$(cat "${count_file}")"
fi
count=$((count + 1))
printf '%s\n' "${count}" >"${count_file}"
linger="${FAKE_LS_LINGER:-0}"
if ((count <= linger)); then
  printf 'ASN:0x0-0x1-"Hammerspoon":\n'
else
  printf '\n'
fi
exit 0
EOF
  chmod +x "${FAKE_BIN}/lsappinfo"

  # No-op so the hook's exit-wait loops stay fast.
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
    CALLS_FILE="${CALLS_FILE}" \
    TEST_TMP="${TEST_TMP}" \
    FAKE_SURVIVES_TERM="${FAKE_SURVIVES_TERM}" \
    FAKE_SURVIVES_KILL="${FAKE_SURVIVES_KILL}" \
    FAKE_OPEN_FAILS="${FAKE_OPEN_FAILS}" \
    FAKE_LS_LINGER="${FAKE_LS_LINGER}" \
    bash "${HOOK_SCRIPT}" >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
}

function stdout_text() {
  cat "${STDOUT_FILE}"
}

function stderr_text() {
  cat "${STDERR_FILE}"
}

function calls_text() {
  cat "${CALLS_FILE}"
}

function test_hook_hashes_every_hammerspoon_lua_file() {
  local failures=""
  local lua_file rel count included

  while IFS= read -r lua_file; do
    rel="${lua_file#home/}"
    count="$(grep -c -F "include \"${rel}\" | sha256sum" "${HOOK_TEMPLATE}" || true)"
    if [[ "${count}" != "1" ]]; then
      failures="${failures}expected exactly one hash line for ${rel}, found ${count}"$'\n'
    fi
  done < <(cd "${REPO_ROOT}" && find home/dot_hammerspoon -type f -name '*.lua' | sort)

  while IFS= read -r included; do
    if [[ ! -f "${REPO_ROOT}/home/${included}" ]]; then
      failures="${failures}hook hashes missing file home/${included}"$'\n'
    fi
  done < <(grep -o 'include "dot_hammerspoon/[^"]*"' "${HOOK_TEMPLATE}" \
    | sed 's/include "//;s/"//' | sort -u)

  if [[ -n "${failures}" ]]; then
    printf 'hash drift:\n%s' "${failures}" >&2
  fi
  assert_same "" "${failures}"
}

function test_hook_renders_empty_on_linux() {
  require_chezmoi || return 0
  if [[ "$(uname -s)" == "Darwin" ]]; then
    bashunit::skip "hook renders a restart body on Darwin"
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
  assert_contains "Hammerspoon restarted" "$(cat "${HOOK_SCRIPT}")"
}

function test_not_running_does_nothing() {
  require_chezmoi || return 0
  render_darwin_hook
  printf 'stopped\n' >"${STATE_FILE}"

  local rc
  if run_hook; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_contains "not running" "$(stdout_text)"
  assert_not_contains "pkill" "$(calls_text)"
  assert_not_contains "open " "$(calls_text)"
  assert_not_contains "lsappinfo" "$(calls_text)"
}

function test_running_exits_on_term() {
  require_chezmoi || return 0
  render_darwin_hook
  printf 'running\n' >"${STATE_FILE}"

  local rc
  if run_hook; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_contains "pkill -x Hammerspoon" "$(calls_text)"
  assert_not_contains "KILL" "$(calls_text)"
  assert_contains "open -g -a Hammerspoon" "$(calls_text)"
  assert_contains "restarted" "$(stdout_text)"
}

function test_running_survives_term_dies_on_kill() {
  require_chezmoi || return 0
  render_darwin_hook
  printf 'running\n' >"${STATE_FILE}"
  FAKE_SURVIVES_TERM=1

  local rc
  if run_hook; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_contains "pkill -KILL -x Hammerspoon" "$(calls_text)"
  assert_contains "open -g -a Hammerspoon" "$(calls_text)"
}

function test_running_survives_kill_is_not_relaunched() {
  require_chezmoi || return 0
  render_darwin_hook
  printf 'running\n' >"${STATE_FILE}"
  FAKE_SURVIVES_TERM=1
  FAKE_SURVIVES_KILL=1

  local rc
  if run_hook; then rc=0; else rc=$?; fi

  assert_same "1" "${rc}"
  assert_contains "pkill -KILL -x Hammerspoon" "$(calls_text)"
  assert_not_contains "open " "$(calls_text)"
  assert_contains "did not exit" "$(stderr_text)"
}

function test_waits_for_launchservices_release_before_open() {
  require_chezmoi || return 0
  render_darwin_hook
  printf 'running\n' >"${STATE_FILE}"
  FAKE_LS_LINGER=3

  local rc
  if run_hook; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_contains "restarted" "$(stdout_text)"
  assert_same "1" "$(grep -c '^open ' "${CALLS_FILE}")"
  local last_lsappinfo open_line
  last_lsappinfo="$(grep -n '^lsappinfo ' "${CALLS_FILE}" | tail -n 1 | cut -d: -f1)"
  open_line="$(grep -n '^open ' "${CALLS_FILE}" | cut -d: -f1)"
  assert_same "1" "$([ "${open_line}" -gt "${last_lsappinfo}" ] && printf '1\n' || printf '0\n')"
}

function test_transient_open_failure_is_retried() {
  require_chezmoi || return 0
  render_darwin_hook
  printf 'running\n' >"${STATE_FILE}"
  FAKE_OPEN_FAILS=1

  local rc
  if run_hook; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_contains "restarted" "$(stdout_text)"
  assert_same "2" "$(grep -c '^open ' "${CALLS_FILE}")"
  assert_not_contains "_LSOpenURLsWithCompletionHandler" "$(stderr_text)"
}

function test_persistent_open_failure_exits_nonzero() {
  require_chezmoi || return 0
  render_darwin_hook
  printf 'running\n' >"${STATE_FILE}"
  FAKE_OPEN_FAILS=10

  local rc
  if run_hook; then rc=0; else rc=$?; fi

  assert_same "1" "${rc}"
  assert_contains "could not be relaunched" "$(stderr_text)"
  assert_contains "error -600" "$(stderr_text)"
  assert_same "5" "$(grep -c '^open ' "${CALLS_FILE}")"
}

function test_lingering_launchservices_registration_still_relaunches() {
  require_chezmoi || return 0
  render_darwin_hook
  printf 'running\n' >"${STATE_FILE}"
  FAKE_LS_LINGER=100

  local rc
  if run_hook; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_contains "restarted" "$(stdout_text)"
  assert_contains "open -g -a Hammerspoon" "$(calls_text)"
}
