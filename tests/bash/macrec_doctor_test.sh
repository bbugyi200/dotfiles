#!/bin/bash

#################################################################################
# Regression tests for macrec_doctor request/run/detach-stop and probe stubs.   #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_macrec_doctor"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  TEST_HOME="${TEST_TMP}/home"
  EVENT_LOG="${TEST_TMP}/events.log"
  STDOUT_FILE="${TEST_TMP}/stdout.log"
  STDERR_FILE="${TEST_TMP}/stderr.log"
  RUN_RC=0
  FAKE_CAPTURE_FAIL=0
  FAKE_CAPTURE_EMPTY=0
  FAKE_CAPTURE_HANG=0
  FAKE_CAPTURE_IGNORE_FIFO=0
  FAKE_FFMPEG_FAIL=0
  FAKE_FFPROBE_FAIL=0
  FAKE_FFPROBE_INVALID=0
  FAKE_CARD_RGB="227 65 59"
  FAKE_V_SLEEP=0.05
  FAKE_FFPROBE_WIDTH=480
  FAKE_FFPROBE_HEIGHT=300
  FAKE_FFPROBE_DURATION=1.0

  mkdir -p "${FAKE_BIN}" "${TEST_HOME}"
  : >"${EVENT_LOG}"

  export TEST_TMP EVENT_LOG
  export MACREC_DOCTOR_NO_REEXEC=1
  export MACREC_DOCTOR_POLL_INTERVAL=0.02
  export MACREC_DOCTOR_PICKUP_SECONDS=1
  export MACREC_DOCTOR_CAPTURE_SECONDS=0.05
  export MACREC_DOCTOR_CAP_SECONDS=1
  export MACREC_DOCTOR_ENCODE_SECONDS=1
  export MACREC_DOCTOR_STOP_CAPTURE_SECONDS=0.05
  export MACREC_DOCTOR_STOP_WAIT_SECONDS=2
  export MACREC_DOCTOR_READY_WAIT_SECONDS=2
  export MACREC_DOCTOR_DETACH_READY_SECONDS=0.05
  export MACREC_DOCTOR_ID=testid

  write_screencapture_stub
  write_ffmpeg_stub
  write_ffprobe_stub
  write_uuidgen_stub
  write_sw_vers_stub
  write_hostname_stub
}

function tear_down() {
  if [ -d "${TEST_HOME}/tmp/screencasts/.macrec/doctor" ]; then
    find "${TEST_HOME}/tmp/screencasts/.macrec/doctor" -name '*.pid' -print 2>/dev/null \
      | while IFS= read -r pidfile; do
        pid="$(tr -d ' \n' <"${pidfile}" 2>/dev/null || true)"
        if [ -n "${pid}" ]; then
          kill "${pid}" 2>/dev/null || true
        fi
      done
  fi
  rm -rf "${TEST_TMP}"
}

