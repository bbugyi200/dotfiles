#!/bin/bash

#################################################################################
# Regression tests for `macrec_ship` validate/encode/poster/publish/notify.    #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_macrec_ship"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  TEST_HOME="${TEST_TMP}/home"
  EVENT_LOG="${TEST_TMP}/events.log"
  STDOUT_FILE="${TEST_TMP}/stdout.log"
  STDERR_FILE="${TEST_TMP}/stderr.log"
  RUN_RC=0

  FFPROBE_DURATION="42.5"
  FFPROBE_DIMS="2560,1600"
  FFPROBE_AUDIO="0"
  FFPROBE_INVALID="0"
  FFMPEG_FAIL_LIBX264="0"
  FFMPEG_FAIL_VT="0"
  FFMPEG_FAIL_COPY="0"
  SSH_FAIL_HOST=""
  SCP_FAIL_HOST=""
  DF_FREE_APOLLO_KB="20000000"
  DF_FREE_ATHENA_KB="20000000"
  PGREP_RC="1"
  IMPORT_ID="importid1"
  REAL_FFMPEG=""
  REAL_FFPROBE=""

  mkdir -p "${FAKE_BIN}" "${TEST_HOME}"
  mkdir -p "${TEST_TMP}/remote/apollo/home/tmp/screencasts"
  mkdir -p "${TEST_TMP}/remote/athena/home/tmp/screencasts"
  : >"${EVENT_LOG}"

  export TEST_TMP EVENT_LOG
  export MACREC_SHIP_NO_REEXEC=1
  export MACREC_SHIP_RETRY_DELAY=0
  export MACREC_SHIP_ACK_WAIT=0.3
  export MACREC_SHIP_POLL_INTERVAL=0.02
  export MACREC_SHIP_TOLERANCE=2.0

  write_ffprobe_stub
  write_ffmpeg_stub
  write_ssh_stub
  write_scp_stub
  write_osascript_stub
  write_pgrep_stub
  write_uuidgen_stub
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function write_ffprobe_stub() {
  cat >"${FAKE_BIN}/ffprobe" <<'EOF'
#!/bin/bash
printf 'ffprobe|%s\n' "$*" >>"${EVENT_LOG}"
case "$*" in
*format=duration*)
  printf '%s\n' "${FFPROBE_DURATION:-}"
  ;;
*stream=width,height*)
  printf '%s\n' "${FFPROBE_DIMS:-2560,1600}"
  ;;
*stream=codec_type*)
  if [[ "${FFPROBE_INVALID:-0}" == "1" ]]; then
    printf 'data\n'
  else
    printf 'video\n'
    if [[ "${FFPROBE_AUDIO:-0}" == "1" ]]; then
      printf 'audio\n'
    fi
  fi
  ;;
esac
exit 0
EOF
  chmod +x "${FAKE_BIN}/ffprobe"
}

