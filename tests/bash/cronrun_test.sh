#!/bin/bash

#################################################################################
# Tests for cronrun, the runner behind every chezmoi-managed cron job. Each     #
# run uses a fake HOME under `env -i`, which is close to what cron provides.    #
#################################################################################

# Job commands are single-quoted on purpose: the job, not this file, expands them.
# shellcheck disable=SC2016

SCRIPT="${PWD}/home/bin/executable_cronrun"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  TEST_HOME="${TEST_TMP}/home"
  STATE_DIR="${TEST_HOME}/.local/state/cron"
  OUT_FILE="${TEST_TMP}/stdout"
  ERR_FILE="${TEST_TMP}/stderr"
  # AF_UNIX socket paths are capped near 104 bytes, so sockets live in a
  # short directory instead of the (possibly long) TMPDIR.
  SOCK_DIR="$(mktemp -d /tmp/cronrun.XXXXXX)"
  mkdir -p "${TEST_HOME}/bin"
  RUN_OS="Darwin"
  RUN_LOCK_IMPL=""
  RUN_LOG_MAX="1048576"
  RUN_ENV=()
  RUN_STDIN="/dev/null"
}

function tear_down() {
  rm -rf "${TEST_TMP}" "${SOCK_DIR}"
}

# Sets CRONRUN_CMD to a cron-like `env -i` invocation of cronrun. env execs
# bash, so a backgrounded "${CRONRUN_CMD[@]}" has cronrun's own pid in $!.
function build_cronrun_cmd() {
  CRONRUN_CMD=(
    env -i
    HOME="${TEST_HOME}"
    PATH="/usr/bin:/bin"
    CRONRUN_OS="${RUN_OS}"
    CRONRUN_RUN_USER_DIR="${SOCK_DIR}/run/user"
    CRONRUN_X11_DIR="${SOCK_DIR}/x11"
    CRONRUN_LOCK_IMPL="${RUN_LOCK_IMPL}"
    CRONRUN_LOG_MAX_BYTES="${RUN_LOG_MAX}"
    ${RUN_ENV[@]+"${RUN_ENV[@]}"}
    "${BASH}" "${SCRIPT}"
  )
}

# Runs cronrun in the foreground; sets RC and fills OUT_FILE and ERR_FILE.
function run_cronrun() {
  build_cronrun_cmd
  "${CRONRUN_CMD[@]}" "$@" <"${RUN_STDIN}" >"${OUT_FILE}" 2>"${ERR_FILE}"
  RC=$?
}

function wait_for_file() {
  local i
  for ((i = 0; i < 100; i++)); do
    [[ -e "$1" ]] && return 0
    sleep 0.1
  done
  return 1
}

# Starts a run of demo-job that blocks until $HOME/release exists; sets BG_PID.
function start_blocking_run() {
  build_cronrun_cmd
  "${CRONRUN_CMD[@]}" demo-job \
    'touch "$HOME/started"; while [ ! -f "$HOME/release" ]; do sleep 0.1; done' \
    </dev/null >"${TEST_TMP}/bg.out" 2>"${TEST_TMP}/bg.err" &
  BG_PID=$!
  wait_for_file "${TEST_HOME}/started"
}

function finish_blocking_run() {
  touch "${TEST_HOME}/release"
  wait "${BG_PID}"
  BG_RC=$?
}

function status_value() {
  sed -n "s/^$1=//p" "${STATE_DIR}/demo-job.status"
}

function make_socket() {
  mkdir -p "$(dirname "$1")"
  python3 -c 'import socket, sys; socket.socket(socket.AF_UNIX).bind(sys.argv[1])' "$1"
}

function test_success_is_silent_and_writes_the_log_and_status() {
  run_cronrun demo-job 'echo "hello from $0"'

  assert_same "0" "${RC}"
  assert_empty "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"

  local log
  log="$(cat "${STATE_DIR}/demo-job.log")"
  assert_contains "start demo-job pid=" "${log}"
  assert_contains "hello from demo-job" "${log}"
  assert_contains "end demo-job exit=0 duration=" "${log}"

  assert_same "job host pid start end exit" \
    "$(cut -d= -f1 "${STATE_DIR}/demo-job.status" | tr '\n' ' ' | sed 's/ $//')"
  assert_same "demo-job" "$(status_value job)"
  assert_same "0" "$(status_value exit)"
  assert_not_empty "$(status_value host)"
  assert_same "true" \
    "$([[ "$(status_value start)" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}Z$ ]] && echo true)"
  assert_same "true" \
    "$([[ "$(status_value end)" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}Z$ ]] && echo true)"
}

