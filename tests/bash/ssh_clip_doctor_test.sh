#!/bin/bash

#################################################################################
# Regression tests for ssh_clip_doctor, the one-command E2E clipboard doctor.   #
#                                                                               #
# Every external tool the doctor uses (ssh, tmux, xclip, xdpyinfo, python3,     #
# nvim, timeout, setsid, flock, uname) is stubbed on PATH. ssh executes the    #
# remote command locally against a fake pasteboard file with fake               #
# pbcopy/pbpaste; tmux load-buffer -w delivers to the fake pasteboard only      #
# when a client is "attached". Poll counts come from CLIP_DOCTOR_POLL_* so     #
# each case runs in well under a second.                                        #
#################################################################################

DOCTOR="${PWD}/home/bin/executable_ssh_clip_doctor"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  mkdir -p "${FAKE_BIN}" "${TEST_TMP}/xdg"
  export TEST_TMP FAKE_BIN

  export FAKE_PB="${TEST_TMP}/pasteboard"
  export WRITE_LOG="${TEST_TMP}/writes.log"
  export SSH_LOG="${TEST_TMP}/ssh.log"
  printf 'ORIGINAL-CLIPBOARD-CONTENT' >"${FAKE_PB}"

  # Healthy defaults: armed pbproxy, XQuartz display, attached kitty client.
  export FAKE_PROBE_OWNERS="0x800001 0x800001"
  export FAKE_PROBE_KICK="already-armed"
  export FAKE_XDPYINFO_MODE="xquartz"
  export FAKE_TMUX_DISPLAY="DISPLAY=localhost:10.0"
  export FAKE_TMUX_CLIENTS="1"
  export FAKE_TMUX_FEATURES="bpaste,ccolour,clipboard,cstyle,extkeys,focus,title"
  export FAKE_TMUX_SET_CLIPBOARD="on"
  export FAKE_NVIM_PROVIDER="tmux-osc52"
  export FAKE_NVIM_DELIVER="1"
  export FAKE_PBPROXY_ARMED="1"
  export FAKE_UNAME="Linux"
  export DISPLAY="localhost:10.0"
  export TMUX="fake-tmux-session"
  export CLIP_PEER="mac"
  export XDG_RUNTIME_DIR="${TEST_TMP}/xdg"
  export CLIP_DOCTOR_POLL_TRIES="30"
  export CLIP_DOCTOR_POLL_INTERVAL="0.01"

  # ssh: strip ssh options + host, log the call, then run the remote command
  # locally with the fake pbcopy/pbpaste first on PATH.
  cat >"${FAKE_BIN}/ssh" <<'EOF'
#!/bin/bash
HOST_ARG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -x | -T) shift ;;
    -o) shift 2 ;;
    -*) shift ;;
    *)
      HOST_ARG="$1"
      shift
      break
      ;;
  esac
done
printf 'ssh host=%s cmd=%s\n' "${HOST_ARG}" "$*" >>"${SSH_LOG}"
if [[ -n "${FAKE_SSH_FAIL_CONTAINS:-}" && "$*" == *"${FAKE_SSH_FAIL_CONTAINS}"* ]]; then
  exit 255
fi
if [[ "$*" == *"pbcopy"* ]]; then
  printf 'ssh-pbcopy %s\n' "$*" >>"${WRITE_LOG}"
