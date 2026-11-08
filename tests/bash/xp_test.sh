#!/bin/bash

#################################################################################
# Regression tests for xp Mac clipboard reader.                                 #
#################################################################################

XP_SCRIPT="${PWD}/home/bin/executable_xp"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  EVENT_LOG="${TEST_TMP}/events.log"
  STDOUT_FILE="${TEST_TMP}/stdout.log"
  STDERR_FILE="${TEST_TMP}/stderr.log"
  RUN_RC=0

  UNAME_S=Linux
  CLIP_PEER_ENV=""
  SSH_FAIL=0
  PASTE_TEXT="mac-clipboard"

  mkdir -p "${FAKE_BIN}"
  : >"${EVENT_LOG}"

  write_uname_stub
  write_pbpaste_stub
  write_ssh_stub
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

function write_pbpaste_stub() {
  cat >"${FAKE_BIN}/pbpaste" <<'EOF'
#!/bin/bash
printf 'local-pbpaste\n' >>"${EVENT_LOG}"
printf '%s' "${PASTE_TEXT}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/pbpaste"
}

function write_ssh_stub() {
  cat >"${FAKE_BIN}/ssh" <<'EOF'
#!/bin/bash
printf 'ssh' >>"${EVENT_LOG}"
for arg in "$@"; do printf ' <%s>' "${arg}" >>"${EVENT_LOG}"; done
printf '\n' >>"${EVENT_LOG}"
if [[ "${SSH_FAIL:-0}" == "1" ]]; then
  printf 'ssh: Connection refused\n' >&2
  exit 7
fi
printf '%s' "${PASTE_TEXT}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/ssh"
}

function run_xp() {
  env -u CLIP_PEER \
    PATH="${FAKE_BIN}:${PATH}" \
    UNAME_S="${UNAME_S}" \
    SSH_FAIL="${SSH_FAIL}" \
    PASTE_TEXT="${PASTE_TEXT}" \
    EVENT_LOG="${EVENT_LOG}" \
    ${CLIP_PEER_ENV:+CLIP_PEER="${CLIP_PEER_ENV}"} \
    bash "${XP_SCRIPT}" >"${STDOUT_FILE}" 2>"${STDERR_FILE}"
  RUN_RC=$?
}

function events() {
  cat "${EVENT_LOG}"
}

function test_darwin_uses_pbpaste() {
  UNAME_S=Darwin
  run_xp

  assert_same "0" "${RUN_RC}"
  assert_same "mac-clipboard" "$(cat "${STDOUT_FILE}")"
  assert_contains "local-pbpaste" "$(events)"
  assert_not_contains "ssh" "$(events)"
}

function test_linux_uses_ssh_pbpaste() {
  run_xp

  assert_same "0" "${RUN_RC}"
  assert_same "mac-clipboard" "$(cat "${STDOUT_FILE}")"
  assert_contains "ssh <-x> <-T> <-o> <BatchMode=yes> <-o> <ConnectTimeout=3> <mac> <pbpaste>" "$(events)"
  assert_not_contains "local-pbpaste" "$(events)"
}

function test_clip_peer_override() {
  CLIP_PEER_ENV=apollo
  PASTE_TEXT="from-apollo"
  run_xp

  assert_same "0" "${RUN_RC}"
  assert_same "from-apollo" "$(cat "${STDOUT_FILE}")"
  assert_contains "ssh <-x> <-T> <-o> <BatchMode=yes> <-o> <ConnectTimeout=3> <apollo> <pbpaste>" "$(events)"
}

function test_nonzero_ssh_exit_propagates() {
  SSH_FAIL=1
  run_xp

  assert_same "7" "${RUN_RC}"
  assert_contains "ssh: Connection refused" "$(cat "${STDERR_FILE}")"
  assert_same "" "$(cat "${STDOUT_FILE}")"
}