function write_screencapture_stub() {
  cat >"${FAKE_BIN}/screencapture" <<'EOF'
#!/bin/bash
# Model a C recorder: re-exec with default INT/QUIT dispositions. A backgrounded
# bash cannot trap signals ignored on entry, while the real screencapture
# installs its own SIGINT handler even when detached (device-spike finding).
if [[ -z "${FAKE_TRAPS_FIXED:-}" ]]; then
  export FAKE_TRAPS_FIXED=1
  exec "${PERL_BIN:-perl}" -e '$SIG{INT}="DEFAULT"; $SIG{QUIT}="DEFAULT"; exec @ARGV' -- "$0" "$@"
fi
out=""
cap=""
prev=""
for arg in "$@"; do
  if [[ "${prev}" == "-V" ]]; then
    cap="${arg}"
  fi
  prev="${arg}"
  out="${arg}"
done
printf 'screencapture|%s\n' "$*" >>"${EVENT_LOG}"

# Model progressive output: a real recorder's file exists while it runs.
if [[ -n "${out}" && "${FAKE_CAPTURE_FAIL:-0}" != "1" && "${FAKE_CAPTURE_EMPTY:-0}" != "1" && "${FAKE_CAPTURE_HANG:-0}" != "1" ]]; then
  printf 'fake-mov-bytes\n' >"${out}"
fi

write_out() {
  if [[ "${FAKE_CAPTURE_FAIL:-0}" == "1" ]]; then
    exit 1
  fi
  if [[ "${FAKE_CAPTURE_EMPTY:-0}" == "1" ]]; then
    : >"${out}"
    exit 0
  fi
  printf 'fake-mov-bytes\n' >"${out}"
  exit 0
}

trap 'printf "signal|INT\n" >>"${EVENT_LOG}"; write_out' INT
trap 'printf "signal|TERM\n" >>"${EVENT_LOG}"; write_out' TERM

if [[ -n "${cap}" ]]; then
  printf 'cap|%s\n' "${cap}" >>"${EVENT_LOG}"
  sleep "${FAKE_V_SLEEP:-0.05}"
  write_out
fi

if [[ "${FAKE_CAPTURE_HANG:-0}" == "1" ]]; then
  sleep 30
  write_out
fi

if [[ "${FAKE_CAPTURE_IGNORE_FIFO:-0}" == "1" ]]; then
  IFS= read -r -n 1 _ch || true
  printf 'stdin|ignored\n' >>"${EVENT_LOG}"
  sleep 5
  write_out
fi

if IFS= read -r -n 1 _ch; then
  printf 'stdin|byte\n' >>"${EVENT_LOG}"
  write_out
fi
printf 'stdin|eof\n' >>"${EVENT_LOG}"
write_out
EOF
  chmod +x "${FAKE_BIN}/screencapture"
}

function write_ffmpeg_stub() {
  cat >"${FAKE_BIN}/ffmpeg" <<'EOF'
#!/bin/bash
printf 'ffmpeg|%s\n' "$*" >>"${EVENT_LOG}"
for arg in "$@"; do
  if [[ "${arg}" == "-encoders" ]]; then
    printf ' V..... libx264             H.264 / AVC\n'
    printf ' V..... h264_videotoolbox   VideoToolbox H.264 Encoder\n'
    exit 0
  fi
done
if [[ "${FAKE_FFMPEG_FAIL:-0}" == "1" ]]; then
  exit 1
fi
if [[ " $* " == *" rawvideo "* || "${@: -1}" == "-" ]]; then
  perl -e 'print pack("C*", split(" ", $ARGV[0]))' "${FAKE_CARD_RGB:-227 65 59}"
  exit 0
fi
out=""
for arg in "$@"; do
  case "${arg}" in
  -* | rawvideo | lavfi | testsrc2*) ;;
  *) out="${arg}" ;;
  esac
done
if [[ -z "${out}" || "${out}" == "-" ]]; then
  perl -e 'print pack("C*", split(" ", $ARGV[0]))' "${FAKE_CARD_RGB:-227 65 59}"
  exit 0
fi
printf 'fake-ffmpeg-out\n' >"${out}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/ffmpeg"
}

function write_ffprobe_stub() {
  cat >"${FAKE_BIN}/ffprobe" <<'EOF'
#!/bin/bash
printf 'ffprobe|%s\n' "$*" >>"${EVENT_LOG}"
if [[ "${FAKE_FFPROBE_FAIL:-0}" == "1" ]]; then
  exit 1
fi
if [[ "${FAKE_FFPROBE_INVALID:-0}" == "1" ]]; then
  printf '%s\n' '{"streams":[],"format":{}}'
  exit 0
fi
cat <<JSON
{
  "streams": [
    {
      "codec_type": "video",
      "codec_name": "h264",
      "width": ${FAKE_FFPROBE_WIDTH:-480},
      "height": ${FAKE_FFPROBE_HEIGHT:-300},
      "r_frame_rate": "30/1",
      "bit_rate": "8000000",
      "duration": "${FAKE_FFPROBE_DURATION:-1.0}"
    }
  ],
  "format": {
    "duration": "${FAKE_FFPROBE_DURATION:-1.0}",
    "bit_rate": "8000000"
  }
}
JSON
exit 0
EOF
  chmod +x "${FAKE_BIN}/ffprobe"
}

function write_uuidgen_stub() {
  cat >"${FAKE_BIN}/uuidgen" <<'EOF'
#!/bin/bash
printf 'test-id-0001\n'
EOF
  chmod +x "${FAKE_BIN}/uuidgen"
}

