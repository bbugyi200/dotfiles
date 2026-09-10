#!/bin/bash

#################################################################################
# Regression tests for the `tmux_load_avg` tmux status-line helper.             #
#                                                                               #
# tmux's status-right runs this every `status-interval` (2s), so it must       #
# never error or hang: a missing/failing `uptime`, or output that does not     #
# parse, must degrade to empty output (a bare hostname) rather than breaking   #
# the status line.                                                             #
#                                                                               #
# `uptime` is stubbed so both the Linux and macOS wordings, plus the failure   #
# modes, can be exercised without depending on the real load average.         #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_tmux_load_avg"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  BASH_BIN="$(command -v bash)"

  mkdir -p "${FAKE_BIN}"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

# Stub `uptime` to print the given line and exit 0.
function stub_uptime() {
  local output="$1"

  cat > "${FAKE_BIN}/uptime" <<EOF
#!/bin/bash
printf '%s\n' '${output}'
EOF
  chmod +x "${FAKE_BIN}/uptime"
}

# Stub `uptime` to fail, as it would if the load average could not be read.
function stub_uptime_failing() {
  cat > "${FAKE_BIN}/uptime" <<'EOF'
#!/bin/bash
exit 1
EOF
  chmod +x "${FAKE_BIN}/uptime"
}

# Run the script with the stubbed uptime first on PATH.
function run_tmux_load_avg() {
  PATH="${FAKE_BIN}:${PATH}" bash "${SCRIPT}" "$@"
}

function test_linux_wording_yields_first_load_figure() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 20.71, 24.19, 24.33'

  assert_equals " (20.71)" "$(run_tmux_load_avg)"
}

function test_macos_wording_yields_first_load_figure() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 3.36 3.26 2.94'

  assert_equals " (3.36)" "$(run_tmux_load_avg)"
}

function test_comma_decimal_separator_is_normalized() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 20,71, 24,19, 24,33'

  assert_equals " (20.71)" "$(run_tmux_load_avg)"
}

function test_unparseable_output_yields_empty() {
  stub_uptime 'this line has no load average in it'

  local output
  output="$(run_tmux_load_avg)"

  assert_empty "${output}"
  assert_not_contains "(" "${output}"
  assert_not_contains ")" "${output}"
}

function test_failing_uptime_yields_empty_and_exit_zero() {
  stub_uptime_failing

  local output
  output="$(run_tmux_load_avg)"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "0" "${exit_code}"
}

function test_missing_uptime_yields_empty_and_exit_zero() {
  local output
  output="$(PATH="${FAKE_BIN}" "${BASH_BIN}" "${SCRIPT}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "0" "${exit_code}"
}

function test_help_flag_prints_usage_and_exits_zero() {
  local output
  output="$(run_tmux_load_avg --help)"
  local exit_code=$?

  assert_contains "usage:" "${output}"
  assert_equals "0" "${exit_code}"
}

function test_unrecognized_argument_is_rejected() {
  assert_exit_code "2" "$(run_tmux_load_avg --bogus 2>&1)"
}