function write_ffmpeg_stub() {
  cat >"${FAKE_BIN}/ffmpeg" <<'EOF'
#!/bin/bash
printf 'ffmpeg|%s\n' "$*" >>"${EVENT_LOG}"
last=""
for a in "$@"; do
  last="$a"
done
joined=" $* "
if [[ "${joined}" == *"scale=640"* ]]; then
  mkdir -p "$(dirname "${last}")"
  printf 'fake-poster\n' >"${last}"
  exit 0
fi
if [[ "${joined}" == *"libx264"* && "${FFMPEG_FAIL_LIBX264:-0}" == "1" ]]; then
  exit 1
fi
if [[ "${joined}" == *"h264_videotoolbox"* && "${FFMPEG_FAIL_VT:-0}" == "1" ]]; then
  exit 1
fi
if [[ "${joined}" == *" -c copy "* && "${FFMPEG_FAIL_COPY:-0}" == "1" ]]; then
  exit 1
fi
mkdir -p "$(dirname "${last}")"
printf 'fake-mp4-bytes\n' >"${last}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/ffmpeg"
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
remote="$*"
printf 'ssh|%s|%s\n' "${host}" "${remote}" >>"${EVENT_LOG}"
if [[ "${host}" == "apollo" && ("${SSH_FAIL_HOST:-}" == "apollo" || "${SSH_FAIL_HOST:-}" == "both") ]]; then
  exit 1
fi
if [[ "${host}" == "athena" && ("${SSH_FAIL_HOST:-}" == "athena" || "${SSH_FAIL_HOST:-}" == "both") ]]; then
  exit 1
fi
if [[ "${remote}" == *"df -Pk"* ]]; then
  if [[ "${host}" == "apollo" ]]; then
    free="${DF_FREE_APOLLO_KB:-20000000}"
  else
    free="${DF_FREE_ATHENA_KB:-20000000}"
  fi
  printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n'
  printf '/dev/disk1 100000000 90000000 %s 90%% /System/Volumes/Data\n' "${free}"
  exit 0
fi
export HOME="${TEST_TMP}/remote/${host}/home"
mkdir -p "${HOME}/tmp/screencasts"
bash -c "${remote}"
EOF
  chmod +x "${FAKE_BIN}/ssh"
}

function write_scp_stub() {
  cat >"${FAKE_BIN}/scp" <<'EOF'
#!/bin/bash
pos=()
while (($# > 0)); do
  case "$1" in
  -o)
    shift 2
    ;;
  -*)
    shift
    ;;
  *)
    pos+=("$1")
    shift
    ;;
  esac
done
src="${pos[0]}"
dest="${pos[1]}"
host="${dest%%:*}"
rpath="${dest#*:}"
printf 'scp|%s|%s\n' "${host}" "${dest}" >>"${EVENT_LOG}"
if [[ "${host}" == "apollo" && ("${SSH_FAIL_HOST:-}" == "apollo" || "${SSH_FAIL_HOST:-}" == "both") ]]; then
  exit 1
fi
if [[ "${host}" == "athena" && ("${SSH_FAIL_HOST:-}" == "athena" || "${SSH_FAIL_HOST:-}" == "both") ]]; then
  exit 1
fi
if [[ "${host}" == "${SCP_FAIL_HOST:-}" ]]; then
  exit 1
fi
expanded="${rpath/#\~/${TEST_TMP}/remote/${host}/home}"
mkdir -p "$(dirname "${expanded}")"
cp "${src}" "${expanded}"
EOF
  chmod +x "${FAKE_BIN}/scp"
}

function write_osascript_stub() {
  cat >"${FAKE_BIN}/osascript" <<'EOF'
#!/bin/bash
printf 'osascript|%s\n' "$*" >>"${EVENT_LOG}"
printf '%s\n' "$@" >"${TEST_TMP}/osascript.args"
exit 0
EOF
  chmod +x "${FAKE_BIN}/osascript"
}

function write_pgrep_stub() {
  cat >"${FAKE_BIN}/pgrep" <<'EOF'
#!/bin/bash
exit "${PGREP_RC:-1}"
EOF
  chmod +x "${FAKE_BIN}/pgrep"
}

function write_uuidgen_stub() {
  cat >"${FAKE_BIN}/uuidgen" <<'EOF'
#!/bin/bash
printf '%s\n' "${IMPORT_ID:-importid1}"
EOF
  chmod +x "${FAKE_BIN}/uuidgen"
}

