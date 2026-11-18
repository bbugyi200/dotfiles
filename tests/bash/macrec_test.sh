#!/bin/bash

#################################################################################
# Regression tests for the detached macrec recording engine.                    #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_macrec"
DOCTOR="${PWD}/home/bin/executable_macrec_doctor"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  TEST_HOME="${TEST_TMP}/home"
  EVENT_LOG="${TEST_TMP}/events.log"
  STDOUT_FILE="${TEST_TMP}/stdout.log"
  STDERR_FILE="${TEST_TMP}/stderr.log"
  RUN_RC=0
  FAKE_CAPTURE_FAIL=0
  FAKE_CAPTURE_CRASH=0
  FAKE_CAPTURE_SYSTEM=0
  FAKE_CAPTURE_IGNORE_INT=0
  FAKE_CAPTURE_INVALID=0
  FAKE_V_SLEEP=2
  FAKE_DF_AVAIL=99999999
  FAKE_SHIP_FAIL=0
  LAST_ID=""

  mkdir -p "${FAKE_BIN}" "${TEST_HOME}"
  : >"${EVENT_LOG}"
  printf '0\n' >"${TEST_TMP}/uuid.n"

  export TEST_TMP EVENT_LOG
  export MACREC_NO_REEXEC=1
  export MACREC_POLL_INTERVAL=0.02
  export MACREC_READY_WAIT=2
  export MACREC_READY_GRACE=0.05
  export MACREC_STOP_INT_WAIT=0.4
  export MACREC_STOP_TERM_WAIT=0.3
  export MACREC_MIN_FREE_KB=2097152

  write_screencapture_stub
  write_ffprobe_stub
  write_uuidgen_stub
  write_df_stub
  write_ship_stub
}

function tear_down() {
  if [ -n "${FAKE_BIN:-}" ]; then
    pkill -9 -f "${FAKE_BIN}/" 2>/dev/null || true
  fi
  if [ -n "${TEST_HOME:-}" ]; then
    pkill -9 -f "${TEST_HOME}/" 2>/dev/null || true
  fi
  pkill -9 -f "${SCRIPT} _wrapper" 2>/dev/null || true
  if [ -d "${TEST_HOME}/tmp/screencasts/.macrec/sessions" ]; then
    find "${TEST_HOME}/tmp/screencasts/.macrec/sessions" \( -name 'recorder.pid' -o -name 'pid' \) -print 2>/dev/null \
      | while IFS= read -r pidfile; do
        pid="$(tr -d ' \n' <"${pidfile}" 2>/dev/null || true)"
        if [ -n "${pid}" ]; then
          kill -9 "${pid}" 2>/dev/null || true
        fi
      done
  fi
  sleep 0.05
  rm -rf "${TEST_TMP}" 2>/dev/null || true
  if [ -n "${TEST_TMP:-}" ] && [ -d "${TEST_TMP}" ]; then
    sleep 0.2
    rm -rf "${TEST_TMP}" 2>/dev/null || true
  fi
}

function write_screencapture_stub() {
  cat >"${FAKE_BIN}/screencapture" <<'EOF'
#!/bin/bash
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

if [[ "${FAKE_CAPTURE_FAIL:-0}" == "1" ]]; then
  printf 'screencapture: could not create image file because you do not have permission to capture this display.\n' >&2
  printf 'not authorized to capture the screen (TCC)\n' >&2
  exit 1
fi

write_out() {
  printf 'fake-mov-bytes\n' >"${out}"
}

if [[ "${FAKE_CAPTURE_IGNORE_INT:-0}" == "1" ]]; then
  trap 'printf "signal|INT\n" >>"${EVENT_LOG}"' INT
else
  # Real macOS timed (-V) captures cannot be finalized early with SIGINT.
  trap 'printf "signal|INT\n" >>"${EVENT_LOG}"; [[ "${FAKE_CAPTURE_INVALID:-0}" == "1" || -n "${cap}" ]] || write_out; exit 0' INT
fi
trap 'printf "signal|TERM\n" >>"${EVENT_LOG}"; [[ "${FAKE_CAPTURE_INVALID:-0}" == "1" ]] || write_out; exit 143' TERM

if [[ "${FAKE_CAPTURE_CRASH:-0}" == "1" ]]; then
  write_out
  sleep 0.6
  exit 1
fi

if [[ "${FAKE_CAPTURE_SYSTEM:-0}" == "1" ]]; then
  write_out
  sleep 0.6
  exit 0
fi

hold="${FAKE_V_SLEEP:-2}"
slept=0
while true; do
  if perl -e 'exit($ARGV[0] + 0 >= $ARGV[1] + 0 ? 0 : 1)' "${slept}" "${hold}"; then
    break
  fi
  sleep 0.05
  slept="$(perl -e 'printf "%.2f\n", $ARGV[0] + 0.05' "${slept}")"
done
write_out
exit 0
EOF
  chmod +x "${FAKE_BIN}/screencapture"
}