function write_sw_vers_stub() {
  cat >"${FAKE_BIN}/sw_vers" <<'EOF'
#!/bin/bash
if [[ "$1" == "-productVersion" ]]; then
  printf '26.5\n'
fi
exit 0
EOF
  chmod +x "${FAKE_BIN}/sw_vers"
}

function write_hostname_stub() {
  cat >"${FAKE_BIN}/hostname" <<'EOF'
#!/bin/bash
printf 'macbook\n'
EOF
  chmod +x "${FAKE_BIN}/hostname"
}

function doctor_env() {
  PATH="${FAKE_BIN}:${PATH}" \
    HOME="${TEST_HOME}" \
    SCREENCAPTURE_BIN="${FAKE_BIN}/screencapture" \
    FFMPEG_BIN="${FAKE_BIN}/ffmpeg" \
    FFPROBE_BIN="${FAKE_BIN}/ffprobe" \
    JQ_BIN="$(command -v jq)" \
    PERL_BIN="$(command -v perl)" \
    UUIDGEN_BIN="${FAKE_BIN}/uuidgen" \
    SW_VERS_BIN="${FAKE_BIN}/sw_vers" \
    HOSTNAME_BIN="${FAKE_BIN}/hostname" \
    NOHUP_BIN="$(command -v nohup)" \
    TEST_TMP="${TEST_TMP}" \
    EVENT_LOG="${EVENT_LOG}" \
    FAKE_CAPTURE_FAIL="${FAKE_CAPTURE_FAIL}" \
    FAKE_CAPTURE_EMPTY="${FAKE_CAPTURE_EMPTY}" \
    FAKE_CAPTURE_HANG="${FAKE_CAPTURE_HANG}" \
    FAKE_CAPTURE_IGNORE_FIFO="${FAKE_CAPTURE_IGNORE_FIFO}" \
    FAKE_FFMPEG_FAIL="${FAKE_FFMPEG_FAIL}" \
    FAKE_FFPROBE_FAIL="${FAKE_FFPROBE_FAIL}" \
    FAKE_FFPROBE_INVALID="${FAKE_FFPROBE_INVALID}" \
    FAKE_CARD_RGB="${FAKE_CARD_RGB}" \
    FAKE_V_SLEEP="${FAKE_V_SLEEP}" \
    FAKE_FFPROBE_WIDTH="${FAKE_FFPROBE_WIDTH}" \
    FAKE_FFPROBE_HEIGHT="${FAKE_FFPROBE_HEIGHT}" \
    FAKE_FFPROBE_DURATION="${FAKE_FFPROBE_DURATION}" \
    MACREC_DOCTOR_NO_REEXEC=1 \
    MACREC_DOCTOR_POLL_INTERVAL="${MACREC_DOCTOR_POLL_INTERVAL}" \
    MACREC_DOCTOR_PICKUP_SECONDS="${MACREC_DOCTOR_PICKUP_SECONDS}" \
    MACREC_DOCTOR_CAPTURE_SECONDS="${MACREC_DOCTOR_CAPTURE_SECONDS}" \
    MACREC_DOCTOR_CAP_SECONDS="${MACREC_DOCTOR_CAP_SECONDS}" \
    MACREC_DOCTOR_ENCODE_SECONDS="${MACREC_DOCTOR_ENCODE_SECONDS}" \
    MACREC_DOCTOR_STOP_CAPTURE_SECONDS="${MACREC_DOCTOR_STOP_CAPTURE_SECONDS}" \
    MACREC_DOCTOR_STOP_WAIT_SECONDS="${MACREC_DOCTOR_STOP_WAIT_SECONDS}" \
    MACREC_DOCTOR_READY_WAIT_SECONDS="${MACREC_DOCTOR_READY_WAIT_SECONDS}" \
    MACREC_DOCTOR_DETACH_READY_SECONDS="${MACREC_DOCTOR_DETACH_READY_SECONDS}" \
    MACREC_DOCTOR_ID="${MACREC_DOCTOR_ID}" \
    bash "${SCRIPT}" "$@"
}

function run_doctor() {
  doctor_env "$@" >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
  RUN_RC=$?
}

