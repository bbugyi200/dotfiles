#!/bin/bash

#################################################################################
# Regression tests for the `bas` remote-environment wrapper.                    #
#                                                                               #
# `bas` must run the remote command through the remote user's interactive login #
# shell (preferring zsh) and refresh an already-running tmux server's stored    #
# PATH/NVM environment before exec'ing the command, so that ~/bin and the       #
# NVM-managed AI CLIs are on PATH for tmux key bindings and run-shell callbacks. #
#                                                                               #
# autossh is stubbed so the remote command string `bas` builds can be inspected #
# without connecting to any host.                                               #
#################################################################################

BAS_SCRIPT="${PWD}/home/bin/executable_bas"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  ARGS_FILE="${TEST_TMP}/args.txt"
  REMOTE_CMD_FILE="${TEST_TMP}/remote_cmd.txt"

  mkdir -p "${FAKE_BIN}"

  # Stub autossh: record the full argument list and the remote command (the last
  # argument) verbatim, then exit successfully without connecting anywhere.
  cat >"${FAKE_BIN}/autossh" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >"${ARGS_FILE}"
printf '%s' "${@: -1}" >"${REMOTE_CMD_FILE}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/autossh"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

# Run bas with the stubbed autossh first on PATH.
function run_bas() {
  PATH="${FAKE_BIN}:${PATH}" \
    ARGS_FILE="${ARGS_FILE}" \
    REMOTE_CMD_FILE="${REMOTE_CMD_FILE}" \
    bash "${BAS_SCRIPT}" "$@"
}

function remote_cmd() {
  cat "${REMOTE_CMD_FILE}"
}

function autossh_args() {
  cat "${ARGS_FILE}"
}

function test_default_command_is_tm_sase() {
  run_bas athena

  assert_contains "exec tm sase" "$(remote_cmd)"
}

function test_one_string_command_is_preserved() {
  # A single quoted argument is passed through verbatim for the remote shell to
  # re-parse, so a multi-word command stays multi-word.
  run_bas athena "echo hello world"

  assert_contains "exec echo hello world" "$(remote_cmd)"
}

function test_split_command_is_quoted_safely() {
  # Split arguments are individually single-quoted so spaces and shell
  # metacharacters survive intact rather than being mangled by a "$*" join. The
  # inner command string (what the remote interactive shell ultimately receives,
  # after the outer login-shell wrapper unwraps it) is decoded for inspection.
  run_bas athena echo 'a b$c'

  local inner
  inner="$(decode_inner)"

  assert_contains "exec 'echo' 'a b\$c'" "${inner}"
}

function test_wrapper_prefers_interactive_login_zsh() {
  local cmd
  cmd="$(remote_cmd_for athena)"

  # Shell preference: remote $SHELL, then /bin/zsh, then /bin/bash.
  assert_contains '__bas_sh="$SHELL"' "${cmd}"
  assert_contains '|| __bas_sh=/bin/zsh' "${cmd}"
  assert_contains '|| __bas_sh=/bin/bash' "${cmd}"

  # zsh is invoked as an interactive login shell; other shells as login shells.
  assert_contains '*zsh) set -- -lic' "${cmd}"
  assert_contains 'set -- -lc' "${cmd}"
  assert_contains 'exec "$__bas_sh" "$@"' "${cmd}"
}

function test_wrapper_refreshes_tmux_environment_before_exec() {
  local cmd
  cmd="$(remote_cmd_for athena)"

  # Best-effort tmux refresh, guarded on a reachable server so no empty server
  # is started when none is running.
  assert_contains "tmux has-session" "${cmd}"
  assert_contains 'tmux set-environment -g PATH "$PATH"' "${cmd}"
  assert_contains 'tmux set-environment -g NVM_DIR "$NVM_DIR"' "${cmd}"
  assert_contains 'tmux set-environment -g NVM_BIN "$NVM_BIN"' "${cmd}"
  assert_contains 'tmux set-environment -g NVM_INC "$NVM_INC"' "${cmd}"

  # The refresh runs before the command is exec'd: the prelude's closing `fi`
  # immediately precedes the exec of the target command.
  assert_contains "fi; exec tm sase" "${cmd}"
}

function test_host_and_tty_are_forwarded_to_autossh() {
  run_bas myhost

  # A TTY is allocated (-t) so the remote interactive shell behaves correctly,
  # and the host is forwarded.
  assert_contains "-t myhost" "$(autossh_args)"
}

# Helper: run bas for HOST and echo the captured remote command.
function remote_cmd_for() {
  run_bas "$1"
  remote_cmd
}

# Recover the inner command string the remote interactive login shell receives.
# The captured remote command is the outer wrapper: it selects a login shell and
# exec's it with the inner string as a single argument. Running it with $SHELL
# pointed at a recorder that captures the chosen shell's last argument unwraps the
# one layer of quoting the wrapper adds, without running tmux or the real command.
function decode_inner() {
  local recorder="${TEST_TMP}/recorder"
  cat >"${recorder}" <<EOF
#!/bin/bash
printf '%s' "\${@: -1}" >"${TEST_TMP}/inner.txt"
EOF
  chmod +x "${recorder}"
  SHELL="${recorder}" bash -c "$(remote_cmd)"
  cat "${TEST_TMP}/inner.txt"
}