function run_ship() {
  PATH="${FAKE_BIN}:${PATH}" \
    HOME="${TEST_HOME}" \
    TEST_TMP="${TEST_TMP}" \
    EVENT_LOG="${EVENT_LOG}" \
    FFMPEG_BIN="${REAL_FFMPEG:-${FAKE_BIN}/ffmpeg}" \
    FFPROBE_BIN="${REAL_FFPROBE:-${FAKE_BIN}/ffprobe}" \
    SSH_BIN="${FAKE_BIN}/ssh" \
    SCP_BIN="${FAKE_BIN}/scp" \
    OSASCRIPT_BIN="${FAKE_BIN}/osascript" \
    PGREP_BIN="${FAKE_BIN}/pgrep" \
    UUIDGEN_BIN="${FAKE_BIN}/uuidgen" \
    JQ_BIN="$(command -v jq)" \
    PERL_BIN="$(command -v perl)" \
    MACREC_SHIP_NO_REEXEC=1 \
    MACREC_SHIP_RETRY_DELAY=0 \
    MACREC_SHIP_ACK_WAIT=0.3 \
    MACREC_SHIP_POLL_INTERVAL=0.02 \
    MACREC_SHIP_TOLERANCE=2.0 \
    FFPROBE_DURATION="${FFPROBE_DURATION}" \
    FFPROBE_DIMS="${FFPROBE_DIMS}" \
    FFPROBE_AUDIO="${FFPROBE_AUDIO}" \
    FFPROBE_INVALID="${FFPROBE_INVALID}" \
    FFMPEG_FAIL_LIBX264="${FFMPEG_FAIL_LIBX264}" \
    FFMPEG_FAIL_VT="${FFMPEG_FAIL_VT}" \
    FFMPEG_FAIL_COPY="${FFMPEG_FAIL_COPY}" \
    SSH_FAIL_HOST="${SSH_FAIL_HOST}" \
    SCP_FAIL_HOST="${SCP_FAIL_HOST}" \
    DF_FREE_APOLLO_KB="${DF_FREE_APOLLO_KB}" \
    DF_FREE_ATHENA_KB="${DF_FREE_ATHENA_KB}" \
    PGREP_RC="${PGREP_RC}" \
    IMPORT_ID="${IMPORT_ID}" \
    bash "${SCRIPT}" "$@" >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
  RUN_RC=$?
}

function make_session() {
  local id="$1"
  local stop_reason="${2:-chord}"
  local sdir="${TEST_HOME}/tmp/screencasts/.macrec/sessions/${id}"
  mkdir -p "${sdir}"
  printf 'fake-raw-mov-bytes\n' >"${sdir}/raw.mov"
  local now started ended
  now="$(date +%s)"
  started="$((now - 50))"
  ended="$((now - 8))"
  jq -n -c --arg id "${id}" --argjson started "${started}" \
    --argjson ended "${ended}" --arg reason "${stop_reason}" '{
    schema: 1, id: $id, name: "20261115_142233",
    region: {x: 0, y: 0, w: 1280, h: 720},
    mic: false, probe: false, cap_seconds: 600,
    started_at: $started, ended_at: $ended, updated_at: $started,
    status: "recording", stop_reason: $reason,
    duration_s: 0, bytes: 0, width: 0, height: 0, has_audio: false,
    mp4: "", poster: "",
    hosts: {apollo: "pending", athena: "pending"},
    host_detail: {apollo: "", athena: ""},
    error: "", recovered: false
  }' >"${sdir}/session.json"
}

function sget() {
  jq -r "$2" "${TEST_HOME}/tmp/screencasts/.macrec/sessions/$1/session.json"
}

function test_happy_path_to_both_hosts() {
  make_session s1
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget s1 '.status')"
  assert_equals "ok" "$(sget s1 '.hosts.apollo')"
  assert_equals "ok" "$(sget s1 '.hosts.athena')"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/20261115_142233.mp4"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/.macrec/sessions/s1/poster.jpg"
  assert_file_not_exists "${TEST_HOME}/tmp/screencasts/.macrec/sessions/s1/raw.mov"
  assert_file_not_exists "${TEST_HOME}/tmp/screencasts/20261115_142233.part.mp4"
  assert_file_exists "${TEST_TMP}/remote/apollo/home/tmp/screencasts/20261115_142233.mp4"
  assert_file_exists "${TEST_TMP}/remote/athena/home/tmp/screencasts/20261115_142233.mp4"
  assert_contains "scp|apollo|" "$(cat "${EVENT_LOG}")"
  assert_contains "scp|athena|" "$(cat "${EVENT_LOG}")"
  assert_contains "Recording uploaded" "$(cat "${TEST_TMP}/osascript.args")"
  assert_contains "~/tmp/screencasts/20261115_142233.mp4" "$(cat "${TEST_TMP}/osascript.args")"
  assert_equals "42.5" "$(sget s1 '.duration_s')"
}