function write_ffprobe_stub() {
  cat >"${FAKE_BIN}/ffprobe" <<'EOF'
#!/bin/bash
printf 'ffprobe|%s\n' "$*" >>"${EVENT_LOG}"
file=""
for arg in "$@"; do
  file="${arg}"
done
if [[ ! -s "${file}" ]]; then
  exit 1
fi
cat <<'JSON'
{
  "streams": [
    {
      "codec_type": "video",
      "codec_name": "h264",
      "width": 480,
      "height": 300,
      "r_frame_rate": "30/1",
      "bit_rate": "8000000",
      "duration": "1.0"
    }
  ],
  "format": { "duration": "1.0", "bit_rate": "8000000" }
}
JSON
exit 0
EOF
  chmod +x "${FAKE_BIN}/ffprobe"
}

function write_uuidgen_stub() {
  cat >"${FAKE_BIN}/uuidgen" <<'EOF'
#!/bin/bash
n=0
if [[ -f "${TEST_TMP}/uuid.n" ]]; then
  n="$(cat "${TEST_TMP}/uuid.n")"
fi
n=$((n + 1))
printf '%s\n' "${n}" >"${TEST_TMP}/uuid.n"
printf 'sess-%04d\n' "${n}"
EOF
  chmod +x "${FAKE_BIN}/uuidgen"
}

function write_df_stub() {
  cat >"${FAKE_BIN}/df" <<'EOF'
#!/bin/bash
avail="${FAKE_DF_AVAIL:-99999999}"
printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n'
printf '/dev/disk 100000000 1 %s 1%% /\n' "${avail}"
EOF
  chmod +x "${FAKE_BIN}/df"
}

function write_ship_stub() {
  cat >"${FAKE_BIN}/macrec_ship" <<'EOF'
#!/bin/bash
printf 'ship|%s\n' "$*" >>"${EVENT_LOG}"
id=""
prev=""
for arg in "$@"; do
  if [[ "${prev}" == "--session" ]]; then
    id="${arg}"
  fi
  prev="${arg}"
done
sj="${HOME}/tmp/screencasts/.macrec/sessions/${id}/session.json"
if [[ -f "${sj}" ]]; then
  if [[ "${FAKE_SHIP_FAIL:-0}" == "1" ]]; then
    jq '.status="failed" | .error="stub ship failed"' "${sj}" >"${sj}.tmp" && mv "${sj}.tmp" "${sj}"
    exit 1
  fi
  jq '.status="done"' "${sj}" >"${sj}.tmp" && mv "${sj}.tmp" "${sj}"
fi
exit 0
EOF
  chmod +x "${FAKE_BIN}/macrec_ship"
}

