#!/bin/bash

#################################################################################
# Regression tests for `svid_fetch` union listing across local/apollo/athena,  #
# plus --sheet contact-sheet generation, caching, and summary output.           #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_svid_fetch"

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
  FFMPEG_HAS_DRAWTEXT="1"
  FFMPEG_FAIL="0"
  FFPROBE_DURATION="42.5"
  FFPROBE_DIMS="2560,1600"
  FFPROBE_AUDIO="0"
  DRAIN_STDIN=""
  RUN_RC=0

  mkdir -p "${FAKE_BIN}" "${TEST_HOME}/tmp/screencasts"
  : >"${EVENT_LOG}"

  export TEST_TMP EVENT_LOG

  write_hostname_stub
  write_ssh_stub
  write_scp_stub
  write_ffmpeg_stub
  write_ffprobe_stub
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
if [[ "${DRAIN_STDIN:-}" == ssh ]]; then
  cat >/dev/null
  printf 'stdin-drained|ssh\n' >>"${EVENT_LOG}"
fi
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

function write_ffmpeg_stub() {
  cat >"${FAKE_BIN}/ffmpeg" <<'EOF'
#!/bin/bash
if [[ "${DRAIN_STDIN:-}" == ffmpeg ]]; then
  cat >/dev/null
  printf 'stdin-drained|ffmpeg\n' >>"${EVENT_LOG}"
fi
has_filters=0
vf=""
last=""
prev=""
for a in "$@"; do
  if [[ "${prev}" == "-vf" ]]; then
    vf="$a"
  fi
  if [[ "$a" == "-filters" ]]; then
    has_filters=1
  fi
  prev="$a"
  last="$a"
done
if [[ "${has_filters}" == "1" ]]; then
  printf 'ffmpeg|filters\n' >>"${EVENT_LOG}"
  if [[ "${FFMPEG_HAS_DRAWTEXT:-1}" == "1" ]]; then
    printf ' TSC drawtext          V->V      Draw text on top of video frames.\n'
  fi
  exit 0
fi
printf 'ffmpeg|vf|%s\n' "${vf}" >>"${EVENT_LOG}"
if [[ "${FFMPEG_FAIL:-0}" == "1" ]]; then
  exit 1
fi
mkdir -p "$(dirname "${last}")"
printf 'fake-sheet\n' >"${last}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/ffmpeg"
}

function write_ffprobe_stub() {
  cat >"${FAKE_BIN}/ffprobe" <<'EOF'
#!/bin/bash
printf 'ffprobe|%s\n' "$*" >>"${EVENT_LOG}"
args="$*"
if [[ "${args}" == *"format=duration"* ]]; then
  printf '%s\n' "${FFPROBE_DURATION:-42.5}"
elif [[ "${args}" == *"stream=width,height"* ]]; then
  printf '%s\n' "${FFPROBE_DIMS:-2560,1600}"
elif [[ "${args}" == *"stream=codec_type"* ]]; then
  printf 'video\n'
  if [[ "${FFPROBE_AUDIO:-0}" == "1" ]]; then
    printf 'audio\n'
  fi
fi
exit 0
EOF
  chmod +x "${FAKE_BIN}/ffprobe"
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
    FFMPEG_HAS_DRAWTEXT="${FFMPEG_HAS_DRAWTEXT}" \
    FFMPEG_FAIL="${FFMPEG_FAIL}" \
    FFPROBE_DURATION="${FFPROBE_DURATION}" \
    FFPROBE_DIMS="${FFPROBE_DIMS}" \
    FFPROBE_AUDIO="${FFPROBE_AUDIO}" \
    DRAIN_STDIN="${DRAIN_STDIN}" \
    bash "${SCRIPT}" "$@" >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
  RUN_RC=$?
}

function test_union_picks_nth_newest_basename() {
  printf 'local-old\n' >"${TEST_HOME}/tmp/screencasts/20260101_000000.mp4"
  APOLLO_LIST="20260919_120000.mp4"
  ATHENA_LIST="20260918_120000.mp4"
  run_fetch 1
  assert_equals "0" "${RUN_RC}"
  assert_contains "local_path=${TEST_HOME}/tmp/screencasts/20260919_120000.mp4" "$(cat "${STDOUT_FILE}")"
  assert_contains "scp|apollo|" "$(cat "${EVENT_LOG}")"
}

function test_skips_scp_when_chosen_file_is_local() {
  printf 'already-here\n' >"${TEST_HOME}/tmp/screencasts/20260919_150000.mp4"
  APOLLO_LIST="20260919_150000.mp4"
  run_fetch 1
  assert_equals "0" "${RUN_RC}"
  assert_contains "local_path=${TEST_HOME}/tmp/screencasts/20260919_150000.mp4" "$(cat "${STDOUT_FILE}")"
  assert_not_contains "scp|" "$(cat "${EVENT_LOG}")"
}

