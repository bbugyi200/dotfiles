#!/bin/bash

#################################################################################
# Regression tests for `bob_xlib_pull`.                                        #
#                                                                               #
# The live command talks to the Mac's tailnet peers and mutates xlib intake, so #
# the main harness stubs `uname`, `ssh`, and `rsync`.  The stubs log observable #
# behavior, support deterministic probe barriers, and keep all state under a    #
# throwaway test directory.                                                     #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_bob_xlib_pull"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  TEST_HOME="${TEST_TMP}/home"
  EVENT_LOG="${TEST_TMP}/events.log"
  STDOUT_FILE="${TEST_TMP}/stdout.log"
  STDERR_FILE="${TEST_TMP}/stderr.log"
  RUN_TMPDIR="${TEST_TMP}/run tmp"
  RUN_BOB_DIR="${TEST_HOME}/bob"
  RUN_XLIB_DIR="xlib"
  FAKE_UNAME="Darwin"
  ATHENA_PROBE="empty"
  APOLLO_PROBE="empty"
  PROBE_BARRIER="0"
  PROBE_BLOCK_HOST=""
  RSYNC_BLOCK_HOST=""
  RSYNC_DELAY="0"
  RSYNC_FAIL_HOST=""

  mkdir -p "${FAKE_BIN}" "${TEST_HOME}" "${RUN_TMPDIR}"
  : >"${EVENT_LOG}"

  export TEST_TMP EVENT_LOG

  write_uname_stub
  write_ssh_stub
  write_rsync_stub
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function write_uname_stub() {
  cat >"${FAKE_BIN}/uname" <<'EOF'
#!/bin/bash
printf '%s\n' "${FAKE_UNAME:-Darwin}"
EOF
  chmod +x "${FAKE_BIN}/uname"
}

function write_ssh_stub() {
  cat >"${FAKE_BIN}/ssh" <<'EOF'
#!/bin/bash

has_n=0
control_path=""
control_cmd=""
opts=()
host=""

while (($# > 0)); do
  case "$1" in
  -n)
    has_n=1
    shift
    ;;
  -S)
    control_path="$2"
    shift 2
    ;;
  -O)
    control_cmd="$2"
    shift 2
    ;;
  -o)
    opts+=("-o $2")
    shift 2
    ;;
  -*)
    opts+=("$1")
    shift
    ;;
  *)
    host="$1"
    shift
    break
    ;;
  esac
done

cmd="$*"
opts_text="${opts[*]}"

log() {
  printf '%s\n' "$*" >>"${EVENT_LOG}"
}

probe_mode() {
  case "$host" in
  athena)
    printf '%s\n' "${ATHENA_PROBE:-empty}"
    ;;
  apollo)
    printf '%s\n' "${APOLLO_PROBE:-empty}"
    ;;
  *)
    printf '%s\n' empty
    ;;
  esac
}

wait_for_file() {
  local file="$1"
  while [[ ! -e "${file}" ]]; do
    sleep 0.05
  done
}

if [[ "${control_cmd}" == "exit" ]]; then
  log "ssh-close|${host}|${control_path}|n=${has_n}"
  exit 0
fi

if [[ "${cmd}" == *'type d -empty -delete'* ]]; then
  log "cleanup|${host}|${control_path}|n=${has_n}|opts=${opts_text}"
  exit 0
fi

log "probe-start|${host}|${control_path}|n=${has_n}|opts=${opts_text}|cmd=${cmd}"
touch "${TEST_TMP}/probe_started_${host}"

if [[ "${PROBE_BARRIER:-0}" == "1" ]]; then
  wait_for_file "${TEST_TMP}/release_probes"
fi

if [[ "${PROBE_BLOCK_HOST:-}" == "${host}" ]]; then
  wait_for_file "${TEST_TMP}/release_${host}_probe"
fi

case "$(probe_mode)" in
pending)
  log "probe-end|${host}|pending"
  printf 'pending\n'
  ;;
empty | missing)
  log "probe-end|${host}|empty"
  printf 'empty\n'
  ;;
unreachable)
  log "probe-end|${host}|unreachable"
  printf 'ssh: connect to host %s timed out\n' "${host}" >&2
  exit 255
  ;;
traversal_error)
  log "probe-end|${host}|traversal_error"
  printf 'find: %s/bob/xlib: Permission denied\n' "${HOME}" >&2
  exit 7
  ;;
weird)
  log "probe-end|${host}|weird"
  printf 'surprise\n'
  ;;