function macrec_env() {
  PATH="${FAKE_BIN}:${PATH}" \
    HOME="${TEST_HOME}" \
    SCREENCAPTURE_BIN="${FAKE_BIN}/screencapture" \
    FFPROBE_BIN="${FAKE_BIN}/ffprobe" \
    JQ_BIN="$(command -v jq)" \
    PERL_BIN="$(command -v perl)" \
    UUIDGEN_BIN="${FAKE_BIN}/uuidgen" \
    NOHUP_BIN="$(command -v nohup)" \
    DF_BIN="${FAKE_BIN}/df" \
    PS_BIN="$(command -v ps)" \
    MKFIFO_BIN="$(command -v mkfifo)" \
    MACREC_SHIP_BIN="${FAKE_BIN}/macrec_ship" \
    MACREC_DOCTOR_BIN="${DOCTOR}" \
    TEST_TMP="${TEST_TMP}" \
    EVENT_LOG="${EVENT_LOG}" \
    FAKE_CAPTURE_FAIL="${FAKE_CAPTURE_FAIL}" \
    FAKE_CAPTURE_CRASH="${FAKE_CAPTURE_CRASH}" \
    FAKE_CAPTURE_SYSTEM="${FAKE_CAPTURE_SYSTEM}" \
    FAKE_CAPTURE_IGNORE_INT="${FAKE_CAPTURE_IGNORE_INT}" \
    FAKE_V_SLEEP="${FAKE_V_SLEEP}" \
    FAKE_DF_AVAIL="${FAKE_DF_AVAIL}" \
    FAKE_SHIP_FAIL="${FAKE_SHIP_FAIL}" \
    MACREC_NO_REEXEC=1 \
    MACREC_POLL_INTERVAL="${MACREC_POLL_INTERVAL}" \
    MACREC_READY_WAIT="${MACREC_READY_WAIT}" \
    MACREC_READY_GRACE="${MACREC_READY_GRACE}" \
    MACREC_STOP_INT_WAIT="${MACREC_STOP_INT_WAIT}" \
    MACREC_STOP_TERM_WAIT="${MACREC_STOP_TERM_WAIT}" \
    MACREC_MIN_FREE_KB="${MACREC_MIN_FREE_KB}" \
    bash "${SCRIPT}" "$@"
}

function run_macrec() {
  macrec_env "$@" >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
  RUN_RC=$?
}

function macrec_dir() {
  printf '%s\n' "${TEST_HOME}/tmp/screencasts/.macrec"
}

function session_path() {
  printf '%s\n' "$(macrec_dir)/sessions/$1"
}

function wait_for() {
  local n=0
  while [ "${n}" -lt 80 ]; do
    if eval "$1"; then
      return 0
    fi
    sleep 0.05
    n=$((n + 1))
  done
  return 1
}

function wait_session_field() {
  local id="$1"
  local key="$2"
  local want="$3"
  local sj
  sj="$(session_path "${id}")/session.json"
  wait_for "[ -f '${sj}' ] && [ \"\$(jq -r --arg k '${key}' '.[\$k] // empty' '${sj}')\" = '${want}' ]"
}

function assert_valid_json() {
  printf '%s' "$1" | jq empty >/dev/null
  assert_equals "0" "$?"
}

function test_reexec_guard_present() {
  local head
  head="$(head -n 20 "${SCRIPT}")"
  assert_contains 'BASH_VERSINFO[0]' "${head}"
  assert_contains '/opt/homebrew/bin/bash' "${head}"
  assert_contains 'MACREC_NO_REEXEC' "${head}"
}

function test_usage_unknown_command() {
  run_macrec nope
  assert_equals "2" "${RUN_RC}"
}

function test_start_stop_ships() {
  run_macrec start 10,20,240,150
  assert_equals "0" "${RUN_RC}"
  assert_valid_json "$(cat "${STDOUT_FILE}")"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  assert_equals "sess-0001" "${LAST_ID}"
  run_macrec status --json
  assert_equals "0" "${RUN_RC}"
  assert_equals "1" "$(jq -r '.schema' "${STDOUT_FILE}")"
  assert_equals "recording" "$(jq -r '.active.state' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.active.recorder_alive' "${STDOUT_FILE}")"
  run_macrec stop --reason chord
  assert_equals "0" "${RUN_RC}"
  assert_equals "${LAST_ID}" "$(jq -r '.id' "${STDOUT_FILE}")"
  assert_equals "chord" "$(jq -r '.stopped_by' "${STDOUT_FILE}")"
  wait_for "grep -q '^ship|' '${EVENT_LOG}'"
  assert_equals "0" "$?"
  wait_session_field "${LAST_ID}" status done
  assert_equals "0" "$?"
  assert_contains "screencapture|" "$(cat "${EVENT_LOG}")"
  assert_equals "1" "$(grep -c '^signal|INT' "${EVENT_LOG}")"
  assert_contains "--session ${LAST_ID}" "$(cat "${EVENT_LOG}")"
}