function macrec_dir() {
  printf '%s\n' "${TEST_HOME}/tmp/screencasts/.macrec"
}

function assert_valid_json() {
  local text="$1"
  printf '%s' "${text}" | jq empty >/dev/null
  assert_equals "0" "$?"
}

function test_usage_unknown_command() {
  run_doctor nope
  assert_equals "2" "${RUN_RC}"
}

function test_env_probe_passes_with_tools_present() {
  run_doctor run --id envok --rect 0,0,240,150 --probes env
  assert_equals "0" "${RUN_RC}"
  assert_valid_json "$(cat "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  assert_equals "env" "$(jq -r '.probes[0].name' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].metrics.libx264' "${STDOUT_FILE}")"
  assert_equals "26.5" "$(jq -r '.macos' "${STDOUT_FILE}")"
}

function test_env_probe_fails_when_screencapture_missing() {
  PATH="${FAKE_BIN}:${PATH}" HOME="${TEST_HOME}" \
    SCREENCAPTURE_BIN="${FAKE_BIN}/nope" \
    FFMPEG_BIN="${FAKE_BIN}/ffmpeg" FFPROBE_BIN="${FAKE_BIN}/ffprobe" \
    JQ_BIN="$(command -v jq)" PERL_BIN="$(command -v perl)" \
    UUIDGEN_BIN="${FAKE_BIN}/uuidgen" SW_VERS_BIN="${FAKE_BIN}/sw_vers" \
    HOSTNAME_BIN="${FAKE_BIN}/hostname" \
    MACREC_DOCTOR_NO_REEXEC=1 MACREC_DOCTOR_ID=envfail \
    bash "${SCRIPT}" run --id envfail --rect 0,0,240,150 --probes env \
    >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
  RUN_RC=$?
  assert_equals "1" "${RUN_RC}"
  assert_equals "false" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  assert_contains "screencapture missing" "$(jq -r '.probes[0].detail' "${STDOUT_FILE}")"
}

function test_capture_probe_pass_and_card_visible() {
  run_doctor run --id capok --rect 100,200,240,150 --probes capture
  assert_equals "0" "${RUN_RC}"
  assert_equals "true" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].metrics.card_visible' "${STDOUT_FILE}")"
  assert_equals "480" "$(jq -r '.probes[0].metrics.width' "${STDOUT_FILE}")"
  assert_equals "2" "$(jq -r '.probes[0].metrics.retina_scale' "${STDOUT_FILE}")"
  assert_equals "number" "$(jq -r '.probes[0].metrics.start_latency_s | type' "${STDOUT_FILE}")"
  assert_contains "signal|INT" "$(cat "${EVENT_LOG}")"
}

function test_capture_probe_fails_when_card_not_visible() {
  FAKE_CARD_RGB="0 0 0"
  run_doctor run --id capdark --rect 0,0,240,150 --probes capture
  assert_equals "1" "${RUN_RC}"
  assert_equals "false" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  assert_equals "false" "$(jq -r '.probes[0].metrics.card_visible' "${STDOUT_FILE}")"
}

function test_capture_probe_fails_on_invalid_file() {
  FAKE_FFPROBE_INVALID=1
  run_doctor run --id capbad --rect 0,0,240,150 --probes capture
  assert_equals "1" "${RUN_RC}"
  assert_equals "false" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
}

function test_stop_probe_honours_fifo_signals_and_eof() {
  run_doctor run --id stopok --rect 0,0,240,150 --probes stop
  assert_equals "0" "${RUN_RC}"
  assert_equals "true" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].metrics.fifo_byte.valid' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].metrics.sigint.valid' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].metrics.sigterm.valid' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].metrics.fifo_eof.valid' "${STDOUT_FILE}")"
  assert_contains "stdin|byte" "$(cat "${EVENT_LOG}")"
  assert_contains "signal|INT" "$(cat "${EVENT_LOG}")"
  assert_contains "signal|TERM" "$(cat "${EVENT_LOG}")"
  assert_contains "stdin|eof" "$(cat "${EVENT_LOG}")"
}

