#!/bin/bash

#################################################################################
# Regression tests for `macscrot` parallel apollo/athena upload.                #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_macscrot"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  TEST_HOME="${TEST_TMP}/home"
  EVENT_LOG="${TEST_TMP}/events.log"
  STDOUT_FILE="${TEST_TMP}/stdout.log"
  STDERR_FILE="${TEST_TMP}/stderr.log"
  FAIL_HOST=""
  BLOCK_HOST=""
  CANCEL_CAPTURE="0"
  RUN_RC=0

  mkdir -p "${FAKE_BIN}" "${TEST_HOME}"
  : >"${EVENT_LOG}"

  export TEST_TMP EVENT_LOG

  write_screencapture_stub
  write_ssh_stub
  write_scp_stub
  write_pbcopy_stub
  write_osascript_stub
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function write_screencapture_stub() {
  cat >"${FAKE_BIN}/screencapture" <<'EOF'
#!/bin/bash
out="${!#}"
if [[ "${CANCEL_CAPTURE:-0}" == "1" ]]; then
  : >"${out}"
  exit 0
fi
printf 'fake-png\n' >"${out}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/screencapture"
}

function write_ssh_stub() {
  cat >"${FAKE_BIN}/ssh" <<'EOF'
#!/bin/bash
host=""
while (($# > 0)); do
  case "$1" in
  -o)
    shift 2
    ;;
  -*)
    shift
    ;;
  *)
    host="$1"
    shift
    break
    ;;
  esac
done
printf 'ssh-start|%s|%s\n' "${host}" "$*" >>"${EVENT_LOG}"
touch "${TEST_TMP}/ssh_started_${host}"
if [[ "${BLOCK_HOST:-}" == "${host}" ]]; then
  while [[ ! -e "${TEST_TMP}/release_${host}" ]]; do
    sleep 0.05
  done
fi
if [[ "${FAIL_HOST:-}" == "${host}" || "${FAIL_HOST:-}" == "both" ]]; then
  printf 'ssh-fail|%s\n' "${host}" >>"${EVENT_LOG}"
  exit 1
fi
printf 'ssh-mkdir|%s|%s\n' "${host}" "$*" >>"${EVENT_LOG}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/ssh"
}

function write_scp_stub() {
  cat >"${FAKE_BIN}/scp" <<'EOF'
#!/bin/bash
dest=""
for arg in "$@"; do
  dest="$arg"
done
host="${dest%%:*}"
printf 'scp-start|%s|%s\n' "${host}" "${dest}" >>"${EVENT_LOG}"
touch "${TEST_TMP}/scp_started_${host}"
if [[ "${BLOCK_HOST:-}" == "${host}" ]]; then
  while [[ ! -e "${TEST_TMP}/release_${host}" ]]; do
    sleep 0.05
  done
fi
if [[ "${FAIL_HOST:-}" == "${host}" || "${FAIL_HOST:-}" == "both" ]]; then
  printf 'scp-fail|%s\n' "${host}" >>"${EVENT_LOG}"
  exit 1
fi
printf 'scp-ok|%s|%s\n' "${host}" "${dest}" >>"${EVENT_LOG}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/scp"
}

function write_pbcopy_stub() {
  cat >"${FAKE_BIN}/pbcopy" <<'EOF'
#!/bin/bash
cat >"${TEST_TMP}/clipboard.txt"
exit 0
EOF
  chmod +x "${FAKE_BIN}/pbcopy"
}

function write_osascript_stub() {
  cat >"${FAKE_BIN}/osascript" <<'EOF'
#!/bin/bash
printf '%s\n' "$@" >"${TEST_TMP}/osascript.args"
exit 0
EOF
  chmod +x "${FAKE_BIN}/osascript"
}

function run_macscrot() {
  PATH="${FAKE_BIN}:${PATH}" \
    HOME="${TEST_HOME}" \
    SCREENCAPTURE_BIN="${FAKE_BIN}/screencapture" \
    TEST_TMP="${TEST_TMP}" \
    EVENT_LOG="${EVENT_LOG}" \
    FAIL_HOST="${FAIL_HOST}" \
    BLOCK_HOST="${BLOCK_HOST}" \
    CANCEL_CAPTURE="${CANCEL_CAPTURE}" \
    bash "${SCRIPT}" "$@" >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
  RUN_RC=$?
}

function test_both_hosts_succeed() {
  run_macscrot 10,20,30,40
  assert_equals "0" "${RUN_RC}"
  assert_contains "ssh-mkdir|apollo|" "$(cat "${EVENT_LOG}")"
  assert_contains "ssh-mkdir|athena|" "$(cat "${EVENT_LOG}")"
  assert_contains "scp-ok|apollo|" "$(cat "${EVENT_LOG}")"
  assert_contains "scp-ok|athena|" "$(cat "${EVENT_LOG}")"
  assert_contains "clipboard: ~/tmp/screenshots/" "$(cat "${STDOUT_FILE}")"
  assert_contains "apollo: ~/tmp/screenshots/" "$(cat "${STDOUT_FILE}")"
  assert_contains "athena: ~/tmp/screenshots/" "$(cat "${STDOUT_FILE}")"
}

function test_uploads_overlap_in_time() {
  PATH="${FAKE_BIN}:${PATH}" \
    HOME="${TEST_HOME}" \
    SCREENCAPTURE_BIN="${FAKE_BIN}/screencapture" \
    TEST_TMP="${TEST_TMP}" \
    EVENT_LOG="${EVENT_LOG}" \
    FAIL_HOST="" \
    BLOCK_HOST=apollo \
    CANCEL_CAPTURE=0 \
    bash "${SCRIPT}" 1,2,3,4 >"${STDOUT_FILE}" 2>"${STDERR_FILE}" &
  local pid=$!
  local waited=0
  while [[ ! -e "${TEST_TMP}/scp_started_athena" && "${waited}" -lt 40 ]]; do
    sleep 0.05
    waited=$((waited + 1))
  done
  assert_file_exists "${TEST_TMP}/scp_started_athena"
  assert_file_not_exists "${TEST_TMP}/release_apollo"
  touch "${TEST_TMP}/release_apollo"
  wait "${pid}"
  assert_equals "0" "$?"
}

function test_apollo_fails_athena_succeeds() {
  FAIL_HOST=apollo
  run_macscrot 1,2,3,4
  assert_equals "0" "${RUN_RC}"
  assert_contains "athena: ~/tmp/screenshots/" "$(cat "${STDOUT_FILE}")"
  assert_not_contains "apollo: ~/tmp/screenshots/" "$(cat "${STDOUT_FILE}")"
}

function test_athena_fails_apollo_succeeds() {
  FAIL_HOST=athena
  run_macscrot 1,2,3,4
  assert_equals "0" "${RUN_RC}"
  assert_contains "apollo: ~/tmp/screenshots/" "$(cat "${STDOUT_FILE}")"
  assert_not_contains "athena: ~/tmp/screenshots/" "$(cat "${STDOUT_FILE}")"
}

function test_both_hosts_fail() {
  FAIL_HOST=both
  run_macscrot 1,2,3,4
  assert_equals "1" "${RUN_RC}"
  assert_not_contains "clipboard:" "$(cat "${STDOUT_FILE}")"
}

function test_capture_cancelled_skips_upload() {
  CANCEL_CAPTURE=1
  run_macscrot 1,2,3,4
  assert_equals "1" "${RUN_RC}"
  assert_empty "$(cat "${EVENT_LOG}")"
  assert_contains "capture cancelled or empty" "$(cat "${STDERR_FILE}")"
}