function test_stop_escalates_sigint_then_sigterm() {
  FAKE_CAPTURE_IGNORE_INT=1
  FAKE_V_SLEEP=8
  run_macrec start 0,0,100,100
  assert_equals "0" "${RUN_RC}"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  run_macrec stop --reason chord
  assert_equals "0" "${RUN_RC}"
  wait_for "grep -q 'signal|TERM' '${EVENT_LOG}'"
  local events
  events="$(cat "${EVENT_LOG}")"
  assert_contains "signal|INT" "${events}"
  assert_contains "signal|TERM" "${events}"
  local int_line term_line
  int_line="$(grep -n 'signal|INT' "${EVENT_LOG}" | head -n 1 | cut -d: -f1)"
  term_line="$(grep -n 'signal|TERM' "${EVENT_LOG}" | head -n 1 | cut -d: -f1)"
  assert_equals "1" "$(awk -v i="${int_line}" -v t="${term_line}" 'BEGIN { print (i + 0 < t + 0) ? 1 : 0 }')"
}

function test_stop_is_idempotent() {
  run_macrec stop
  assert_equals "0" "${RUN_RC}"
  assert_equals "idle" "$(jq -r '.state' "${STDOUT_FILE}")"
  run_macrec start 0,0,80,80
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  run_macrec stop --reason chord
  assert_equals "0" "${RUN_RC}"
  run_macrec stop --reason chord
  assert_equals "0" "${RUN_RC}"
  assert_equals "idle" "$(jq -r '.state' "${STDOUT_FILE}")"
}

function test_discard_does_not_ship() {
  run_macrec start 0,0,80,80
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  run_macrec discard
  assert_equals "0" "${RUN_RC}"
  wait_session_field "${LAST_ID}" status discarded
  assert_equals "0" "$?"
  if grep -q '^ship|' "${EVENT_LOG}"; then
    assert_equals "no-ship" "ship"
  fi
  if [ -f "$(session_path "${LAST_ID}")/raw.mov" ]; then
    assert_equals "raw-gone" "raw-present"
  fi
}

function test_busy_refusal() {
  run_macrec start 0,0,80,80
  assert_equals "0" "${RUN_RC}"
  run_macrec start 0,0,90,90
  assert_equals "3" "${RUN_RC}"
  assert_contains "already recording" "$(cat "${STDERR_FILE}")"
  run_macrec stop --reason chord
}

function test_low_disk_refusal() {
  FAKE_DF_AVAIL=100
  run_macrec start 0,0,80,80
  assert_equals "5" "${RUN_RC}"
  assert_contains "low disk" "$(cat "${STDERR_FILE}")"
}

function test_early_exit_permission_message() {
  FAKE_CAPTURE_FAIL=1
  run_macrec start 0,0,80,80 --probe
  assert_equals "4" "${RUN_RC}"
  assert_contains "Screen Recording is off for Hammerspoon" "$(cat "${STDERR_FILE}")"
}

function test_cap_system_and_crash_classification() {
  FAKE_V_SLEEP=1.2
  run_macrec start 0,0,80,80 --probe --max-seconds 1
  assert_equals "0" "${RUN_RC}"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  wait_session_field "${LAST_ID}" stop_reason cap
  assert_equals "0" "$?"

  FAKE_CAPTURE_SYSTEM=1
  run_macrec start 0,0,80,80 --probe --max-seconds 600
  assert_equals "0" "${RUN_RC}"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  wait_session_field "${LAST_ID}" stop_reason system
  assert_equals "0" "$?"

  FAKE_CAPTURE_SYSTEM=0
  FAKE_CAPTURE_CRASH=1
  run_macrec start 0,0,80,80 --probe --max-seconds 600
  assert_equals "0" "${RUN_RC}"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  wait_session_field "${LAST_ID}" stop_reason crash
  assert_equals "0" "$?"
}

