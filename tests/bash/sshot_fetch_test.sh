#!/bin/bash

#################################################################################
# Regression tests for `sshot_fetch` union listing across local/apollo/athena.  #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_sshot_fetch"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  TEST_HOME="${TEST_TMP}/home"
  EVENT_LOG="${TEST_TMP}/events.log"
  STDOUT_FILE="${TEST_TMP}/stdout.log"
  STDERR_FILE="${TEST_TMP}/stderr.log"
  CURRENT_HOST="macbook"
  APOLLO_LIST=""
  ATHENA_LIST=""
  APOLLO_FAIL="0"
  ATHENA_FAIL="0"
  SCP_FAIL_HOST=""
  RUN_RC=0

  mkdir -p "${FAKE_BIN}" "${TEST_HOME}/tmp/screenshots"
  : >"${EVENT_LOG}"

  export TEST_TMP EVENT_LOG

  write_hostname_stub
  write_ssh_stub
  write_scp_stub
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function write_hostname_stub() {
  cat >"${FAKE_BIN}/hostname" <<'EOF'
#!/bin/bash
printf '%s\n' "${CURRENT_HOST:-macbook}"
EOF
  chmod +x "${FAKE_BIN}/hostname"
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
printf 'ssh-list|%s\n' "${host}" >>"${EVENT_LOG}"
case "$host" in
apollo)
  if [[ "${APOLLO_FAIL:-0}" == "1" ]]; then
    exit 1
  fi
  if [[ -n "${APOLLO_LIST}" ]]; then
    printf '%s\n' ${APOLLO_LIST}
  fi
  ;;
athena)
  if [[ "${ATHENA_FAIL:-0}" == "1" ]]; then
    exit 1
  fi
  if [[ -n "${ATHENA_LIST}" ]]; then
    printf '%s\n' ${ATHENA_LIST}
  fi
  ;;
esac
exit 0
EOF
  chmod +x "${FAKE_BIN}/ssh"
}

function write_scp_stub() {
  cat >"${FAKE_BIN}/scp" <<'EOF'
#!/bin/bash
src=""
dest=""
for arg in "$@"; do
  src="${dest}"
  dest="$arg"
done
host="${src%%:*}"
printf 'scp|%s|%s\n' "${host}" "${dest}" >>"${EVENT_LOG}"
if [[ "${SCP_FAIL_HOST:-}" == "${host}" ]]; then
  exit 1
fi
mkdir -p "$(dirname "${dest}")"
printf 'copied-from-%s\n' "${host}" >"${dest}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/scp"
}

function run_fetch() {
  PATH="${FAKE_BIN}:${PATH}" \
    HOME="${TEST_HOME}" \
    TEST_TMP="${TEST_TMP}" \
    EVENT_LOG="${EVENT_LOG}" \
    CURRENT_HOST="${CURRENT_HOST}" \
    APOLLO_LIST="${APOLLO_LIST}" \
    ATHENA_LIST="${ATHENA_LIST}" \
    APOLLO_FAIL="${APOLLO_FAIL}" \
    ATHENA_FAIL="${ATHENA_FAIL}" \
    SCP_FAIL_HOST="${SCP_FAIL_HOST}" \
    bash "${SCRIPT}" "$@" >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
  RUN_RC=$?
}

function test_union_picks_nth_newest_basename() {
  printf 'local-old\n' >"${TEST_HOME}/tmp/screenshots/20260101_000000.png"
  APOLLO_LIST="20260919_120000.png"
  ATHENA_LIST="20260918_120000.png"
  run_fetch 1
  assert_equals "0" "${RUN_RC}"
  assert_contains "local_path=${TEST_HOME}/tmp/screenshots/20260919_120000.png" "$(cat "${STDOUT_FILE}")"
  assert_contains "scp|apollo|" "$(cat "${EVENT_LOG}")"
}

function test_skips_scp_when_chosen_file_is_local() {
  printf 'already-here\n' >"${TEST_HOME}/tmp/screenshots/20260919_150000.png"
  APOLLO_LIST="20260919_150000.png"
  run_fetch 1
  assert_equals "0" "${RUN_RC}"
  assert_contains "local_path=${TEST_HOME}/tmp/screenshots/20260919_150000.png" "$(cat "${STDOUT_FILE}")"
  assert_not_contains "scp|" "$(cat "${EVENT_LOG}")"
}

function test_apollo_listing_fail_still_returns_athena_file() {
  APOLLO_FAIL=1
  ATHENA_LIST="20260919_090000.png"
  run_fetch 1
  assert_equals "0" "${RUN_RC}"
  assert_contains "20260919_090000.png" "$(cat "${STDOUT_FILE}")"
  assert_contains "scp|athena|" "$(cat "${EVENT_LOG}")"
}

function test_rejects_n_less_than_one() {
  run_fetch 0
  assert_equals "1" "${RUN_RC}"
  assert_contains "n must be >= 1" "$(cat "${STDERR_FILE}")"
}

function test_missing_nth_entry_errors() {
  printf 'one\n' >"${TEST_HOME}/tmp/screenshots/20260919_010000.png"
  run_fetch 2
  assert_equals "1" "${RUN_RC}"
  assert_contains "no screenshot #2" "$(cat "${STDERR_FILE}")"
}