function test_failure_prints_the_summary_and_tail_and_propagates_the_exit_code() {
  run_cronrun demo-job 'echo previous-run-marker'
  run_cronrun demo-job 'for i in $(seq 1 60); do echo "line-$i"; done; echo boom >&2; exit 7'

  assert_same "7" "${RC}"
  assert_empty "$(cat "${OUT_FILE}")"
  local err
  err="$(cat "${ERR_FILE}")"
  assert_contains "cronrun: demo-job failed (exit 7) on " "${err}"
  assert_contains "boom" "${err}"
  assert_contains "line-60" "${err}"
  assert_contains "line-23" "${err}"
  assert_not_contains "line-22" "${err}"
  assert_not_contains "previous-run-marker" "${err}"
  assert_same "7" "$(status_value exit)"
  assert_contains "end demo-job exit=7" "$(cat "${STATE_DIR}/demo-job.log")"
}

function test_the_end_marker_starts_its_own_line() {
  run_cronrun demo-job 'printf no-trailing-newline'

  assert_same "0" "${RC}"
  assert_same "no-trailing-newline" "$(sed -n 2p "${STATE_DIR}/demo-job.log")"
  assert_contains "==> " "$(sed -n 3p "${STATE_DIR}/demo-job.log")"
  assert_contains "end demo-job exit=0" "$(sed -n 3p "${STATE_DIR}/demo-job.log")"
}

function test_the_command_gets_no_stdin() {
  printf 'secret\n' >"${TEST_TMP}/stdin"
  RUN_STDIN="${TEST_TMP}/stdin"

  run_cronrun demo-job 'if read -r line; then echo "got:$line"; else echo no-input; fi'

  assert_same "0" "${RC}"
  assert_contains "no-input" "$(cat "${STATE_DIR}/demo-job.log")"
}

function test_an_overlapping_run_is_skipped() {
  start_blocking_run
  assert_empty "$(status_value end)"
  assert_empty "$(status_value exit)"

  run_cronrun demo-job 'touch "$HOME/second-ran"'
  finish_blocking_run

  assert_same "0" "${RC}"
  assert_empty "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"
  assert_file_not_exists "${TEST_HOME}/second-ran"
  assert_contains "skipped demo-job: an earlier run (pid ${BG_PID})" \
    "$(cat "${STATE_DIR}/demo-job.log")"
  assert_same "0" "${BG_RC}"
  assert_same "${BG_PID}" "$(status_value pid)"

  run_cronrun demo-job 'touch "$HOME/third-ran"'
  assert_same "0" "${RC}"
  assert_file_exists "${TEST_HOME}/third-ran"
}

function test_the_mkdir_lock_fallback_skips_an_overlap_and_releases() {
  RUN_LOCK_IMPL="mkdir"
  start_blocking_run
  assert_same "${BG_PID}" "$(cat "${STATE_DIR}/demo-job.lock.d/pid")"

  run_cronrun demo-job 'touch "$HOME/second-ran"'
  finish_blocking_run

  assert_same "0" "${RC}"
  assert_empty "$(cat "${ERR_FILE}")"
  assert_file_not_exists "${TEST_HOME}/second-ran"
  assert_contains "skipped demo-job: an earlier run (pid ${BG_PID})" \
    "$(cat "${STATE_DIR}/demo-job.log")"
  assert_file_not_exists "${STATE_DIR}/demo-job.lock.d"

  run_cronrun demo-job 'touch "$HOME/third-ran"'
  assert_same "0" "${RC}"
  assert_file_exists "${TEST_HOME}/third-ran"
}

function test_the_mkdir_lock_fallback_breaks_stale_locks() {
  RUN_LOCK_IMPL="mkdir"
  local dead_pid live_pid
  sleep 0 &
  dead_pid=$!
  wait "${dead_pid}"
  mkdir -p "${STATE_DIR}/demo-job.lock.d"
  echo "${dead_pid}" >"${STATE_DIR}/demo-job.lock.d/pid"

  run_cronrun demo-job 'touch "$HOME/after-dead-pid"'

  assert_same "0" "${RC}"
  assert_file_exists "${TEST_HOME}/after-dead-pid"
  assert_file_not_exists "${STATE_DIR}/demo-job.lock.d"

  # A live pid that is not cronrun is a recycled pid, so the lock is stale too.
  sleep 30 &
  live_pid=$!
  mkdir -p "${STATE_DIR}/demo-job.lock.d"
  echo "${live_pid}" >"${STATE_DIR}/demo-job.lock.d/pid"

  run_cronrun demo-job 'touch "$HOME/after-recycled-pid"'
  kill "${live_pid}" 2>/dev/null
  wait "${live_pid}" 2>/dev/null

  assert_same "0" "${RC}"
  assert_file_exists "${TEST_HOME}/after-recycled-pid"
}