function test_watchdog_cap_finalizes_without_native_timed_capture() {
  FAKE_V_SLEEP=30
  run_macrec start 0,0,80,80 --probe --max-seconds 1
  assert_equals "0" "${RUN_RC}"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  wait_session_field "${LAST_ID}" status done
  assert_equals "0" "$?"
  local session
  session="$(session_path "${LAST_ID}")/session.json"
  assert_equals "cap" "$(jq -r '.stop_reason' "${session}")"
  assert_equals "true" "$(jq '.ended_at - .started_at < 3' "${session}")"
  assert_contains "signal|INT" "$(cat "${EVENT_LOG}")"
  assert_file_not_exists "$(session_path "${LAST_ID}")/raw.mov"
}

function test_orphan_detection_and_recover() {
  local sdir
  sdir="$(session_path orphan1)"
  mkdir -p "${sdir}/owner.lock"
  printf '999999\n' >"${sdir}/owner.lock/pid"
  jq -n -c '{
    schema:1,id:"orphan1",name:"clip",status:"recording",
    region:{x:0,y:0,w:80,h:80},mic:false,probe:false,
    started_at:100,cap_seconds:600,hosts:{},host_detail:{},recovered:false
  }' >"${sdir}/session.json"
  : >"${sdir}/log"
  run_macrec status --json
  assert_equals "0" "${RUN_RC}"
  assert_equals "true" "$(jq -r '.sessions[] | select(.id=="orphan1") | .orphaned' "${STDOUT_FILE}")"
  run_macrec recover orphan1
  assert_equals "0" "${RUN_RC}"
  assert_contains "ship|--session orphan1" "$(cat "${EVENT_LOG}")"
  assert_equals "true" "$(jq -r '.recovered' "${sdir}/session.json")"
  assert_equals "recovered" "$(jq -r '.stop_reason' "${sdir}/session.json")"
}

function test_pid_reuse_safety() {
  run_macrec start 0,0,80,80 --probe
  assert_equals "0" "${RUN_RC}"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  sleep 30 &
  local sleep_pid=$!
  printf '%s\n' "${sleep_pid}" >"$(session_path "${LAST_ID}")/recorder.pid"
  run_macrec stop --reason chord
  assert_equals "0" "${RUN_RC}"
  if ! kill -0 "${sleep_pid}" 2>/dev/null; then
    assert_equals "sleep-alive" "sleep-dead"
  fi
  kill "${sleep_pid}" 2>/dev/null || true
  wait "${sleep_pid}" 2>/dev/null || true
  wait_session_field "${LAST_ID}" status done
  assert_equals "0" "$?"
}

function test_atomic_writes_and_status_schema() {
  run_macrec start 1,2,80,80 --mic --probe
  assert_equals "0" "${RUN_RC}"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  local sj
  sj="$(session_path "${LAST_ID}")/session.json"
  jq empty "${sj}"
  assert_equals "0" "$?"
  local leftovers
  leftovers="$(find "$(macrec_dir)" -name '*.tmp.*' 2>/dev/null | wc -l | tr -d ' ')"
  assert_equals "0" "${leftovers}"
  run_macrec status --json
  assert_equals "1" "$(jq -r '.schema' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.active.mic' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.sessions[0].acked.notified == false and .sessions[0].acked.adopted == false' "${STDOUT_FILE}")"
  assert_equals "string" "$(jq -r '.sessions[0].log | type' "${STDOUT_FILE}")"
  run_macrec stop --reason menu
  wait_session_field "${LAST_ID}" stop_reason menu
  leftovers="$(find "$(macrec_dir)" -name '*.tmp.*' 2>/dev/null | wc -l | tr -d ' ')"
  assert_equals "0" "${leftovers}"
  jq empty "${sj}"
  assert_equals "0" "$?"
  assert_contains " -g " "$(grep '^screencapture|' "${EVENT_LOG}")"
}