function test_stop_probe_passes_when_only_fifo_methods_fail() {
  FAKE_CAPTURE_IGNORE_FIFO=1
  run_doctor run --id stopsigint --rect 0,0,240,150 --probes stop
  assert_equals "0" "${RUN_RC}"
  assert_equals "true" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].metrics.sigint.valid' "${STDOUT_FILE}")"
  assert_equals "number" "$(jq -r '.probes[0].metrics.sigint.start_latency_s | type' "${STDOUT_FILE}")"
  assert_equals "124" "$(jq -r '.probes[0].metrics.fifo_byte.exit_status' "${STDOUT_FILE}")"
  assert_contains "auxiliary methods" "$(jq -r '.probes[0].detail' "${STDOUT_FILE}")"
}

function test_stop_probe_fails_when_sigint_leaves_invalid_file() {
  FAKE_FFPROBE_INVALID=1
  run_doctor run --id stopbad --rect 0,0,240,150 --probes stop
  assert_equals "1" "${RUN_RC}"
  assert_equals "false" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  assert_contains "SIGINT" "$(jq -r '.probes[0].detail' "${STDOUT_FILE}")"
}

function test_cap_probe_stops_with_dash_v() {
  run_doctor run --id capv --rect 0,0,240,150 --probes cap
  assert_equals "0" "${RUN_RC}"
  assert_equals "true" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  assert_contains "cap|1" "$(cat "${EVENT_LOG}")"
}

function test_encode_probe_times_both_encoders() {
  run_doctor run --id encok --rect 0,0,240,150 --probes encode
  assert_equals "0" "${RUN_RC}"
  assert_equals "true" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].metrics.libx264_synthetic.ok' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].metrics.h264_videotoolbox_synthetic.ok' "${STDOUT_FILE}")"
  assert_contains "libx264" "$(cat "${EVENT_LOG}")"
  assert_contains "h264_videotoolbox" "$(cat "${EVENT_LOG}")"
}

function test_encode_probe_fails_when_ffmpeg_fails() {
  FAKE_FFMPEG_FAIL=1
  run_doctor run --id encfail --rect 0,0,240,150 --probes encode
  assert_equals "1" "${RUN_RC}"
  assert_equals "false" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
}

function test_probe_clips_are_deleted_without_keep() {
  run_doctor run --id cleanup --rect 0,0,240,150 --probes capture
  assert_equals "0" "${RUN_RC}"
  local leftover
  leftover="$(find "$(macrec_dir)/doctor/cleanup" -name '*.mov' 2>/dev/null | wc -l | tr -d ' ')"
  assert_equals "0" "${leftover}"
}

function test_keep_leaves_probe_clips() {
  run_doctor run --id keepme --rect 0,0,240,150 --probes capture --keep
  assert_equals "0" "${RUN_RC}"
  assert_file_exists "$(macrec_dir)/doctor/keepme/capture.mov"
}

function test_run_result_is_schema_1_json() {
  run_doctor run --id schema1 --rect 10,20,240,150 --probes env
  assert_equals "0" "${RUN_RC}"
  assert_equals "1" "$(jq -r '.schema' "${STDOUT_FILE}")"
  assert_equals "schema1" "$(jq -r '.id' "${STDOUT_FILE}")"
  assert_equals "macbook" "$(jq -r '.host' "${STDOUT_FILE}")"
}

function test_request_handshake_pass() {
  mkdir -p "$(macrec_dir)/requests" "$(macrec_dir)/doctor"
  doctor_env request --probes env --timeout 2 >"${STDOUT_FILE}" 2>"${STDERR_FILE}" &
  local pid=$!
  local req=""
  local waited=0
  while [[ -z "${req}" && "${waited}" -lt 50 ]]; do
    req="$(find "$(macrec_dir)/requests" -name 'doctor-*.json' 2>/dev/null | head -n 1)"
    sleep 0.02
    waited=$((waited + 1))
  done
  assert_file_exists "${req}"
  local id
  id="$(jq -r '.id' "${req}")"
  assert_equals "doctor" "$(jq -r '.action' "${req}")"
  jq -n --arg id "${id}" '{schema:1,id:$id,probes:[{name:"env",ok:true,metrics:{},detail:""}]}' \
    >"$(macrec_dir)/doctor/${id}.json"
  wait "${pid}"
  RUN_RC=$?
  assert_equals "0" "${RUN_RC}"
  assert_equals "true" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
}