function test_a_background_child_does_not_keep_the_flock_lock() {
  if ! command -v flock >/dev/null 2>&1; then
    bashunit::skip "flock is not installed (macOS uses the mkdir lock)"
    return
  fi
  RUN_LOCK_IMPL="flock"
  run_cronrun demo-job 'sleep 30 >/dev/null 2>&1 & echo $! >"$HOME/bg.pid"'
  assert_same "0" "${RC}"

  run_cronrun demo-job 'touch "$HOME/second-ran"'
  kill "$(cat "${TEST_HOME}/bg.pid")" 2>/dev/null

  assert_same "0" "${RC}"
  assert_file_exists "${TEST_HOME}/second-ran"
  assert_not_contains "skipped" "$(cat "${STATE_DIR}/demo-job.log")"
}

function test_an_interrupted_run_still_records_its_end_and_releases_the_lock() {
  RUN_LOCK_IMPL="mkdir"
  start_blocking_run
  kill -TERM "${BG_PID}"
  finish_blocking_run

  assert_same "143" "${BG_RC}"
  assert_same "143" "$(status_value exit)"
  assert_not_empty "$(status_value end)"
  assert_contains "exit=143 (cronrun was interrupted)" "$(cat "${STATE_DIR}/demo-job.log")"
  assert_file_not_exists "${STATE_DIR}/demo-job.lock.d"
}

function test_the_log_rotates_past_its_size_limit() {
  RUN_LOG_MAX="100"
  mkdir -p "${STATE_DIR}"
  printf 'old-content %0200d\n' 0 >"${STATE_DIR}/demo-job.log"

  run_cronrun demo-job 'echo new-run'

  assert_same "0" "${RC}"
  assert_contains "old-content" "$(cat "${STATE_DIR}/demo-job.log.1")"
  assert_not_contains "old-content" "$(cat "${STATE_DIR}/demo-job.log")"
  assert_contains "new-run" "$(cat "${STATE_DIR}/demo-job.log")"

  RUN_LOG_MAX="1048576"
  run_cronrun demo-job 'echo another-run'
  assert_contains "new-run" "$(cat "${STATE_DIR}/demo-job.log")"
  assert_contains "another-run" "$(cat "${STATE_DIR}/demo-job.log")"
  assert_contains "old-content" "$(cat "${STATE_DIR}/demo-job.log.1")"
}

function test_dry_run_never_executes_or_writes_state() {
  run_cronrun --dry-run demo-job 'touch "$HOME/ran"'

  assert_same "0" "${RC}"
  assert_file_not_exists "${TEST_HOME}/ran"
  assert_same "absent" "$([[ -e "${STATE_DIR}" ]] && echo present || echo absent)"
  local out
  out="$(cat "${OUT_FILE}")"
  assert_contains "dry run of job demo-job" "${out}"
  assert_contains "PATH=${TEST_HOME}/bin:${TEST_HOME}/.local/bin:" "${out}"
  assert_contains "XDG_RUNTIME_DIR=<unset>" "${out}"
  assert_contains "first word: touch -> " "${out}"
}

function test_dry_run_fails_when_the_first_word_does_not_resolve() {
  run_cronrun --dry-run demo-job 'FOO=1 no-such-cronrun-tool --flag'

  assert_same "1" "${RC}"
  assert_contains "first word: no-such-cronrun-tool -> NOT FOUND" "$(cat "${OUT_FILE}")"
  assert_same "absent" "$([[ -e "${STATE_DIR}" ]] && echo present || echo absent)"
}

function test_dry_run_resolves_tools_from_the_baseline_path_and_profile() {
  mkdir -p "${TEST_HOME}/opt/bin"
  printf '#!/bin/sh\n' >"${TEST_HOME}/bin/home-tool"
  printf '#!/bin/sh\n' >"${TEST_HOME}/opt/bin/profile-tool"
  chmod +x "${TEST_HOME}/bin/home-tool" "${TEST_HOME}/opt/bin/profile-tool"
  printf 'export PATH="$HOME/opt/bin:$PATH"\n' >"${TEST_HOME}/.profile"

  run_cronrun --dry-run demo-job 'home-tool --flag'
  assert_same "0" "${RC}"
  assert_contains "first word: home-tool -> ${TEST_HOME}/bin/home-tool" "$(cat "${OUT_FILE}")"

  run_cronrun --dry-run demo-job '"$HOME/opt/bin/profile-tool"'
  assert_same "0" "${RC}"
  assert_contains "profile: sourced ${TEST_HOME}/.profile" "$(cat "${OUT_FILE}")"

  run_cronrun --dry-run demo-job 'profile-tool | cat'
  assert_same "0" "${RC}"
  assert_contains "first word: profile-tool -> ${TEST_HOME}/opt/bin/profile-tool" \
    "$(cat "${OUT_FILE}")"
}