function test_ack_retry_and_aliases() {
  local sdir
  sdir="$(session_path fail1)"
  mkdir -p "${sdir}"
  jq -n -c '{
    schema:1,id:"fail1",name:"clip",status:"failed",
    region:{x:0,y:0,w:80,h:80},mic:false,probe:false,
    started_at:50,cap_seconds:600,hosts:{apollo:"failed"},host_detail:{}
  }' >"${sdir}/session.json"
  run_macrec ack fail1 notified
  assert_equals "0" "${RUN_RC}"
  assert_file_exists "${sdir}/ack.notified"
  assert_contains "ack fail1 notified" "$(cat "$(macrec_dir)/macrec.log")"
  run_macrec ack fail1 adopted
  assert_file_exists "${sdir}/ack.adopted"
  run_macrec ack fail1 dismissed
  assert_equals "0" "${RUN_RC}"
  assert_file_exists "${sdir}/ack.dismissed"
  run_macrec ack fail1 bogus
  assert_equals "2" "${RUN_RC}"
  : >"${sdir}/log"
  run_macrec status --json
  assert_equals "true" "$(jq -r '.sessions[] | select(.id=="fail1") | .acked.dismissed' "${STDOUT_FILE}")"
  # A newer failed doctor probe must never become the default retry target.
  local probe_dir
  probe_dir="$(session_path probefail)"
  mkdir -p "${probe_dir}"
  jq -n -c '{
    schema:1,id:"probefail",name:"probe",status:"failed",
    region:{x:0,y:0,w:80,h:80},mic:false,probe:true,
    started_at:90,cap_seconds:8,hosts:{},host_detail:{}
  }' >"${probe_dir}/session.json"
  run_macrec retry
  assert_equals "0" "${RUN_RC}"
  assert_contains "ship|--session fail1 --retry" "$(cat "${EVENT_LOG}")"
  assert_not_contains "probefail" "$(cat "${EVENT_LOG}")"
  run_macrec ship --session fail1 --retry
  assert_equals "0" "${RUN_RC}"
  run_macrec doctor -h
  assert_equals "0" "${RUN_RC}"
  assert_contains "macrec_doctor" "$(cat "${STDOUT_FILE}")"
}

function test_keys_modes_recorded_in_both_files() {
  for mode in all chords off; do
    run_macrec start 0,0,80,80 --keys "${mode}"
    assert_equals "0" "${RUN_RC}"
    LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
    assert_equals "${mode}" "$(jq -r '.keys' "$(session_path "${LAST_ID}")/session.json")"
    assert_equals "${mode}" "$(jq -r '.keys' "$(macrec_dir)/active.json")"
    run_macrec status --json
    assert_equals "0" "${RUN_RC}"
    assert_equals "${mode}" "$(jq -r '.active.keys' "${STDOUT_FILE}")"
    assert_equals "${mode}" "$(jq -r --arg id "${LAST_ID}" '.sessions[] | select(.id==$id) | .keys' "${STDOUT_FILE}")"
    run_macrec stop --reason chord
    assert_equals "0" "${RUN_RC}"
    wait_session_field "${LAST_ID}" status done
    assert_equals "0" "$?"
  done
}

function test_keys_default_is_off() {
  run_macrec start 0,0,80,80
  assert_equals "0" "${RUN_RC}"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  assert_equals "off" "$(jq -r '.keys' "$(session_path "${LAST_ID}")/session.json")"
  assert_equals "off" "$(jq -r '.keys' "$(macrec_dir)/active.json")"
  run_macrec status --json
  assert_equals "off" "$(jq -r '.active.keys' "${STDOUT_FILE}")"
  run_macrec stop --reason chord
  wait_session_field "${LAST_ID}" status done
  assert_equals "0" "$?"
}

function test_keys_bogus_exits_2() {
  run_macrec start 0,0,80,80 --keys bogus
  assert_equals "2" "${RUN_RC}"
  run_macrec start 0,0,80,80 --keys
  assert_equals "2" "${RUN_RC}"
}

function test_keys_probe_forces_off() {
  run_macrec start 0,0,80,80 --probe --keys all
  assert_equals "0" "${RUN_RC}"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  assert_equals "off" "$(jq -r '.keys' "$(session_path "${LAST_ID}")/session.json")"
  assert_equals "off" "$(jq -r '.keys' "$(macrec_dir)/active.json")"
  run_macrec status --json
  assert_equals "off" "$(jq -r '.active.keys' "${STDOUT_FILE}")"
  wait_session_field "${LAST_ID}" status done
  assert_equals "0" "$?"
}

