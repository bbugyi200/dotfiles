#!/bin/bash

#################################################################################
# Regression tests for xc clipboard routing (OSC 52 first, never forwarded X11). #
#################################################################################

XC_SCRIPT="${PWD}/home/bin/executable_xc"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  EVENT_LOG="${TEST_TMP}/events.log"
  STDOUT_FILE="${TEST_TMP}/stdout.log"
  STDERR_FILE="${TEST_TMP}/stderr.log"
  SSH_STDIN="${TEST_TMP}/ssh_stdin"
  PBCOPY_STDIN="${TEST_TMP}/pbcopy_stdin"
  XCLIP_STDIN="${TEST_TMP}/xclip_stdin"
  TMUX_STDIN="${TEST_TMP}/tmux_stdin"
  RUN_RC=0

  UNAME_S=Linux
  TMUX_ENV=""
  SSH_TTY_ENV=""
  DISPLAY_ENV=""
  CLIP_PEER_ENV=""
  TMUX_CLIENTS=0
  SSH_FAIL=0

  mkdir -p "${FAKE_BIN}"
  : >"${EVENT_LOG}"

  write_uname_stub
  write_tmux_stub
  write_ssh_stub
  write_pbcopy_stub
  write_xclip_stub
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function write_uname_stub() {
  cat >"${FAKE_BIN}/uname" <<'EOF'
#!/bin/bash
if [[ "${1:-}" == "-s" ]]; then
  printf '%s\n' "${UNAME_S:-Linux}"
  exit 0
fi
printf '%s\n' "${UNAME_S:-Linux}"
EOF
  chmod +x "${FAKE_BIN}/uname"
}

function write_tmux_stub() {
  cat >"${FAKE_BIN}/tmux" <<'EOF'
#!/bin/bash
printf 'tmux' >>"${EVENT_LOG}"
for arg in "$@"; do printf ' <%s>' "${arg}" >>"${EVENT_LOG}"; done
printf '\n' >>"${EVENT_LOG}"
case "${1:-}" in
list-clients)
  if [[ "${TMUX_CLIENTS:-0}" == "1" ]]; then
    printf '0: kitty\n'
    exit 0
  fi
  exit 1
  ;;
load-buffer)
  cat >"${TMUX_STDIN}"
  exit 0
  ;;
*)
  printf 'unexpected tmux command: %s\n' "$*" >&2
  exit 2
  ;;
esac
EOF
  chmod +x "${FAKE_BIN}/tmux"
}

function write_ssh_stub() {
  cat >"${FAKE_BIN}/ssh" <<'EOF'
#!/bin/bash
printf 'ssh' >>"${EVENT_LOG}"
for arg in "$@"; do printf ' <%s>' "${arg}" >>"${EVENT_LOG}"; done
printf '\n' >>"${EVENT_LOG}"
cat >"${SSH_STDIN}"
if [[ "${SSH_FAIL:-0}" == "1" ]]; then
  printf 'ssh: Connection refused\n' >&2
  exit 1
fi
exit 0
EOF
  chmod +x "${FAKE_BIN}/ssh"
}

function write_pbcopy_stub() {
  cat >"${FAKE_BIN}/pbcopy" <<'EOF'
#!/bin/bash
printf 'pbcopy\n' >>"${EVENT_LOG}"
cat >"${PBCOPY_STDIN}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/pbcopy"
}

function write_xclip_stub() {
  cat >"${FAKE_BIN}/xclip" <<'EOF'
#!/bin/bash
printf 'xclip' >>"${EVENT_LOG}"
for arg in "$@"; do printf ' <%s>' "${arg}" >>"${EVENT_LOG}"; done
printf '\n' >>"${EVENT_LOG}"
cat >"${XCLIP_STDIN}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/xclip"
}

function run_xc() {
  local payload="$1"
  printf '%s' "${payload}" | env -u TMUX -u SSH_TTY -u DISPLAY -u CLIP_PEER \
    PATH="${FAKE_BIN}:${PATH}" \
    UNAME_S="${UNAME_S}" \
    TMUX_CLIENTS="${TMUX_CLIENTS}" \
    SSH_FAIL="${SSH_FAIL}" \
    EVENT_LOG="${EVENT_LOG}" \
    SSH_STDIN="${SSH_STDIN}" \
    PBCOPY_STDIN="${PBCOPY_STDIN}" \
    XCLIP_STDIN="${XCLIP_STDIN}" \
    TMUX_STDIN="${TMUX_STDIN}" \
    TMPDIR="${TEST_TMP}" \
    ${TMUX_ENV:+TMUX="${TMUX_ENV}"} \
    ${SSH_TTY_ENV:+SSH_TTY="${SSH_TTY_ENV}"} \
    ${DISPLAY_ENV:+DISPLAY="${DISPLAY_ENV}"} \
    ${CLIP_PEER_ENV:+CLIP_PEER="${CLIP_PEER_ENV}"} \
    bash "${XC_SCRIPT}" >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
  RUN_RC=$?
}

function events() {
  cat "${EVENT_LOG}"
}