function test_request_handshake_some_probes_fail() {
  mkdir -p "$(macrec_dir)/requests" "$(macrec_dir)/doctor"
  doctor_env request --probes env --timeout 2 >"${STDOUT_FILE}" 2>"${STDERR_FILE}" &
  local pid=$!
  local req=""
  local waited=0
  while [[ -z "${req}" && "${waited}" -lt 50 ]]; do
    req="$(find "$(macrec_dir)/requests" -name 'doctor-*.json' 2>/dev/null | head -n 1)"
    sleep 0.02
    waited=$((waited + 1))
  done
  local id
  id="$(jq -r '.id' "${req}")"
  jq -n --arg id "${id}" '{schema:1,id:$id,probes:[{name:"env",ok:false,metrics:{},detail:"missing"}]}' \
    >"$(macrec_dir)/doctor/${id}.json"
  wait "${pid}"
  RUN_RC=$?
  assert_equals "1" "${RUN_RC}"
}

function test_request_refused_locked() {
  mkdir -p "$(macrec_dir)/requests" "$(macrec_dir)/doctor"
  doctor_env request --probes env --timeout 2 >"${STDOUT_FILE}" 2>"${STDERR_FILE}" &
  local pid=$!
  local req=""
  local waited=0
  while [[ -z "${req}" && "${waited}" -lt 50 ]]; do
    req="$(find "$(macrec_dir)/requests" -name 'doctor-*.json' 2>/dev/null | head -n 1)"
    sleep 0.02
    waited=$((waited + 1))
  done
  local id
  id="$(jq -r '.id' "${req}")"
  jq -n --arg id "${id}" '{schema:1,id:$id,refused:"locked"}' >"$(macrec_dir)/doctor/${id}.json"
  wait "${pid}"
  RUN_RC=$?
  assert_equals "3" "${RUN_RC}"
  assert_equals "locked" "$(jq -r '.refused' "${STDOUT_FILE}")"
}

function test_request_not_picked_up() {
  run_doctor request --probes env --timeout 2
  assert_equals "3" "${RUN_RC}"
  assert_contains "not picked up" "$(cat "${STDERR_FILE}")"
}

function test_request_timeout_after_pickup() {
  mkdir -p "$(macrec_dir)/requests" "$(macrec_dir)/doctor"
  doctor_env request --probes env --timeout 1 >"${STDOUT_FILE}" 2>"${STDERR_FILE}" &
  local pid=$!
  local req=""
  local waited=0
  while [[ -z "${req}" && "${waited}" -lt 50 ]]; do
    req="$(find "$(macrec_dir)/requests" -name 'doctor-*.json' 2>/dev/null | head -n 1)"
    sleep 0.02
    waited=$((waited + 1))
  done
  rm -f "${req}"
  wait "${pid}"
  RUN_RC=$?
  assert_equals "4" "${RUN_RC}"
  assert_contains "timeout" "$(cat "${STDERR_FILE}")"
}

function test_request_invalid_probes() {
  run_doctor request --probes nope
  assert_equals "2" "${RUN_RC}"
}

function test_detach_and_detach_stop() {
  run_doctor run --id det1 --rect 0,0,240,150 --probes detach
  assert_equals "0" "${RUN_RC}"
  assert_equals "true" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  local rec_pid
  rec_pid="$(jq -r '.probes[0].metrics.recorder_pid' "${STDOUT_FILE}")"
  assert_equals "0" "$(kill -0 "${rec_pid}" 2>/dev/null && echo 0 || echo 1)"
  run_doctor detach-stop --id det1
  assert_equals "0" "${RUN_RC}"
  assert_equals "true" "$(jq -r '.valid' "${STDOUT_FILE}")"
  assert_contains "signal|INT" "$(cat "${EVENT_LOG}")"
  if [ -d "$(macrec_dir)/doctor/det1" ]; then
    assert_equals "gone" "present"
  fi
  assert_equals "1" "$(kill -0 "${rec_pid}" 2>/dev/null && echo 0 || echo 1)"
}