function test_the_profile_is_sourced_and_its_failure_is_logged() {
  cat >"${TEST_HOME}/.profile" <<'EOF'
echo "profile noise"
export CRONRUN_TEST_VALUE=from-profile
declare -x CRONRUN_TEST_DECLARED=declared
return 3
EOF

  run_cronrun demo-job \
    'printf "%s %s\n" "$CRONRUN_TEST_VALUE" "$CRONRUN_TEST_DECLARED" >"$HOME/value"'

  assert_same "0" "${RC}"
  assert_empty "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"
  assert_same "from-profile declared" "$(cat "${TEST_HOME}/value")"
  local log
  log="$(cat "${STATE_DIR}/demo-job.log")"
  assert_contains "profile noise" "${log}"
  assert_contains "warning: sourcing ${TEST_HOME}/.profile failed (exit 3); continued" "${log}"
}

function test_the_runtime_env_is_derived_on_linux() {
  RUN_OS="Linux"
  make_socket "${SOCK_DIR}/run/user/$(id -u)/bus"
  make_socket "${SOCK_DIR}/x11/X0"

  run_cronrun demo-job 'env >"$HOME/env.out"'

  assert_same "0" "${RC}"
  local env_out
  env_out="$(cat "${TEST_HOME}/env.out")"
  assert_contains "XDG_RUNTIME_DIR=${SOCK_DIR}/run/user/$(id -u)" "${env_out}"
  assert_contains \
    "DBUS_SESSION_BUS_ADDRESS=unix:path=${SOCK_DIR}/run/user/$(id -u)/bus" "${env_out}"
  assert_contains "DISPLAY=:0" "${env_out}"

  run_cronrun --dry-run demo-job 'env'
  assert_contains "DISPLAY=:0 (derived by cronrun)" "$(cat "${OUT_FILE}")"
}

function test_the_runtime_env_is_only_set_when_unset() {
  RUN_OS="Linux"
  make_socket "${SOCK_DIR}/run/user/$(id -u)/bus"
  make_socket "${SOCK_DIR}/x11/X0"
  RUN_ENV=(DISPLAY=:7 XDG_RUNTIME_DIR="${TEST_TMP}/custom-runtime")

  run_cronrun demo-job 'env >"$HOME/env.out"'

  assert_same "0" "${RC}"
  local env_out
  env_out="$(cat "${TEST_HOME}/env.out")"
  assert_contains "DISPLAY=:7" "${env_out}"
  assert_not_contains "DISPLAY=:0" "${env_out}"
  assert_contains "XDG_RUNTIME_DIR=${TEST_TMP}/custom-runtime" "${env_out}"
  # The preset runtime dir has no bus socket, so no bus address is derived.
  assert_not_contains "DBUS_SESSION_BUS_ADDRESS=" "${env_out}"
}

function test_the_runtime_env_needs_linux_and_existing_targets() {
  RUN_OS="Linux"
  run_cronrun demo-job 'env >"$HOME/env.out"'
  assert_not_contains "XDG_RUNTIME_DIR=" "$(cat "${TEST_HOME}/env.out")"
  assert_not_contains "DISPLAY=" "$(cat "${TEST_HOME}/env.out")"

  RUN_OS="Darwin"
  make_socket "${SOCK_DIR}/run/user/$(id -u)/bus"
  make_socket "${SOCK_DIR}/x11/X0"
  run_cronrun demo-job 'env >"$HOME/env.out"'
  assert_not_contains "XDG_RUNTIME_DIR=" "$(cat "${TEST_HOME}/env.out")"
  assert_not_contains "DBUS_SESSION_BUS_ADDRESS=" "$(cat "${TEST_HOME}/env.out")"
  assert_not_contains "DISPLAY=" "$(cat "${TEST_HOME}/env.out")"
}

function test_usage_errors_exit_2_without_running() {
  run_cronrun
  assert_same "2" "${RC}"
  assert_contains "expected <job> <command>" "$(cat "${ERR_FILE}")"

  run_cronrun Bad_Name 'touch "$HOME/ran"'
  assert_same "2" "${RC}"
  assert_contains "invalid job name" "$(cat "${ERR_FILE}")"

  run_cronrun ../escape 'touch "$HOME/ran"'
  assert_same "2" "${RC}"

  run_cronrun demo-job '   '
  assert_same "2" "${RC}"
  assert_contains "empty command" "$(cat "${ERR_FILE}")"

  run_cronrun --bogus demo-job 'touch "$HOME/ran"'
  assert_same "2" "${RC}"

  assert_file_not_exists "${TEST_HOME}/ran"
  assert_same "absent" "$([[ -e "${STATE_DIR}" ]] && echo present || echo absent)"

  run_cronrun --help
  assert_same "0" "${RC}"
  assert_contains "usage: cronrun [-h] [--dry-run] <job> <command>" "$(cat "${OUT_FILE}")"
}