function test_atomic_part_rename_leaves_no_parts() {
  make_session s1
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "" "$(ls "${TEST_HOME}/tmp/screencasts" | grep -F '.part' || true)"
  assert_equals "" "$(ls -a "${TEST_TMP}/remote/apollo/home/tmp/screencasts" | grep -F '.part' || true)"
  assert_equals "" "$(ls -a "${TEST_TMP}/remote/athena/home/tmp/screencasts" | grep -F '.part' || true)"
  cmp "${TEST_HOME}/tmp/screencasts/20261115_142233.mp4" \
    "${TEST_TMP}/remote/apollo/home/tmp/screencasts/20261115_142233.mp4"
  assert_equals "0" "$?"
}

function test_one_host_down_still_succeeds() {
  SSH_FAIL_HOST="apollo"
  make_session s1
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget s1 '.status')"
  assert_equals "failed" "$(sget s1 '.hosts.apollo')"
  assert_equals "ok" "$(sget s1 '.hosts.athena')"
  assert_file_not_exists "${TEST_HOME}/tmp/screencasts/.macrec/sessions/s1/raw.mov"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/20261115_142233.mp4"
  assert_equals "ssh probe failed" "$(sget s1 '.host_detail.apollo')"
}

function test_scp_failure_retries_once_then_marks_host_failed() {
  SCP_FAIL_HOST="apollo"
  make_session s1
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget s1 '.status')"
  assert_equals "failed" "$(sget s1 '.hosts.apollo')"
  assert_equals "upload failed" "$(sget s1 '.host_detail.apollo')"
  assert_equals "ok" "$(sget s1 '.hosts.athena')"
  assert_equals "2" "$(grep -c 'scp|apollo|' "${EVENT_LOG}")"
}

function test_both_hosts_down_fails_and_keeps_raw() {
  SSH_FAIL_HOST="both"
  make_session s1
  run_ship --session s1
  assert_equals "1" "${RUN_RC}"
  assert_equals "failed" "$(sget s1 '.status')"
  assert_equals "failed" "$(sget s1 '.hosts.apollo')"
  assert_equals "failed" "$(sget s1 '.hosts.athena')"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/.macrec/sessions/s1/raw.mov"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/20261115_142233.mp4"
  assert_contains "Recording not uploaded" "$(cat "${TEST_TMP}/osascript.args")"
}

function test_apollo_low_disk_skips_with_reason() {
  DF_FREE_APOLLO_KB="1048576"
  make_session s1
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget s1 '.status')"
  assert_equals "skipped" "$(sget s1 '.hosts.apollo')"
  assert_equals "ok" "$(sget s1 '.hosts.athena')"
  assert_contains "low disk (1.0 GiB free)" "$(sget s1 '.host_detail.apollo')"
  assert_not_contains "scp|apollo|" "$(cat "${EVENT_LOG}")"
  assert_contains "scp|athena|" "$(cat "${EVENT_LOG}")"
  assert_contains "apollo skipped" "$(cat "${TEST_TMP}/osascript.args")"
}

function test_prune_deletes_oldest_and_never_new() {
  local rdir="${TEST_TMP}/remote/apollo/home/tmp/screencasts"
  truncate -s 1500M "${rdir}/20250101_000000.mp4"
  truncate -s 1000M "${rdir}/20250102_000000.mp4"
  make_session s1
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_file_not_exists "${rdir}/20250101_000000.mp4"
  assert_file_exists "${rdir}/20250102_000000.mp4"
  assert_file_exists "${rdir}/20261115_142233.mp4"
}