fi
export PATH="${FAKE_BIN}:${PATH}"
if [[ $# -eq 0 ]]; then exit 0; fi
bash -c "$*" ssh-stub
EOF
  chmod +x "${FAKE_BIN}/ssh"

  cat >"${FAKE_BIN}/pbcopy" <<'EOF'
#!/bin/bash
data=$(cat)
if [[ "${FAKE_RESTORE_FAIL:-0}" == "1" && "${data}" == "ORIGINAL-CLIPBOARD-CONTENT" ]]; then
  printf 'pbcopy-restore-fail\n' >>"${WRITE_LOG}"
  exit 1
fi
printf '%s' "${data}" >"${FAKE_PB}"
EOF
  chmod +x "${FAKE_BIN}/pbcopy"

  cat >"${FAKE_BIN}/pbpaste" <<'EOF'
#!/bin/bash
if [[ "${FAKE_PBPASTE_FAIL_FIRST:-0}" == "1" ]]; then
  count_file="${TEST_TMP}/pbpaste.count"
  n=$(cat "$count_file" 2>/dev/null || echo 0)
  n=$((n + 1))
  printf '%s' "$n" >"$count_file"
  if [[ "$n" -eq 1 ]]; then
    exit 1
  fi
fi
cat "${FAKE_PB}"
EOF
  chmod +x "${FAKE_BIN}/pbpaste"

  cat >"${FAKE_BIN}/tmux" <<'EOF'
#!/bin/bash
case "$1" in
  show-options)
    printf 'set-clipboard %s\n' "${FAKE_TMUX_SET_CLIPBOARD:-on}"
    ;;
  show-environment)
    if [[ -n "${FAKE_TMUX_DISPLAY:-}" ]]; then
      printf '%s\n' "${FAKE_TMUX_DISPLAY}"
    else
      exit 1
    fi
    ;;
  list-clients)
    if [[ "${FAKE_TMUX_CLIENTS:-1}" -gt 0 ]]; then
      i=0
      while [[ $i -lt "${FAKE_TMUX_CLIENTS}" ]]; do
        printf '%s\n' "${FAKE_TMUX_FEATURES:-clipboard}"
        i=$((i + 1))
      done
    else
      exit 1
    fi
    ;;
  display-message)
    printf 'term=xterm-kitty features=%s\n' "${FAKE_TMUX_FEATURES:-clipboard}"
    ;;
  load-buffer)
    data=$(cat)
    printf 'tmux-load-buffer\n' >>"${WRITE_LOG}"
    if [[ "${FAKE_TMUX_DROP_OSC52:-0}" == "1" ]]; then
      exit 0
    fi
    if [[ -n "${FAKE_TMUX_DELAY:-}" ]]; then
      (sleep "${FAKE_TMUX_DELAY}"; printf '%s' "${data}" >"${FAKE_PB}") &
      exit 0
    fi
    if [[ "${FAKE_TMUX_CLIENTS:-1}" -gt 0 ]]; then
      printf '%s' "${data}" >"${FAKE_PB}"
    fi
    if [[ -n "${FAKE_TMUX_KILL_PARENT:-}" ]]; then
      count_file="${TEST_TMP}/tmux-kill.count"
      n=$(cat "$count_file" 2>/dev/null || echo 0)
      n=$((n + 1))
      printf '%s' "$n" >"$count_file"
      if [[ "$n" -eq 1 ]]; then
        if [[ "${FAKE_TMUX_KILL_PARENT}" == "TERM" ]]; then
          kill -TERM "$PPID" 2>/dev/null || true
        else
          kill -INT "$PPID" 2>/dev/null || true
        fi
        sleep 0.2
      fi
    fi
    exit 0
    ;;
  save-buffer)
    cat "${FAKE_PB}"
    ;;
  *)
    printf 'tmux-stub: unknown %s\n' "$*" >&2
    exit 1
    ;;
esac
EOF
  chmod +x "${FAKE_BIN}/tmux"

  cat >"${FAKE_BIN}/xdpyinfo" <<'EOF'
#!/bin/bash
case "${FAKE_XDPYINFO_MODE:-xquartz}" in
  xquartz)
    if [[ "$*" == *queryExtensions* ]]; then
      printf '    Apple-WM  (opcode: 130, base event: 68, base error: 130)\n'
    fi
    exit 0
    ;;
  other)
    exit 0
    ;;
  hung)
    exit 124
    ;;
  dead)
    exit 1
    ;;