esac
EOF
  chmod +x "${FAKE_BIN}/ssh"
}

function write_rsync_stub() {
  cat >"${FAKE_BIN}/rsync" <<'EOF'
#!/bin/bash

ssh_transport=""
source_arg=""
dest_arg=""

while (($# > 0)); do
  case "$1" in
  -e)
    ssh_transport="$2"
    shift 2
    ;;
  -*)
    shift
    ;;
  *)
    if [[ -z "${source_arg}" ]]; then
      source_arg="$1"
    else
      dest_arg="$1"
    fi
    shift
    ;;
  esac
done

host="${source_arg%%:*}"
control_path=""
read -r -a transport_parts <<<"${ssh_transport}"
for ((i = 0; i < ${#transport_parts[@]}; i++)); do
  if [[ "${transport_parts[$i]}" == "-S" ]]; then
    control_path="${transport_parts[$((i + 1))]}"
  fi
done

log() {
  printf '%s\n' "$*" >>"${EVENT_LOG}"
}

if ! mkdir "${TEST_TMP}/rsync_active" 2>/dev/null; then
  log "rsync-overlap|${host}"
fi

log "rsync-start|${host}|${control_path}|ssh=${ssh_transport}|src=${source_arg}|dest=${dest_arg}"
touch "${TEST_TMP}/rsync_started_${host}"

if [[ "${RSYNC_BLOCK_HOST:-}" == "${host}" ]]; then
  while [[ ! -e "${TEST_TMP}/release_${host}_rsync" ]]; do
    sleep 0.05
  done
fi

if [[ "${RSYNC_DELAY:-0}" != "0" ]]; then
  sleep "${RSYNC_DELAY}"
fi

if [[ "${RSYNC_FAIL_HOST:-}" == "${host}" ]]; then
  rmdir "${TEST_TMP}/rsync_active" 2>/dev/null || true
  log "rsync-fail|${host}"
  exit 23
fi

mkdir -p "${dest_arg}"
printf '%s\n' "${host}" >"${dest_arg}/${host}.txt"
rmdir "${TEST_TMP}/rsync_active" 2>/dev/null || true
log "rsync-end|${host}"
EOF
  chmod +x "${FAKE_BIN}/rsync"
}

function run_xlib_pull() {
  local rc=0

  env \
    HOME="${TEST_HOME}" \
    PATH="${FAKE_BIN}:${PATH}" \
    TMPDIR="${RUN_TMPDIR}" \
    BOB_DIR="${RUN_BOB_DIR}" \
    BOB_HIGHLIGHTS_XLIB_DIR="${RUN_XLIB_DIR}" \
    FAKE_UNAME="${FAKE_UNAME}" \
    ATHENA_PROBE="${ATHENA_PROBE}" \
    APOLLO_PROBE="${APOLLO_PROBE}" \
    PROBE_BARRIER="${PROBE_BARRIER}" \
    PROBE_BLOCK_HOST="${PROBE_BLOCK_HOST}" \
    RSYNC_BLOCK_HOST="${RSYNC_BLOCK_HOST}" \
    RSYNC_DELAY="${RSYNC_DELAY}" \
    RSYNC_FAIL_HOST="${RSYNC_FAIL_HOST}" \
    /bin/sh "${SCRIPT}" >"${STDOUT_FILE}" 2>"${STDERR_FILE}" || rc=$?

  RUN_RC="${rc}"
}

function start_xlib_pull() {
  env \
    HOME="${TEST_HOME}" \
    PATH="${FAKE_BIN}:${PATH}" \
    TMPDIR="${RUN_TMPDIR}" \
    BOB_DIR="${RUN_BOB_DIR}" \
    BOB_HIGHLIGHTS_XLIB_DIR="${RUN_XLIB_DIR}" \
    FAKE_UNAME="${FAKE_UNAME}" \
    ATHENA_PROBE="${ATHENA_PROBE}" \
    APOLLO_PROBE="${APOLLO_PROBE}" \
    PROBE_BARRIER="${PROBE_BARRIER}" \
    PROBE_BLOCK_HOST="${PROBE_BLOCK_HOST}" \
    RSYNC_BLOCK_HOST="${RSYNC_BLOCK_HOST}" \
    RSYNC_DELAY="${RSYNC_DELAY}" \
    RSYNC_FAIL_HOST="${RSYNC_FAIL_HOST}" \
    /bin/sh "${SCRIPT}" >"${STDOUT_FILE}" 2>"${STDERR_FILE}" &
  SCRIPT_PID=$!
}

function wait_for_script() {
  local rc=0
  wait "${SCRIPT_PID}" || rc=$?
  RUN_RC="${rc}"
}

function events() {
  cat "${EVENT_LOG}" 2>/dev/null
}

function stderr_text() {
  cat "${STDERR_FILE}" 2>/dev/null
}

function wait_for_file() {
  local file="$1"

  for _ in {1..200}; do
    if [[ -e "${file}" ]]; then
      return 0
    fi
    sleep 0.05
  done

  return 1
}

function event_count() {
  local needle="$1"
  grep -F -c "${needle}" "${EVENT_LOG}" 2>/dev/null || true
}

function first_field_value() {
  local event_name="$1" host="$2" field_number="$3"
  awk -F '|' -v event="${event_name}" -v host="${host}" -v field="${field_number}" \
    '$1 == event && $2 == host { print $field; exit }' "${EVENT_LOG}"
}

function rsync_dest() {
  local host="$1"
  awk -F '|' -v host="${host}" '
    $1 == "rsync-start" && $2 == host {
      sub(/^dest=/, "", $6)
      print $6
      exit
    }
  ' "${EVENT_LOG}"
}

function rsync_ssh() {
  local host="$1"
  awk -F '|' -v host="${host}" '
    $1 == "rsync-start" && $2 == host {
      sub(/^ssh=/, "", $4)
      print $4
      exit
    }
  ' "${EVENT_LOG}"
}

function lock_path() {
  printf '%s/bob_xlib_pull.lock\n' "${RUN_TMPDIR}"
}

function test_non_macos_exits_without_network_work() {
  FAKE_UNAME="Linux"

  run_xlib_pull

  assert_same "0" "${RUN_RC}"
  assert_empty "$(events)"
}

function test_existing_invocation_lock_exits_without_network_work() {
  mkdir -p "$(lock_path)"

  run_xlib_pull

  assert_same "0" "${RUN_RC}"
  assert_empty "$(events)"
  assert_directory_exists "$(lock_path)"
}

function test_both_hosts_are_checked_and_nonempty_hosts_are_pulled() {
  ATHENA_PROBE="pending"
  APOLLO_PROBE="pending"
  RSYNC_DELAY="0.1"

  run_xlib_pull

  assert_same "0" "${RUN_RC}"
  assert_same "1" "$(event_count "probe-start|athena|")"
  assert_same "1" "$(event_count "probe-start|apollo|")"
  assert_same "1" "$(event_count "rsync-start|athena|")"
  assert_same "1" "$(event_count "rsync-start|apollo|")"
  assert_same "1" "$(event_count "cleanup|athena|")"
  assert_same "1" "$(event_count "cleanup|apollo|")"
  assert_not_contains "rsync-overlap" "$(events)"
}

function test_probe_barrier_proves_both_checks_start_before_results_are_consumed() {
  ATHENA_PROBE="empty"
  APOLLO_PROBE="empty"
  PROBE_BARRIER="1"

  start_xlib_pull
  wait_for_file "${TEST_TMP}/probe_started_athena"
  wait_for_file "${TEST_TMP}/probe_started_apollo"

  assert_same "2" "$(event_count "probe-start|")"
  assert_not_contains "rsync-start" "$(events)"

  touch "${TEST_TMP}/release_probes"
  wait_for_script

  assert_same "0" "${RUN_RC}"
}

function test_blocked_apollo_probe_does_not_delay_ready_athena_transfer() {
  ATHENA_PROBE="pending"
  APOLLO_PROBE="empty"
  PROBE_BLOCK_HOST="apollo"

  start_xlib_pull
  wait_for_file "${TEST_TMP}/probe_started_apollo"
  wait_for_file "${TEST_TMP}/rsync_started_athena"

  assert_contains "rsync-start|athena|" "$(events)"
  assert_not_contains "probe-end|apollo" "$(events)"

  touch "${TEST_TMP}/release_apollo_probe"
  wait_for_script

  assert_same "0" "${RUN_RC}"
}

function test_empty_queues_skip_rsync_and_cleanup() {
  ATHENA_PROBE="empty"
  APOLLO_PROBE="missing"

  run_xlib_pull

  assert_same "0" "${RUN_RC}"
  assert_not_contains "rsync-start" "$(events)"
  assert_not_contains "cleanup|" "$(events)"
}

function test_unreachable_hosts_are_no_work_and_do_not_retry_through_transfer() {
  ATHENA_PROBE="unreachable"
  APOLLO_PROBE="pending"

  run_xlib_pull

  assert_same "0" "${RUN_RC}"
  assert_same "1" "$(event_count "probe-start|athena|")"
  assert_same "1" "$(event_count "probe-start|apollo|")"
  assert_not_contains "rsync-start|athena|" "$(events)"
  assert_contains "rsync-start|apollo|" "$(events)"
  assert_not_contains "cleanup|athena|" "$(events)"
}

function test_later_unreachable_host_still_allows_first_transfer() {
  ATHENA_PROBE="pending"
  APOLLO_PROBE="unreachable"

  run_xlib_pull

  assert_same "0" "${RUN_RC}"
  assert_contains "rsync-start|athena|" "$(events)"
  assert_not_contains "rsync-start|apollo|" "$(events)"
}

function test_traversal_errors_are_reported_as_failures() {
  ATHENA_PROBE="traversal_error"
  APOLLO_PROBE="empty"

  run_xlib_pull

  assert_same "1" "${RUN_RC}"
  assert_contains "athena probe failed" "$(stderr_text)"
  assert_contains "Permission denied" "$(stderr_text)"
  assert_not_contains "rsync-start|athena|" "$(events)"
}

function test_transfer_failure_survives_second_host_success_and_cleanup() {
  ATHENA_PROBE="pending"
  APOLLO_PROBE="pending"
  RSYNC_FAIL_HOST="athena"

  run_xlib_pull

  assert_same "1" "${RUN_RC}"
  assert_contains "athena transfer failed" "$(stderr_text)"
  assert_contains "rsync-start|apollo|" "$(events)"
  assert_not_contains "cleanup|athena|" "$(events)"
  assert_contains "cleanup|apollo|" "$(events)"
}

function test_probe_transfer_and_cleanup_reuse_the_same_control_path() {
  ATHENA_PROBE="pending"
  APOLLO_PROBE="empty"

  run_xlib_pull

  local probe_control rsync_control cleanup_control transport
  probe_control="$(first_field_value probe-start athena 3)"
  rsync_control="$(first_field_value rsync-start athena 3)"
  cleanup_control="$(first_field_value cleanup athena 3)"
  transport="$(rsync_ssh athena)"

  assert_same "${probe_control}" "${rsync_control}"
  assert_same "${probe_control}" "${cleanup_control}"
  assert_contains "ControlMaster=auto" "${transport}"
  assert_contains "ControlPersist=60" "${transport}"
  assert_contains "BatchMode=yes" "${transport}"
  assert_not_contains " -n " "${transport}"
}

function test_relative_xlib_dir_resolves_under_bob_dir_with_spaces() {
  ATHENA_PROBE="pending"
  RUN_BOB_DIR="~/Bob Root"
  RUN_XLIB_DIR="intake dir"

  run_xlib_pull

  assert_same "0" "${RUN_RC}"
  assert_same "${TEST_HOME}/Bob Root/intake dir/" "$(rsync_dest athena)"
}

function test_absolute_xlib_dir_is_preserved() {
  ATHENA_PROBE="pending"
  RUN_XLIB_DIR="${TEST_TMP}/absolute xlib"

  run_xlib_pull

  assert_same "0" "${RUN_RC}"
  assert_same "${TEST_TMP}/absolute xlib/" "$(rsync_dest athena)"
}

function test_home_relative_xlib_dir_is_expanded() {
  ATHENA_PROBE="pending"
  RUN_XLIB_DIR="~/personal xlib"

  run_xlib_pull

  assert_same "0" "${RUN_RC}"
  assert_same "${TEST_HOME}/personal xlib/" "$(rsync_dest athena)"
}

function test_long_spaced_tmpdir_only_holds_the_invocation_lock() {
  ATHENA_PROBE="pending"
  RUN_TMPDIR="${TEST_TMP}/a very long tmpdir with spaces/and/more/path/segments"
  mkdir -p "${RUN_TMPDIR}"

  run_xlib_pull

  local probe_control
  probe_control="$(first_field_value probe-start athena 3)"

  assert_same "0" "${RUN_RC}"
  assert_contains "/tmp/bob_xlib_pull." "${probe_control}"
  assert_not_contains "${RUN_TMPDIR}" "${probe_control}"
  assert_file_not_exists "$(lock_path)"
}

function test_rsync_source_path_and_stdin_sensitive_transport_are_preserved() {
  ATHENA_PROBE="pending"

  run_xlib_pull

  assert_contains "src=athena:bob/xlib/" "$(events)"
  assert_not_contains "ssh -n" "$(rsync_ssh athena)"
}

function test_signal_during_blocked_probe_reaps_workers_and_releases_lock() {
  ATHENA_PROBE="empty"
  APOLLO_PROBE="empty"
  PROBE_BLOCK_HOST="athena"

  start_xlib_pull
  wait_for_file "${TEST_TMP}/probe_started_athena"
  wait_for_file "${TEST_TMP}/probe_started_apollo"

  kill -TERM "${SCRIPT_PID}"
  wait_for_script

  assert_same "143" "${RUN_RC}"
  assert_file_not_exists "$(lock_path)"
  assert_not_contains "rsync-start" "$(events)"

  PROBE_BLOCK_HOST=""
  : >"${EVENT_LOG}"
  run_xlib_pull

  assert_same "0" "${RUN_RC}"
  assert_same "2" "$(event_count "probe-start|")"
}

function test_signal_during_transfer_reaps_worker_and_releases_lock() {
  ATHENA_PROBE="pending"
  APOLLO_PROBE="empty"
  RSYNC_BLOCK_HOST="athena"

  start_xlib_pull
  wait_for_file "${TEST_TMP}/rsync_started_athena"

  kill -TERM "${SCRIPT_PID}"
  wait_for_script
  touch "${TEST_TMP}/release_athena_rsync"
  sleep 0.1

  assert_same "143" "${RUN_RC}"
  assert_file_not_exists "$(lock_path)"
  assert_not_contains "rsync-end|athena" "$(events)"
  assert_file_not_exists "${RUN_BOB_DIR}/${RUN_XLIB_DIR}/athena.txt"

  RSYNC_BLOCK_HOST=""
  : >"${EVENT_LOG}"
  run_xlib_pull

  assert_same "0" "${RUN_RC}"
  assert_same "2" "$(event_count "probe-start|")"
}

function test_real_rsync_ignore_existing_keeps_collisions_on_the_source() {
  if ! command -v rsync >/dev/null 2>&1; then
    bashunit::skip "rsync is required for the real fixture check"
  fi

  local src_one="${TEST_TMP}/src one"
  local src_two="${TEST_TMP}/src two"
  local dest="${TEST_TMP}/dest"
  mkdir -p "${src_one}/nested" "${src_two}/nested" "${src_two}/bundle.textbundle" "${dest}"

  printf 'one\n' >"${src_one}/unique-one.pdf"
  printf 'markdown\n' >"${src_one}/nested/sidecar.md"
  printf 'two\n' >"${src_two}/unique-two.pdf"
  printf 'textbundle\n' >"${src_two}/bundle.textbundle/text.txt"
  printf 'source collision\n' >"${src_two}/collision.pdf"
  printf 'local collision\n' >"${dest}/collision.pdf"

  rsync -a --remove-source-files --ignore-existing "${src_one}/" "${dest}/"
  rsync -a --remove-source-files --ignore-existing "${src_two}/" "${dest}/"

  assert_same "one" "$(cat "${dest}/unique-one.pdf")"
  assert_same "markdown" "$(cat "${dest}/nested/sidecar.md")"
  assert_same "two" "$(cat "${dest}/unique-two.pdf")"
  assert_same "textbundle" "$(cat "${dest}/bundle.textbundle/text.txt")"
  assert_same "local collision" "$(cat "${dest}/collision.pdf")"
  assert_file_exists "${src_two}/collision.pdf"
  assert_file_not_exists "${src_one}/unique-one.pdf"
  assert_file_not_exists "${src_two}/unique-two.pdf"
}

function test_real_rsync_file_directory_collision_retains_source_data() {
  if ! command -v rsync >/dev/null 2>&1; then
    bashunit::skip "rsync is required for the real fixture check"
  fi

  local src="${TEST_TMP}/src shape"
  local dest="${TEST_TMP}/dest shape"
  local rc=0
  mkdir -p "${src}/shape" "${dest}"
  printf 'nested\n' >"${src}/shape/file.txt"
  printf 'existing file\n' >"${dest}/shape"

  rsync -a --remove-source-files --ignore-existing "${src}/" "${dest}/" \
    >"${TEST_TMP}/shape.out" 2>"${TEST_TMP}/shape.err" || rc=$?

  assert_same "existing file" "$(cat "${dest}/shape")"
  assert_file_exists "${src}/shape/file.txt"
  if [[ "${rc}" == "0" ]]; then
    assert_same "0" "${rc}"
  else
    assert_same "23" "${rc}"
  fi
}
