#!/bin/bash

#################################################################################
# Regression tests for the scheduled Highlights scan gate.                      #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_maybe_bob_highlights_sync"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  TEST_HOME="${TEST_TMP}/home"
  BOB_DIR="${TEST_HOME}/bob"
  FAKE_BIN="${TEST_TMP}/bin"
  RUN_TMPDIR="${TEST_TMP}/run"
  CALLS_FILE="${TEST_TMP}/bob-calls.txt"

  mkdir -p "${FAKE_BIN}" "${RUN_TMPDIR}" "${BOB_DIR}"
  : >"${CALLS_FILE}"

  cat >"${FAKE_BIN}/bob" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >>"${CALLS_FILE}"
EOF
  chmod +x "${FAKE_BIN}/bob"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function run_sync_gate() {
  PATH="${FAKE_BIN}:/usr/bin:/bin" \
    HOME="${TEST_HOME}" \
    BOB_DIR="${BOB_DIR}" \
    BOB_HIGHLIGHTS_LIB_DIR="lib" \
    BOB_HIGHLIGHTS_XLIB_DIR="${RUN_XLIB_DIR:-xlib}" \
    BOB_HIGHLIGHTS_PRE_SCAN_HOOK="" \
    TMPDIR="${RUN_TMPDIR}" \
    CALLS_FILE="${CALLS_FILE}" \
    bash "${SCRIPT}" "$@"
}

function call_count() {
  wc -l <"${CALLS_FILE}" | tr -d '[:space:]'
}

function test_idle_vault_skips_the_scan() {
  mkdir -p "${BOB_DIR}/lib" "${BOB_DIR}/xlib"

  run_sync_gate

  assert_same "0" "$(call_count)"
}

function test_recent_library_file_still_runs_the_scan() {
  mkdir -p "${BOB_DIR}/lib"
  touch "${BOB_DIR}/lib/recent.pdf"

  run_sync_gate -w

  assert_same "1" "$(call_count)"
  assert_same "highlights scan -w" "$(cat "${CALLS_FILE}")"
}

function test_queued_xlib_file_runs_the_scan_without_a_library_directory() {
  mkdir -p "${BOB_DIR}/xlib"
  touch "${BOB_DIR}/xlib/queued.pdf"

  run_sync_gate

  assert_same "1" "$(call_count)"
  assert_same "highlights scan" "$(cat "${CALLS_FILE}")"
}

function test_configured_xlib_path_with_spaces_runs_the_scan() {
  local xlib_dir="${TEST_HOME}/queued references"
  mkdir -p "${xlib_dir}"
  touch "${xlib_dir}/queued.pdf"
  RUN_XLIB_DIR="${xlib_dir}"

  run_sync_gate

  assert_same "1" "$(call_count)"
}

function test_configured_hook_still_runs_when_vault_is_idle() {
  mkdir -p "${BOB_DIR}/lib" "${BOB_DIR}/xlib"

  PATH="${FAKE_BIN}:/usr/bin:/bin" \
    HOME="${TEST_HOME}" \
    BOB_DIR="${BOB_DIR}" \
    BOB_HIGHLIGHTS_LIB_DIR="lib" \
    BOB_HIGHLIGHTS_XLIB_DIR="xlib" \
    BOB_HIGHLIGHTS_PRE_SCAN_HOOK="echo custom" \
    TMPDIR="${RUN_TMPDIR}" \
    CALLS_FILE="${CALLS_FILE}" \
    bash "${SCRIPT}"

  assert_same "1" "$(call_count)"
}