function test_apollo_listing_fail_still_returns_athena_file() {
  APOLLO_FAIL=1
  ATHENA_LIST="20260919_090000.mp4"
  run_fetch 1
  assert_equals "0" "${RUN_RC}"
  assert_contains "20260919_090000.mp4" "$(cat "${STDOUT_FILE}")"
  assert_contains "scp|athena|" "$(cat "${EVENT_LOG}")"
}

function test_rejects_n_less_than_one() {
  run_fetch 0
  assert_equals "1" "${RUN_RC}"
  assert_contains "n must be >= 1" "$(cat "${STDERR_FILE}")"
}

function test_missing_nth_entry_errors() {
  printf 'one\n' >"${TEST_HOME}/tmp/screencasts/20260919_010000.mp4"
  run_fetch 2
  assert_equals "1" "${RUN_RC}"
  assert_contains "no screen recording #2" "$(cat "${STDERR_FILE}")"
}

function test_sheet_builds_sheet_and_summary() {
  head -c 5242880 /dev/zero >"${TEST_HOME}/tmp/screencasts/20260919_150000.mp4"
  run_fetch 1 --sheet
  assert_equals "0" "${RUN_RC}"
  assert_contains "local_path=${TEST_HOME}/tmp/screencasts/20260919_150000.mp4" "$(cat "${STDOUT_FILE}")"
  assert_contains "sheet_path=${TEST_HOME}/tmp/screencasts/.sheets/20260919_150000.jpg" "$(cat "${STDOUT_FILE}")"
  assert_contains "summary=0:42 · 5.0 MB · 2560×1600 · silent" "$(cat "${STDOUT_FILE}")"
  assert_contains "drawtext" "$(cat "${EVENT_LOG}")"
  [ -s "${TEST_HOME}/tmp/screencasts/.sheets/20260919_150000.jpg" ]
  assert_equals "0" "$?"
}

function test_sheet_uses_ten_frame_contact_sheet_filter() {
  printf 'clip\n' >"${TEST_HOME}/tmp/screencasts/20260919_150000.mp4"
  run_fetch 1 --sheet
  assert_equals "0" "${RUN_RC}"
  assert_contains "fps=10/43" "$(cat "${EVENT_LOG}")"
  assert_contains "tile=5x2" "$(cat "${EVENT_LOG}")"
  assert_contains "scale=384:-1" "$(cat "${EVENT_LOG}")"
}

function test_sheet_is_cached_on_second_run() {
  printf 'clip\n' >"${TEST_HOME}/tmp/screencasts/20260919_150000.mp4"
  touch -t 200101010000 "${TEST_HOME}/tmp/screencasts/20260919_150000.mp4"
  run_fetch 1 --sheet
  assert_equals "0" "${RUN_RC}"
  run_fetch 1 --sheet
  assert_equals "0" "${RUN_RC}"
  assert_equals "1" "$(grep -c '^ffmpeg|vf|' "${EVENT_LOG}")"
}

function test_sheet_without_drawtext_falls_back() {
  FFMPEG_HAS_DRAWTEXT=0
  printf 'clip\n' >"${TEST_HOME}/tmp/screencasts/20260919_150000.mp4"
  run_fetch 1 --sheet
  assert_equals "0" "${RUN_RC}"
  assert_contains "sheet_path=${TEST_HOME}/tmp/screencasts/.sheets/20260919_150000.jpg" "$(cat "${STDOUT_FILE}")"
  assert_not_contains "drawtext" "$(grep '^ffmpeg|vf|' "${EVENT_LOG}")"
}

function test_sheet_failure_errors() {
  FFMPEG_FAIL=1
  printf 'clip\n' >"${TEST_HOME}/tmp/screencasts/20260919_150000.mp4"
  run_fetch 1 --sheet
  assert_equals "1" "${RUN_RC}"
  assert_contains "failed to build contact sheet" "$(cat "${STDERR_FILE}")"
}

function test_summary_reports_mic_when_audio_present() {
  FFPROBE_AUDIO=1
  printf 'clip\n' >"${TEST_HOME}/tmp/screencasts/20260919_150000.mp4"
  run_fetch 1 --sheet
  assert_equals "0" "${RUN_RC}"
  assert_contains "· mic" "$(cat "${STDOUT_FILE}")"
}

function check_caller_stdin_is_preserved() {
  local remaining=""
  printf 'clip\n' >"${TEST_HOME}/tmp/screencasts/20260919_150000.mp4"
  printf 'caller-still-running\n' >"${TEST_TMP}/stdin"
  {
    run_fetch 1 --sheet
    IFS= read -r remaining || true
  } <"${TEST_TMP}/stdin"
  assert_equals "0" "${RUN_RC}"
  assert_contains "stdin-drained|${DRAIN_STDIN}" "$(cat "${EVENT_LOG}")"
  assert_contains "sheet_path=" "$(cat "${STDOUT_FILE}")"
  assert_equals "caller-still-running" "${remaining}"
}

function test_ssh_preserves_caller_stdin() {
  DRAIN_STDIN=ssh
  check_caller_stdin_is_preserved
}

function test_ffmpeg_preserves_caller_stdin() {
  DRAIN_STDIN=ffmpeg
  check_caller_stdin_is_preserved
}