esac
EOF
  chmod +x "${FAKE_BIN}/xdpyinfo"

  cat >"${FAKE_BIN}/python3" <<'EOF'
#!/bin/bash
cmd=""
for a in "$@"; do
  case "$a" in
    owners | kick | blackhole) cmd="$a" ;;
  esac
done
case "${cmd}" in
  owners) printf '%s\n' "${FAKE_PROBE_OWNERS:-0x800001 0x800001}" ;;
  kick) printf '%s\n' "${FAKE_PROBE_KICK:-already-armed}" ;;
  blackhole) printf 'swallowed 1 SelectionRequest(s)\n' ;;
  *)
    printf 'python3-stub: no probe cmd in %s\n' "$*" >&2
    exit 1
    ;;
esac
EOF
  chmod +x "${FAKE_BIN}/python3"

  cat >"${FAKE_BIN}/xclip" <<'EOF'
#!/bin/bash
# A lingering selection owner must never inherit the single-instance lock FD.
if ls -l /proc/$$/fd 2>/dev/null | grep -q "ssh_clip_doctor.lock"; then
  printf 'LEAKED-LOCK-FD\n' >>"${WRITE_LOG}"
fi
data=$(cat)
printf 'xclip\n' >>"${WRITE_LOG}"
if [[ "${FAKE_PBPROXY_ARMED:-1}" == "1" ]]; then
  printf '%s' "${data}" >"${FAKE_PB}"
fi
exit 0
EOF
  chmod +x "${FAKE_BIN}/xclip"

  cat >"${FAKE_BIN}/nvim" <<'EOF'
#!/bin/bash
# Editor servers autostarted by the live probe must never inherit the lock FD.
if ls -l /proc/$$/fd 2>/dev/null | grep -q "ssh_clip_doctor.lock"; then
  printf 'LEAKED-LOCK-FD\n' >>"${WRITE_LOG}"
fi
joined="$*"
sent=$(printf '%s' "${joined}" | grep -o 'ssh-clip-doctor-nvim-[A-Za-z0-9_.-]*' | head -1 || true)
# The writefile target is mktemp output, so honor $TMPDIR: take the
# single-quoted absolute path in the lua invocation ('+' has no slash).
out=$(printf '%s' "${joined}" | grep -o "'/[^']*'" | head -1 | tr -d "'" || true)
if [[ -n "${out}" ]]; then
  printf '%s' "${FAKE_NVIM_PROVIDER:-tmux-osc52}" >"${out}"
fi
if [[ -n "${sent}" && "${FAKE_NVIM_DELIVER:-1}" == "1" ]]; then
  printf '%s\n' "${sent}" >"${FAKE_PB}"
fi
printf 'nvim\n' >>"${WRITE_LOG}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/nvim"

  cat >"${FAKE_BIN}/uname" <<'EOF'
#!/bin/bash
printf '%s\n' "${FAKE_UNAME:-Linux}"
EOF
  chmod +x "${FAKE_BIN}/uname"

  # Sanitized PATH: only the stubs plus system dirs, so a real xc/xp (or any
  # other helper) installed on the test machine cannot leak into a case.
  export PATH="${FAKE_BIN}:/usr/bin:/bin"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function run_doctor() {
  OUT_FILE="${TEST_TMP}/out.txt"
  bash "${DOCTOR}" "$@" >"${OUT_FILE}" 2>&1
  DOCTOR_RC=$?
  DOCTOR_OUT="$(cat "${OUT_FILE}")"
}

function writes_log() {
  if [[ -f "${WRITE_LOG}" ]]; then
    cat "${WRITE_LOG}"
  else
    printf ''
  fi
}

function make_fake_xc() {
  cat >"${FAKE_BIN}/xc" <<'EOF'
#!/bin/bash
data=$(cat)
printf 'xc\n' >>"${WRITE_LOG}"
printf '%s' "${data}" >"${FAKE_PB}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/xc"
}