function test_darwin_uses_pbcopy() {
  UNAME_S=Darwin
  DISPLAY_ENV=localhost:10.0
  TMUX_ENV=tmux-session
  run_xc "hello-mac"

  assert_same "0" "${RUN_RC}"
  assert_contains "hello-mac" "$(cat "${STDERR_FILE}")"
  assert_same "hello-mac" "$(cat "${PBCOPY_STDIN}")"
  assert_contains "pbcopy" "$(events)"
  assert_not_contains "xclip" "$(events)"
  assert_not_contains "tmux" "$(events)"
  assert_not_contains "ssh" "$(events)"
}

function test_tmux_with_client_uses_load_buffer_dash_w() {
  TMUX_ENV=tmux-session
  TMUX_CLIENTS=1
  DISPLAY_ENV=localhost:10.0
  run_xc "from-tmux"

  assert_same "0" "${RUN_RC}"
  assert_contains "from-tmux" "$(cat "${STDERR_FILE}")"
  assert_same "from-tmux" "$(cat "${TMUX_STDIN}")"
  assert_contains "tmux <load-buffer> <-w> <->" "$(events)"
  assert_contains "tmux <list-clients>" "$(events)"
  assert_not_contains "xclip" "$(events)"
  assert_not_contains "ssh" "$(events)"
}

function test_tmux_without_client_loads_buffer_then_headless_push() {
  TMUX_ENV=tmux-session
  TMUX_CLIENTS=0
  run_xc "detached-text"

  assert_same "0" "${RUN_RC}"
  assert_contains "detached-text" "$(cat "${STDERR_FILE}")"
  assert_contains "xc: no attached terminal; pushed via ssh mac pbcopy" "$(cat "${STDERR_FILE}")"
  assert_same "detached-text" "$(cat "${TMUX_STDIN}")"
  assert_same "detached-text" "$(cat "${SSH_STDIN}")"
  assert_contains "tmux <load-buffer> <->" "$(events)"
  assert_not_contains "<-w>" "$(events)"
  assert_contains "ssh <-x> <-T> <-o> <BatchMode=yes> <-o> <ConnectTimeout=3> <mac> <pbcopy>" "$(events)"
}

function test_ssh_tty_writes_exact_osc52_bytes() {
  SSH_TTY_ENV="${TEST_TMP}/tty"
  : >"${SSH_TTY_ENV}"
  run_xc "hello"

  assert_same "0" "${RUN_RC}"
  local expected
  expected="$(printf '\033]52;c;aGVsbG8=\a')"
  assert_same "${expected}" "$(cat "${SSH_TTY_ENV}")"
  assert_contains "hello" "$(cat "${STDERR_FILE}")"
  assert_not_contains "xclip" "$(events)"
  assert_not_contains "ssh" "$(events)"
}

function test_local_display_uses_xclip() {
  DISPLAY_ENV=":0"
  run_xc "local-x"

  assert_same "0" "${RUN_RC}"
  assert_same "local-x" "$(cat "${XCLIP_STDIN}")"
  assert_contains "xclip <-selection> <clipboard>" "$(events)"
  assert_not_contains "ssh" "$(events)"
}

function test_forwarded_display_never_reaches_xclip() {
  DISPLAY_ENV="localhost:10.0"
  run_xc "forwarded"

  assert_same "0" "${RUN_RC}"
  assert_not_contains "xclip" "$(events)"
  assert_contains "ssh <-x> <-T> <-o> <BatchMode=yes> <-o> <ConnectTimeout=3> <mac> <pbcopy>" "$(events)"
  assert_same "forwarded" "$(cat "${SSH_STDIN}")"
  assert_contains "xc: no attached terminal; pushed via ssh mac pbcopy" "$(cat "${STDERR_FILE}")"
  assert_file_not_exists "${XCLIP_STDIN}"
}

function test_headless_push_uses_clip_peer_override() {
  CLIP_PEER_ENV=apollo
  run_xc "peer-text"

  assert_same "0" "${RUN_RC}"
  assert_contains "xc: no attached terminal; pushed via ssh apollo pbcopy" "$(cat "${STDERR_FILE}")"
  assert_contains "ssh <-x> <-T> <-o> <BatchMode=yes> <-o> <ConnectTimeout=3> <apollo> <pbcopy>" "$(events)"
  assert_same "peer-text" "$(cat "${SSH_STDIN}")"
}

function test_headless_ssh_failure_exits_nonzero() {
  SSH_FAIL=1
  run_xc "will-fail"

  assert_same "1" "${RUN_RC}"
  assert_contains "ssh: Connection refused" "$(cat "${STDERR_FILE}")"
  assert_contains "xc: no attached terminal; pushed via ssh mac pbcopy" "$(cat "${STDERR_FILE}")"
}

function test_echoes_copied_text_to_stderr_not_stdout() {
  DISPLAY_ENV=":0"
  run_xc "visible"

  assert_same "0" "${RUN_RC}"
  assert_same "visible" "$(cat "${STDERR_FILE}")"
  assert_same "" "$(cat "${STDOUT_FILE}")"
}
