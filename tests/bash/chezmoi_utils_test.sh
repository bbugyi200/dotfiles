#!/bin/bash

#################################################################################
# Regression tests for shared chezmoi install-script helpers.                   #
#################################################################################

UTILS="${PWD}/lib/chezmoi_utils.sh"
source "${UTILS}"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  mkdir -p "${FAKE_BIN}"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function write_sudo_stub() {
  local rc="$1"
  cat >"${FAKE_BIN}/sudo" <<EOF
#!/bin/bash
if [[ "\$1" == "-n" && "\$2" == "true" ]]; then
  exit ${rc}
fi
exit 1
EOF
  chmod +x "${FAKE_BIN}/sudo"
}

function force_tty() {
  local rc="$1"
  eval "function chez::has_tty() { return ${rc}; }"
}

function run_can_sudo() {
  PATH="${FAKE_BIN}:${PATH}" chez::can_sudo
}

function run_exit_install() {
  local install_rc="$1"
  (chez::exit_install "$install_rc")
}

function test_can_sudo_true_via_passwordless_sudo() {
  write_sudo_stub 0
  force_tty 1

  run_can_sudo

  assert_same "0" "$?"
}

function test_can_sudo_true_via_tty_when_sudo_n_refuses() {
  write_sudo_stub 1
  force_tty 0

  run_can_sudo

  assert_same "0" "$?"
}

function test_can_sudo_false_when_sudo_n_and_tty_both_fail() {
  local rc=0
  write_sudo_stub 1
  force_tty 1

  run_can_sudo || rc="$?"

  assert_same "1" "$rc"
}

function test_exit_install_exits_zero_on_success() {
  force_tty 1

  run_exit_install 0

  assert_same "0" "$?"
}

function test_exit_install_exits_nonzero_when_interactive() {
  local rc=0
  force_tty 0

  run_exit_install 7 || rc="$?"

  assert_same "7" "$rc"
}

function test_exit_install_soft_fails_non_interactive_install_failure() {
  local output rc=0
  force_tty 1

  output="$(run_exit_install 7)" || rc="$?"

  assert_same "0" "$rc"
  assert_contains "WARNING" "${output}"
  assert_contains "non-interactive chezmoi apply" "${output}"
  assert_contains "chezmoi state delete-bucket --bucket=scriptState && chezmoi apply" "${output}"
}