function test_encoder_falls_back_to_videotoolbox() {
  FFMPEG_FAIL_LIBX264="1"
  make_session s1
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget s1 '.status')"
  assert_contains "h264_videotoolbox" "$(cat "${EVENT_LOG}")"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/20261115_142233.mp4"
}

function test_encoder_falls_back_to_copy_remux() {
  FFMPEG_FAIL_LIBX264="1"
  FFMPEG_FAIL_VT="1"
  make_session s1
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget s1 '.status')"
  assert_contains " -c copy " "$(cat "${EVENT_LOG}")"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/20261115_142233.mp4"
}

function test_encoder_falls_back_to_mov_under_true_extension() {
  FFMPEG_FAIL_LIBX264="1"
  FFMPEG_FAIL_VT="1"
  FFMPEG_FAIL_COPY="1"
  make_session s1
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget s1 '.status')"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/20261115_142233.mov"
  assert_contains ".mov" "$(sget s1 '.mp4')"
  assert_contains "scp|apollo|" "$(cat "${EVENT_LOG}")"
  assert_file_exists "${TEST_TMP}/remote/athena/home/tmp/screencasts/20261115_142233.mov"
}

function test_truncated_raw_fails_with_raw_kept() {
  FFPROBE_INVALID="1"
  FFPROBE_DURATION=""
  make_session s1
  run_ship --session s1
  assert_equals "1" "${RUN_RC}"
  assert_equals "failed" "$(sget s1 '.status')"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/.macrec/sessions/s1/raw.mov"
  assert_not_contains "scp|" "$(cat "${EVENT_LOG}")"
  assert_contains "Recording not uploaded" "$(cat "${TEST_TMP}/osascript.args")"
}

function test_retry_publishes_only_failed_hosts_without_reencoding() {
  SSH_FAIL_HOST="apollo"
  make_session s1
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "failed" "$(sget s1 '.hosts.apollo')"
  local encodes_before
  encodes_before="$(grep -c -e 'libx264' -e 'h264_videotoolbox' -e ' -c copy ' "${EVENT_LOG}")"
  local scp_athena_before
  scp_athena_before="$(grep -c 'scp|athena|' "${EVENT_LOG}")"
  SSH_FAIL_HOST=""
  run_ship --session s1 --retry
  assert_equals "0" "${RUN_RC}"
  assert_equals "ok" "$(sget s1 '.hosts.apollo')"
  assert_equals "ok" "$(sget s1 '.hosts.athena')"
  assert_equals "${encodes_before}" "$(grep -c -e 'libx264' -e 'h264_videotoolbox' -e ' -c copy ' "${EVENT_LOG}")"
  assert_equals "${scp_athena_before}" "$(grep -c 'scp|athena|' "${EVENT_LOG}")"
  assert_contains "scp|apollo|" "$(cat "${EVENT_LOG}")"
}

function test_import_builds_session_and_ships() {
  printf 'fake-import-mov-bytes\n' >"${TEST_TMP}/clip.mov"
  run_ship --import "${TEST_TMP}/clip.mov" --name acceptance_77
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget importid1 '.status')"
  assert_equals "import" "$(sget importid1 '.stop_reason')"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/acceptance_77.mp4"
  assert_contains "acceptance_77" "$(cat "${STDOUT_FILE}")"
  assert_contains "scp|apollo|" "$(cat "${EVENT_LOG}")"
  assert_equals "" "$(cat "${STDERR_FILE}")"
}

function test_import_defaults_name_from_basename() {
  printf 'fake-import-mov-bytes\n' >"${TEST_TMP}/myclip.mov"
  IMPORT_ID="importid2"
  run_ship --import "${TEST_TMP}/myclip.mov"
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget importid2 '.status')"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/myclip.mp4"
}