function make_fake_xp() {
  cat >"${FAKE_BIN}/xp" <<'EOF'
#!/bin/bash
cat "${FAKE_PB}"
EOF
  chmod +x "${FAKE_BIN}/xp"
}

function test_help_prints_usage_and_exits_zero() {
  run_doctor -h

  assert_equals 0 "${DOCTOR_RC}"
  assert_contains "BEFORE restarting XQuartz or reconnecting" "${DOCTOR_OUT}"
  assert_contains "was WEDGED" "${DOCTOR_OUT}"
  assert_contains "Exit status" "${DOCTOR_OUT}"
}

function test_unknown_flag_exits_two() {
  run_doctor --bogus

  assert_equals 2 "${DOCTOR_RC}"
  assert_contains "unknown arg" "${DOCTOR_OUT}"
}

function test_macos_refusal_exits_two() {
  export FAKE_UNAME="Darwin"
  run_doctor --observe

  assert_equals 2 "${DOCTOR_RC}"
  assert_contains "run this on the remote host" "${DOCTOR_OUT}"
}

function test_observe_makes_zero_clipboard_writes() {
  run_doctor --observe

  assert_equals 0 "${DOCTOR_RC}"
  assert_contains "pbproxy armed" "${DOCTOR_OUT}"
  assert_not_contains "== end-to-end" "${DOCTOR_OUT}"
  assert_equals "" "$(writes_log)"
  assert_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
}

function test_healthy_armed_pbproxy_passes() {
  run_doctor

  assert_equals 0 "${DOCTOR_RC}"
  assert_contains "pbproxy armed" "${DOCTOR_OUT}"
  assert_contains "peer" "${DOCTOR_OUT}"
  assert_contains "PASS" "${DOCTOR_OUT}"
}

function test_restore_returns_original_pasteboard() {
  run_doctor

  assert_equals 0 "${DOCTOR_RC}"
  assert_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
  assert_contains "restored previous Mac text clipboard" "${DOCTOR_OUT}"
}

function test_unarmed_without_repair_fails() {
  export FAKE_PROBE_OWNERS="0x400002 0x800001"
  export FAKE_PBPROXY_ARMED="0"
  run_doctor

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "NOT armed" "${DOCTOR_OUT}"
  assert_contains "--repair" "${DOCTOR_OUT}"
}

function test_unarmed_with_repair_reports_unarmed() {
  export FAKE_PROBE_OWNERS="0x400002 0x800001"
  export FAKE_PROBE_KICK="armed (was UNARMED)"
  export FAKE_PBPROXY_ARMED="1"
  run_doctor --repair

  # The NOT-armed finding stays a FAIL line (exit 1); the kick label plus the
  # passing x11 re-test below it prove the repair worked.
  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "NOT armed" "${DOCTOR_OUT}"
  assert_contains "was UNARMED" "${DOCTOR_OUT}"
  assert_contains "x11" "${DOCTOR_OUT}"
}

function test_wedged_with_repair_reports_wedged() {
  export FAKE_PROBE_OWNERS="0x400003 0x800001"
  export FAKE_PROBE_KICK="armed (was WEDGED)"
  export FAKE_PBPROXY_ARMED="1"
  run_doctor --repair

  # The NOT-armed finding stays a FAIL line (exit 1); the kick label plus the
  # passing x11 re-test below it prove the repair worked.
  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "NOT armed" "${DOCTOR_OUT}"
  assert_contains "was WEDGED" "${DOCTOR_OUT}"
  assert_contains "x11" "${DOCTOR_OUT}"
}

function test_stale_display_fails() {
  export FAKE_TMUX_DISPLAY="DISPLAY=localhost:11.0"
  run_doctor --observe

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "differs from the latest attach" "${DOCTOR_OUT}"
}

function test_hung_display_fails() {
  export FAKE_XDPYINFO_MODE="hung"
  run_doctor --observe

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "HANGS" "${DOCTOR_OUT}"
}