function test_keys_legacy_active_without_keys_reports_off() {
  run_macrec start 0,0,80,80 --keys all
  assert_equals "0" "${RUN_RC}"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  jq 'del(.keys)' "$(macrec_dir)/active.json" >"${TEST_TMP}/legacy-active.json"
  mv "${TEST_TMP}/legacy-active.json" "$(macrec_dir)/active.json"
  run_macrec status --json
  assert_equals "0" "${RUN_RC}"
  assert_equals "off" "$(jq -r '.active.keys' "${STDOUT_FILE}")"
  run_macrec stop --reason chord
  wait_session_field "${LAST_ID}" status done
  assert_equals "0" "$?"
}

function test_keys_subcommand_patches_matching_active() {
  run_macrec start 0,0,80,80
  assert_equals "0" "${RUN_RC}"
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  run_macrec keys "${LAST_ID}" chords
  assert_equals "0" "${RUN_RC}"
  assert_equals "${LAST_ID}" "$(jq -r '.id' "${STDOUT_FILE}")"
  assert_equals "chords" "$(jq -r '.keys' "${STDOUT_FILE}")"
  assert_equals "chords" "$(jq -r '.keys' "$(session_path "${LAST_ID}")/session.json")"
  assert_equals "chords" "$(jq -r '.keys' "$(macrec_dir)/active.json")"
  run_macrec status --json
  assert_equals "chords" "$(jq -r '.active.keys' "${STDOUT_FILE}")"
  run_macrec stop --reason chord
  wait_session_field "${LAST_ID}" status done
  assert_equals "0" "$?"
}

function test_keys_subcommand_leaves_non_matching_active_untouched() {
  run_macrec start 0,0,80,80
  assert_equals "0" "${RUN_RC}"
  local live_id
  live_id="$(jq -r '.id' "${STDOUT_FILE}")"
  local other_dir
  other_dir="$(session_path other1)"
  mkdir -p "${other_dir}"
  jq -n -c '{
    schema:1,id:"other1",name:"clip",status:"recording",
    region:{x:0,y:0,w:80,h:80},mic:false,probe:false,keys:"off",
    started_at:50,cap_seconds:600,hosts:{},host_detail:{},recovered:false
  }' >"${other_dir}/session.json"
  run_macrec keys other1 all
  assert_equals "0" "${RUN_RC}"
  assert_equals "all" "$(jq -r '.keys' "${other_dir}/session.json")"
  assert_equals "off" "$(jq -r '.keys' "$(macrec_dir)/active.json")"
  assert_equals "${live_id}" "$(jq -r '.id' "$(macrec_dir)/active.json")"
  run_macrec stop --reason chord
  wait_session_field "${live_id}" status done
  assert_equals "0" "$?"
}

function test_keys_subcommand_errors() {
  run_macrec keys nosuch1 chords
  assert_equals "1" "${RUN_RC}"
  run_macrec keys nosuch1 bogus
  assert_equals "2" "${RUN_RC}"
  run_macrec keys
  assert_equals "2" "${RUN_RC}"
  run_macrec keys onlyid
  assert_equals "2" "${RUN_RC}"
  run_macrec keys a b c
  assert_equals "2" "${RUN_RC}"
}