function test_real_encode_preserves_small_regions_and_caps_large_regions() {
  REAL_FFMPEG="$(command -v ffmpeg || true)"
  REAL_FFPROBE="$(command -v ffprobe || true)"
  if [[ -z "${REAL_FFMPEG}" || -z "${REAL_FFPROBE}" ]]; then
    bashunit::skip "ffmpeg and ffprobe are required for the real media regression"
    return
  fi
  local size expected output
  for size in 640x360 3000x1800 1800x3000; do
    case "${size}" in
      640x360) expected="640,360" ;;
      3000x1800) expected="2560,1536" ;;
      1800x3000) expected="1536,2560" ;;
    esac
    "${REAL_FFMPEG}" -v error -f lavfi -i "color=size=${size}:rate=30:duration=0.2" \
      -c:v libx264 -threads 1 "${TEST_TMP}/${size}.mov"
    assert_equals "0" "$?"
    IMPORT_ID="real_${size}"
    run_ship --import "${TEST_TMP}/${size}.mov" --name "real_${size}" --no-notify
    assert_equals "0" "${RUN_RC}"
    assert_equals "" "$(cat "${STDERR_FILE}")"
    output="${TEST_HOME}/tmp/screencasts/real_${size}.mp4"
    assert_equals "${expected}" "$("${REAL_FFPROBE}" -v error -select_streams v:0 \
      -show_entries stream=width,height -of csv=p=0 "${output}")"
  done
}

function test_ack_received_skips_osascript() {
  PGREP_RC="0"
  make_session s1
  touch "${TEST_HOME}/tmp/screencasts/.macrec/sessions/s1/ack.notified"
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget s1 '.status')"
  assert_not_contains "osascript|" "$(cat "${EVENT_LOG}")"
}

function test_fallback_creates_ack_and_logs_when_hammerspoon_absent() {
  PGREP_RC="1"
  make_session s1
  rm -f "${TEST_HOME}/tmp/screencasts/.macrec/sessions/s1/ack.notified"
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget s1 '.status')"
  assert_contains "osascript|" "$(cat "${EVENT_LOG}")"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/.macrec/sessions/s1/ack.notified"
  assert_contains "osascript fallback" "$(cat "${TEST_HOME}/tmp/screencasts/.macrec/macrec.log")"
}

function test_fallback_creates_ack_when_hammerspoon_undelivered() {
  PGREP_RC="0"
  make_session s1
  rm -f "${TEST_HOME}/tmp/screencasts/.macrec/sessions/s1/ack.notified"
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget s1 '.status')"
  assert_contains "osascript|" "$(cat "${EVENT_LOG}")"
  assert_file_exists "${TEST_HOME}/tmp/screencasts/.macrec/sessions/s1/ack.notified"
  assert_contains "osascript fallback" "$(cat "${TEST_HOME}/tmp/screencasts/.macrec/macrec.log")"
}

function test_preexisting_ack_suppresses_fallback_log() {
  PGREP_RC="0"
  make_session s1
  touch "${TEST_HOME}/tmp/screencasts/.macrec/sessions/s1/ack.notified"
  : >"${TEST_HOME}/tmp/screencasts/.macrec/macrec.log"
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_not_contains "osascript|" "$(cat "${EVENT_LOG}")"
  assert_not_contains "osascript fallback" "$(cat "${TEST_HOME}/tmp/screencasts/.macrec/macrec.log")"
}

function test_no_notify_skips_osascript() {
  make_session s1
  run_ship --session s1 --no-notify
  assert_equals "0" "${RUN_RC}"
  assert_equals "done" "$(sget s1 '.status')"
  assert_not_contains "osascript|" "$(cat "${EVENT_LOG}")"
}

function test_cap_stop_prefixes_notification_details() {
  make_session s1 cap
  run_ship --session s1
  assert_equals "0" "${RUN_RC}"
  assert_contains "Stopped at 0:42 cap" "$(cat "${TEST_TMP}/osascript.args")"
}

function test_usage_errors_exit_two() {
  run_ship
  assert_equals "2" "${RUN_RC}"
  run_ship --session nosuchid
  assert_equals "2" "${RUN_RC}"
  run_ship --session 'bad id!'
  assert_equals "2" "${RUN_RC}"
}