function test_dead_display_fails() {
  export FAKE_XDPYINFO_MODE="dead"
  run_doctor --observe

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "refuses connections" "${DOCTOR_OUT}"
}

function test_non_xquartz_display_fails() {
  export FAKE_XDPYINFO_MODE="other"
  run_doctor --observe

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "NOT XQuartz" "${DOCTOR_OUT}"
}

function test_display_unset_reports_info_only() {
  unset DISPLAY
  run_doctor

  assert_equals 0 "${DOCTOR_RC}"
  assert_contains "DISPLAY unset" "${DOCTOR_OUT}"
}

function test_osc52_no_attached_client_fails() {
  export FAKE_TMUX_CLIENTS="0"
  run_doctor

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "no attached clients" "${DOCTOR_OUT}"
}

function test_osc52_client_without_clipboard_feature_fails() {
  export FAKE_TMUX_FEATURES="bpaste,focus,title"
  run_doctor --observe

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "clipboard" "${DOCTOR_OUT}"
}

function test_payloads_compare_sha256() {
  run_doctor --payloads

  assert_equals 0 "${DOCTOR_RC}"
  assert_contains "peer/multiline" "${DOCTOR_OUT}"
  assert_contains "peer/unicode" "${DOCTOR_OUT}"
  assert_contains "peer/64KiB" "${DOCTOR_OUT}"
  assert_contains "osc52/multiline" "${DOCTOR_OUT}"
  assert_contains "osc52/unicode" "${DOCTOR_OUT}"
  assert_contains "osc52/64KiB" "${DOCTOR_OUT}"
  assert_contains "sha256" "${DOCTOR_OUT}"
  assert_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
}

function test_xc_and_xp_pass_when_installed() {
  make_fake_xc
  make_fake_xp
  run_doctor

  assert_equals 0 "${DOCTOR_RC}"
  assert_contains "xc -> Mac" "${DOCTOR_OUT}"
  assert_contains "xp returned the peer sentinel" "${DOCTOR_OUT}"
}

function test_xc_and_xp_skipped_when_missing() {
  run_doctor

  assert_equals 0 "${DOCTOR_RC}"
  assert_contains "xc: not on PATH; skipped" "${DOCTOR_OUT}"
  assert_contains "xp: not on PATH; skipped" "${DOCTOR_OUT}"
}

function test_peer_host_comes_from_clip_peer() {
  export CLIP_PEER="ula"
  run_doctor --observe

  assert_equals 0 "${DOCTOR_RC}"
  assert_contains "peer host: ula" "${DOCTOR_OUT}"
  assert_contains "host=ula" "$(cat "${SSH_LOG}")"
}

function test_lock_fd_does_not_leak_to_children() {
  run_doctor

  assert_equals 0 "${DOCTOR_RC}"
  assert_not_contains "LEAKED-LOCK-FD" "$(writes_log)"
}

function test_concurrent_run_guard_exits_two() {
  LOCK_FILE="${XDG_RUNTIME_DIR}/ssh_clip_doctor.lock"
  exec 200>"${LOCK_FILE}"
  flock -n 200
  run_doctor --observe
  exec 200>&-

  assert_equals 2 "${DOCTOR_RC}"
  assert_contains "another copy is running" "${DOCTOR_OUT}"
}

function test_transport_error_never_becomes_pass() {
  export FAKE_SSH_FAIL_CONTAINS="grep -qxF"
  run_doctor

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "transport or poll error" "${DOCTOR_OUT}"
  assert_not_contains "arrived in " "${DOCTOR_OUT}"
  assert_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
}

function test_snapshot_failure_stops_without_writes() {
  export FAKE_PBPASTE_FAIL_FIRST="1"
  run_doctor

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "could not read Mac clipboard for restore" "${DOCTOR_OUT}"
  assert_contains "stopping without writing" "${DOCTOR_OUT}"
  assert_equals "" "$(writes_log)"
  assert_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
}

