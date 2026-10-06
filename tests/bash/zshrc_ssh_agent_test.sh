#!/bin/bash

#################################################################################
# Behavioral tests for the idempotent ssh-agent bootstrap in home/dot_zshrc.    #
#                                                                               #
# The bootstrap must reuse a live or empty agent at ${HOME}/.ssh/agent.sock,    #
# start exactly one agent when the socket is stale, and never depend on $USER,  #
# pgrep, or ~/.ssh-agent-thing. Stub ssh-add/ssh-agent binaries on PATH log     #
# their argv so no real agents start.                                           #
#################################################################################

REPO_ROOT="${PWD}"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  TEST_HOME="${TEST_TMP}/home"
  FAKE_BIN="${TEST_TMP}/bin"
  LOG_FILE="${TEST_TMP}/calls.log"
  AGENT_STATE="${TEST_TMP}/agent_state"

  mkdir -p "${TEST_HOME}" "${FAKE_BIN}"
  : >"${LOG_FILE}"
  printf '0' >"${AGENT_STATE}"

  # Stub ssh-add: exit code comes from AGENT_STATE (0 = has identities,
  # 1 = reachable but empty, 2 = unreachable) and every call is logged.
  cat >"${FAKE_BIN}/ssh-add" <<'EOF'
#!/bin/bash
printf 'ssh-add sock=%s argv=%s\n' "${SSH_AUTH_SOCK:-UNSET}" "$*" >>"${LOG_FILE}"
code="$(cat "${AGENT_STATE}")"
if [[ "${code}" == "0" ]]; then
  printf 'fake-identity\n'
fi
exit "${code}"
EOF
  chmod +x "${FAKE_BIN}/ssh-add"

  # Stub ssh-agent: log the call and flip the state to reachable-but-empty,
  # modelling the fresh agent a real ssh-agent -a would leave behind.
  cat >"${FAKE_BIN}/ssh-agent" <<'EOF'
#!/bin/bash
printf 'ssh-agent argv=%s\n' "$*" >>"${LOG_FILE}"
printf '1' >"${AGENT_STATE}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/ssh-agent"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function require_zsh() {
  if ! command -v zsh >/dev/null 2>&1; then
    bashunit::skip "zsh is required for ssh-agent bootstrap verification"
    return 1
  fi
}

function set_agent_state() {
  printf '%s' "${1}" >"${AGENT_STATE}"
}

function write_ssh_agent_fragment() {
  awk '/--- ssh-agent bootstrap \(managed\) ---/,/--- end ssh-agent bootstrap ---/' \
    "${REPO_ROOT}/home/dot_zshrc" >"${TEST_TMP}/ssh-agent-bootstrap.zsh"
}

function agent_spawn_count() {
  grep -c '^ssh-agent ' "${LOG_FILE}" || true
}

# Source the bootstrap fragment once in a clean zsh and print the result.
function run_bootstrap_probe() {
  write_ssh_agent_fragment

  HOME="${TEST_HOME}" PATH="${FAKE_BIN}:${PATH}" \
    LOG_FILE="${LOG_FILE}" AGENT_STATE="${AGENT_STATE}" \
    zsh -f -c '
      source "$1"
      print -r -- "sock=${SSH_AUTH_SOCK:-UNSET}"
      print -r -- "pid=${SSH_AGENT_PID:-UNSET}"
    ' bootstrap-probe "${TEST_TMP}/ssh-agent-bootstrap.zsh"
}

# Source the bootstrap fragment twice in one shell (idempotence probe).
function run_bootstrap_probe_twice() {
  write_ssh_agent_fragment

  HOME="${TEST_HOME}" PATH="${FAKE_BIN}:${PATH}" \
    LOG_FILE="${LOG_FILE}" AGENT_STATE="${AGENT_STATE}" \
    zsh -f -c '
      source "$1"
      source "$1"
      print -r -- "sock=${SSH_AUTH_SOCK:-UNSET}"
      print -r -- "pid=${SSH_AGENT_PID:-UNSET}"
    ' bootstrap-probe "${TEST_TMP}/ssh-agent-bootstrap.zsh"
}

function test_live_socket_spawns_nothing() {
  require_zsh || return 0
  set_agent_state 0

  output="$(run_bootstrap_probe)"

  assert_same "0" "$(agent_spawn_count)"
  assert_contains "sock=${TEST_HOME}/.ssh/agent.sock" "${output}"
  assert_contains "pid=UNSET" "${output}"
  assert_contains "ssh-add sock=${TEST_HOME}/.ssh/agent.sock argv=-l" "$(cat "${LOG_FILE}")"
}

function test_empty_agent_spawns_nothing() {
  require_zsh || return 0
  set_agent_state 1

  output="$(run_bootstrap_probe)"

  assert_same "0" "$(agent_spawn_count)"
  assert_contains "sock=${TEST_HOME}/.ssh/agent.sock" "${output}"
  assert_contains "pid=UNSET" "${output}"
}

function test_dead_socket_starts_one_agent_and_removes_stale_path() {
  require_zsh || return 0
  set_agent_state 2
  mkdir -p "${TEST_HOME}/.ssh"
  touch "${TEST_HOME}/.ssh/agent.sock"

  output="$(run_bootstrap_probe)"

  assert_same "1" "$(agent_spawn_count)"
  assert_contains "ssh-agent argv=-a ${TEST_HOME}/.ssh/agent.sock" "$(cat "${LOG_FILE}")"
  assert_file_not_exists "${TEST_HOME}/.ssh/agent.sock"
  assert_contains "sock=${TEST_HOME}/.ssh/agent.sock" "${output}"
  assert_contains "pid=UNSET" "${output}"
}

function test_user_unset_behaves_like_live_socket() {
  require_zsh || return 0
  set_agent_state 0
  write_ssh_agent_fragment

  output="$(
    env -u USER HOME="${TEST_HOME}" PATH="${FAKE_BIN}:${PATH}" \
      LOG_FILE="${LOG_FILE}" AGENT_STATE="${AGENT_STATE}" \
      zsh -f -c '
        source "$1"
        print -r -- "sock=${SSH_AUTH_SOCK:-UNSET}"
      ' bootstrap-probe "${TEST_TMP}/ssh-agent-bootstrap.zsh"
  )"

  assert_same "0" "$(agent_spawn_count)"
  assert_contains "sock=${TEST_HOME}/.ssh/agent.sock" "${output}"
}

function test_foreign_inherited_sock_is_replaced() {
  require_zsh || return 0
  set_agent_state 0
  write_ssh_agent_fragment

  output="$(
    HOME="${TEST_HOME}" PATH="${FAKE_BIN}:${PATH}" \
      LOG_FILE="${LOG_FILE}" AGENT_STATE="${AGENT_STATE}" \
      SSH_AUTH_SOCK=/tmp/forwarded/agent.999 \
      zsh -f -c '
        source "$1"
        print -r -- "sock=${SSH_AUTH_SOCK:-UNSET}"
      ' bootstrap-probe "${TEST_TMP}/ssh-agent-bootstrap.zsh"
  )"

  assert_same "0" "$(agent_spawn_count)"
  assert_contains "sock=${TEST_HOME}/.ssh/agent.sock" "${output}"
  assert_not_contains "forwarded" "${output}"
}

function test_sourcing_twice_is_idempotent() {
  require_zsh || return 0
  set_agent_state 2

  output="$(run_bootstrap_probe_twice)"

  assert_same "1" "$(agent_spawn_count)"
  assert_contains "sock=${TEST_HOME}/.ssh/agent.sock" "${output}"
}