function test_lifecycle_probe_round_trip() {
  PATH="${FAKE_BIN}:${PATH}" \
    HOME="${TEST_HOME}" \
    SCREENCAPTURE_BIN="${FAKE_BIN}/screencapture" \
    FFPROBE_BIN="${FAKE_BIN}/ffprobe" \
    JQ_BIN="$(command -v jq)" \
    PERL_BIN="$(command -v perl)" \
    UUIDGEN_BIN="${FAKE_BIN}/uuidgen" \
    NOHUP_BIN="$(command -v nohup)" \
    DF_BIN="${FAKE_BIN}/df" \
    PS_BIN="$(command -v ps)" \
    MKFIFO_BIN="$(command -v mkfifo)" \
    MACREC_BIN="${SCRIPT}" \
    MACREC_SHIP_BIN="${FAKE_BIN}/macrec_ship" \
    MACREC_NO_REEXEC=1 \
    MACREC_DOCTOR_NO_REEXEC=1 \
    MACREC_POLL_INTERVAL=0.02 \
    MACREC_READY_WAIT=2 \
    MACREC_READY_GRACE=0.05 \
    MACREC_STOP_INT_WAIT=0.4 \
    MACREC_STOP_TERM_WAIT=0.3 \
    MACREC_DOCTOR_LIFECYCLE_CAP=2 \
    MACREC_DOCTOR_LIFECYCLE_HOLD=0.1 \
    MACREC_DOCTOR_POLL_INTERVAL=0.02 \
    EVENT_LOG="${EVENT_LOG}" \
    FAKE_V_SLEEP=2 \
    bash "${DOCTOR}" run --id life1 --rect 0,0,240,150 --probes lifecycle \
    >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
  RUN_RC=$?
  assert_equals "0" "${RUN_RC}"
  assert_equals "true" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].metrics.start_ok' "${STDOUT_FILE}")"
  assert_equals "true" "$(jq -r '.probes[0].metrics.stop_ok' "${STDOUT_FILE}")"
}

function test_lifecycle_probe_rejects_failed_session() {
  PATH="${FAKE_BIN}:${PATH}" \
    HOME="${TEST_HOME}" \
    SCREENCAPTURE_BIN="${FAKE_BIN}/screencapture" \
    FFPROBE_BIN="${FAKE_BIN}/ffprobe" \
    JQ_BIN="$(command -v jq)" \
    PERL_BIN="$(command -v perl)" \
    UUIDGEN_BIN="${FAKE_BIN}/uuidgen" \
    NOHUP_BIN="$(command -v nohup)" \
    DF_BIN="${FAKE_BIN}/df" \
    PS_BIN="$(command -v ps)" \
    MKFIFO_BIN="$(command -v mkfifo)" \
    MACREC_BIN="${SCRIPT}" \
    MACREC_SHIP_BIN="${FAKE_BIN}/macrec_ship" \
    MACREC_NO_REEXEC=1 \
    MACREC_DOCTOR_NO_REEXEC=1 \
    MACREC_POLL_INTERVAL=0.02 \
    MACREC_READY_WAIT=2 \
    MACREC_READY_GRACE=0.05 \
    MACREC_STOP_INT_WAIT=0.4 \
    MACREC_STOP_TERM_WAIT=0.3 \
    MACREC_DOCTOR_LIFECYCLE_CAP=2 \
    MACREC_DOCTOR_LIFECYCLE_HOLD=0.1 \
    MACREC_DOCTOR_POLL_INTERVAL=0.02 \
    EVENT_LOG="${EVENT_LOG}" \
    FAKE_V_SLEEP=2 \
    FAKE_CAPTURE_INVALID=1 \
    bash "${DOCTOR}" run --id life-failed --rect 0,0,240,150 --probes lifecycle \
    >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
  RUN_RC=$?
  assert_equals "1" "${RUN_RC}"
  assert_equals "false" "$(jq -r '.probes[0].ok' "${STDOUT_FILE}")"
  assert_equals "failed" "$(jq -r '.probes[0].metrics.session_status' "${STDOUT_FILE}")"
  assert_contains "probe capture was not a valid video" "$(jq -r '.probes[0].detail' "${STDOUT_FILE}")"
}

function test_discard_removes_keys_log() {
  run_macrec start 0,0,80,80
  LAST_ID="$(jq -r '.id' "${STDOUT_FILE}")"
  printf '{"t":1.0,"id":1,"text":"a"}\n' >"$(session_path "${LAST_ID}")/keys.jsonl"
  printf 'WEBVTT\n' >"$(session_path "${LAST_ID}")/keys.vtt"
  run_macrec discard
  assert_equals "0" "${RUN_RC}"
  wait_session_field "${LAST_ID}" status discarded
  assert_file_not_exists "$(session_path "${LAST_ID}")/keys.jsonl"
  assert_file_not_exists "$(session_path "${LAST_ID}")/keys.vtt"
}