function test_successful_empty_restoration() {
  printf '' >"${FAKE_PB}"
  run_doctor

  assert_equals 0 "${DOCTOR_RC}"
  assert_contains "restored previous Mac text clipboard" "${DOCTOR_OUT}"
  assert_equals "" "$(cat "${FAKE_PB}")"
}

function test_restore_failure_keeps_backup_and_fails() {
  export FAKE_RESTORE_FAIL="1"
  run_doctor

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "failed to restore previous Mac clipboard" "${DOCTOR_OUT}"
  assert_contains "backup kept at" "${DOCTOR_OUT}"
  assert_contains "pbcopy-restore-fail" "$(writes_log)"
  assert_not_contains "restored previous Mac text clipboard" "${DOCTOR_OUT}"
  assert_not_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
}

function test_sigterm_restores_once_and_stops_writes() {
  export FAKE_TMUX_KILL_PARENT="TERM"
  run_doctor

  assert_equals 143 "${DOCTOR_RC}"
  assert_contains "restored previous Mac text clipboard" "${DOCTOR_OUT}"
  assert_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
  assert_not_contains "nvim" "$(writes_log)"
  restore_count=$(printf '%s' "${DOCTOR_OUT}" | grep -c "restored previous Mac text clipboard" || true)
  assert_equals 1 "${restore_count}"
}

function test_sigint_restores_once_and_stops_writes() {
  export FAKE_TMUX_KILL_PARENT="INT"
  run_doctor

  assert_equals 130 "${DOCTOR_RC}"
  assert_contains "restored previous Mac text clipboard" "${DOCTOR_OUT}"
  assert_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
  assert_not_contains "nvim" "$(writes_log)"
  restore_count=$(printf '%s' "${DOCTOR_OUT}" | grep -c "restored previous Mac text clipboard" || true)
  assert_equals 1 "${restore_count}"
}

function test_no_restore_skips_snapshot_and_leaves_clipboard() {
  run_doctor --no-restore

  assert_equals 0 "${DOCTOR_RC}"
  assert_not_contains "restored previous Mac text clipboard" "${DOCTOR_OUT}"
  assert_not_contains "could not read Mac clipboard" "${DOCTOR_OUT}"
  assert_not_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
}

function test_dropped_osc52_payloads_fail_independently() {
  export FAKE_TMUX_DROP_OSC52="1"
  run_doctor --payloads

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "peer/64KiB" "${DOCTOR_OUT}"
  assert_contains "osc52/64KiB" "${DOCTOR_OUT}"
  assert_contains "sha256 mismatch" "${DOCTOR_OUT}"
  assert_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
}

function test_delayed_osc52_delivery_succeeds_inside_budget() {
  export FAKE_TMUX_DELAY="0.05"
  run_doctor --payloads

  assert_equals 0 "${DOCTOR_RC}"
  assert_contains "osc52/multiline" "${DOCTOR_OUT}"
  assert_contains "osc52/unicode" "${DOCTOR_OUT}"
  assert_contains "osc52/64KiB" "${DOCTOR_OUT}"
  # Delayed background writes may land after restore; wait then restore expectation.
  sleep 0.3
  printf 'ORIGINAL-CLIPBOARD-CONTENT' >"${FAKE_PB}"
  assert_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
}

function test_expired_osc52_delivery_fails() {
  export FAKE_TMUX_DELAY="2"
  export CLIP_DOCTOR_POLL_TRIES="10"
  export CLIP_DOCTOR_POLL_INTERVAL="0.01"
  run_doctor --payloads

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "sha256 mismatch" "${DOCTOR_OUT}"
  sleep 2.2
  printf 'ORIGINAL-CLIPBOARD-CONTENT' >"${FAKE_PB}"
  assert_equals "ORIGINAL-CLIPBOARD-CONTENT" "$(cat "${FAKE_PB}")"
}
