#!/bin/bash

#################################################################################
# Regression tests for the `tmux_load_avg` tmux status-line helper.             #
#                                                                               #
# tmux's status-right runs this every `status-interval` (2s), so it must       #
# never error or hang: a missing/failing `uptime`, output that does not parse, #
# or memory counters that cannot be collected must degrade quietly rather than #
# breaking the status line.                                                     #
#                                                                               #
# `uptime`, `vm_stat`, and `sysctl` are stubbed where the full helper runs.     #
# Memory parsers are also tested directly so the suite never depends on the    #
# host's live RAM by accident.                                                  #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_tmux_load_avg"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  BASH_BIN="$(command -v bash)"
  CALL_LOG="${TEST_TMP}/calls.log"
  TEST_RUNNER="${TEST_TMP}/run_tmux_load_avg"

  export CALL_LOG

  mkdir -p "${FAKE_BIN}"

  cat > "${TEST_RUNNER}" <<'EOF'
#!/bin/bash
script="$1"
shift

source "${script}"

if [[ -n "${TEST_OSTYPE:-}" ]]; then
  OSTYPE="${TEST_OSTYPE}"
fi

if [[ -n "${TEST_MEMORY_MODE:-}" ]]; then
  function memory_percent() {
    if [[ -n "${TEST_MEMORY_CALL_LOG:-}" ]]; then
      printf 'memory_percent\n' >> "${TEST_MEMORY_CALL_LOG}"
    fi

    case "${TEST_MEMORY_MODE}" in
    success)
      printf '%s' "${TEST_MEMORY_VALUE}"
      ;;
    fail)
      return 1
      ;;
    empty)
      return 0
      ;;
    *)
      return 99
      ;;
    esac
  }
fi

run "$@"
EOF
  chmod +x "${TEST_RUNNER}"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function calls() {
  if [[ -f "${CALL_LOG}" ]]; then
    cat "${CALL_LOG}"
  fi
}

function call_count() {
  local name="$1"

  if [[ -f "${CALL_LOG}" ]]; then
    grep -F -x -c "${name}" "${CALL_LOG}" || true
  else
    printf '0'
  fi
}

function install_uptime_stub() {
  cat > "${FAKE_BIN}/uptime" <<'EOF'
#!/bin/bash
printf 'uptime\n' >> "${CALL_LOG}"
if [[ "${UPTIME_FAIL:-0}" == 1 ]]; then
  exit 1
fi
printf '%s\n' "${UPTIME_OUTPUT}"
EOF
  chmod +x "${FAKE_BIN}/uptime"
}

# Stub `uptime` to print the given line and exit 0.
function stub_uptime() {
  export UPTIME_OUTPUT="$1"
  export UPTIME_FAIL=0

  install_uptime_stub
}

# Stub `uptime` to fail, as it would if the load average could not be read.
function stub_uptime_failing() {
  export UPTIME_OUTPUT=''
  export UPTIME_FAIL=1

  install_uptime_stub
}

function stub_vm_stat() {
  export VM_STAT_OUTPUT="$1"
  export VM_STAT_FAIL=0

  cat > "${FAKE_BIN}/vm_stat" <<'EOF'
#!/bin/bash
printf 'vm_stat\n' >> "${CALL_LOG}"
if [[ "${VM_STAT_FAIL:-0}" == 1 ]]; then
  exit 1
fi
printf '%s\n' "${VM_STAT_OUTPUT}"
EOF
  chmod +x "${FAKE_BIN}/vm_stat"
}

function stub_vm_stat_failing() {
  stub_vm_stat ''
  export VM_STAT_FAIL=1
}

function stub_sysctl_memsize() {
  export SYSCTL_MEMSIZE="$1"
  export SYSCTL_FAIL=0

  cat > "${FAKE_BIN}/sysctl" <<'EOF'
#!/bin/bash
printf 'sysctl %s\n' "$*" >> "${CALL_LOG}"
if [[ "${SYSCTL_FAIL:-0}" == 1 ]]; then
  exit 1
fi
if [[ "$*" != "-n hw.memsize" ]]; then
  exit 64
fi
printf '%s\n' "${SYSCTL_MEMSIZE}"
EOF
  chmod +x "${FAKE_BIN}/sysctl"
}

function stub_sysctl_failing() {
  stub_sysctl_memsize ''
  export SYSCTL_FAIL=1
}

# Run the script with stubbed uptime and an internal memory collector.
function run_tmux_load_avg_with_memory() {
  local mode="$1"
  local value="$2"
  local memory_call_log="${TEST_MEMORY_CALL_LOG:-}"
  shift 2

  TEST_MEMORY_MODE="${mode}" \
    TEST_MEMORY_VALUE="${value}" \
    TEST_MEMORY_CALL_LOG="${memory_call_log}" \
    PATH="${FAKE_BIN}:${PATH}" \
    "${BASH_BIN}" "${TEST_RUNNER}" "${SCRIPT}" "$@"
}

function run_tmux_load_avg() {
  run_tmux_load_avg_with_memory success 63
}

function run_tmux_load_avg_with_counted_memory() {
  TEST_MEMORY_CALL_LOG="${CALL_LOG}" run_tmux_load_avg_with_memory "$@"
}

function run_tmux_load_avg_native() {
  local ostype="$1"
  shift

  TEST_OSTYPE="${ostype}" \
    PATH="${FAKE_BIN}:${PATH}" \
    "${BASH_BIN}" "${TEST_RUNNER}" "${SCRIPT}" "$@"
}

function run_tmux_load_avg_native_fake_path_only() {
  local ostype="$1"
  shift

  TEST_OSTYPE="${ostype}" \
    PATH="${FAKE_BIN}" \
    "${BASH_BIN}" "${TEST_RUNNER}" "${SCRIPT}" "$@"
}

function linux_percent_from_fixture() {
  local fixture="$1"

  printf '%s\n' "${fixture}" \
    | "${BASH_BIN}" -c 'source "$1"; linux_memory_percent_from_meminfo' bash "${SCRIPT}"
}

function linux_percent_from_file() {
  local path="$1"

  "${BASH_BIN}" -c 'source "$1"; linux_memory_percent_from_file "$2"' bash "${SCRIPT}" "${path}"
}

function darwin_percent_from_fixture() {
  local memsize="$1"
  local fixture="$2"

  printf '%s\n' "${fixture}" \
    | "${BASH_BIN}" -c 'source "$1"; darwin_memory_percent_from_vm_stat "$2"' bash "${SCRIPT}" "${memsize}"
}

function linux_fixture() {
  printf '%s\n' \
    'MemTotal:       1000 kB' \
    'MemAvailable:   370 kB'
}

function darwin_fixture_4096() {
  cat <<'EOF'
Mach Virtual Memory Statistics: (page size of 4096 bytes)
Pages free:                              1.
Pages active:                            2.
File-backed pages:                       999999.
Anonymous pages:                         900000.
Pages purgeable:                         100000.
Pages wired down:                        200000.
Pages occupied by compressor:            48576.
Pages stored in compressor:              9999999.
EOF
}

function darwin_fixture_16384() {
  cat <<'EOF'
Mach Virtual Memory Statistics: (page size of 16384 bytes)
Anonymous pages:                         147572.
Pages purgeable:                         1074.
Pages wired down:                        166600.
Pages occupied by compressor:            98634.
Pages stored in compressor:              768503.
EOF
}

function test_linux_wording_yields_first_load_figure_and_memory() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 20.71, 24.19, 24.33'

  assert_equals " (20.71/63%)" "$(run_tmux_load_avg)"
}

function test_macos_wording_yields_first_load_figure_and_memory() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 3.36 3.26 2.94'

  assert_equals " (3.36/63%)" "$(run_tmux_load_avg)"
}

function test_comma_decimal_separator_is_normalized() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 20,71, 24,19, 24,33'

  assert_equals " (20.71/63%)" "$(run_tmux_load_avg)"
}

function test_success_has_no_trailing_newline() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 20.71, 24.19, 24.33'

  assert_equals "12" "$(run_tmux_load_avg | wc -c | tr -d ' ')"
}

function test_success_reads_load_once_and_memory_once() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 20.71, 24.19, 24.33'

  run_tmux_load_avg_with_counted_memory success 63 > /dev/null

  assert_equals "1" "$(call_count uptime)"
  assert_equals "1" "$(call_count memory_percent)"
}

function test_unparseable_output_yields_empty_and_skips_memory() {
  stub_uptime 'this line has no load average in it'

  local output
  output="$(run_tmux_load_avg_with_counted_memory success 63)"

  assert_empty "${output}"
  assert_not_contains "(" "${output}"
  assert_not_contains ")" "${output}"
  assert_equals "1" "$(call_count uptime)"
  assert_equals "0" "$(call_count memory_percent)"
}

function test_failing_uptime_yields_empty_exit_zero_and_skips_memory() {
  stub_uptime_failing

  local output
  output="$(run_tmux_load_avg_with_counted_memory success 63)"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "0" "${exit_code}"
  assert_equals "1" "$(call_count uptime)"
  assert_equals "0" "$(call_count memory_percent)"
}

function test_missing_uptime_yields_empty_and_exit_zero() {
  local output
  output="$(PATH="${FAKE_BIN}" "${BASH_BIN}" "${SCRIPT}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "0" "${exit_code}"
}

function test_memory_failure_preserves_load_only_output_and_quiet_stderr() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 20.71, 24.19, 24.33'

  local stderr_file output exit_code
  stderr_file="${TEST_TMP}/stderr"
  output="$(run_tmux_load_avg_with_memory fail '' 2> "${stderr_file}")"
  exit_code=$?

  assert_equals " (20.71)" "${output}"
  assert_equals "0" "${exit_code}"
  assert_empty "$(cat "${stderr_file}")"
}

function test_unsupported_os_preserves_load_only_output() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 20.71, 24.19, 24.33'

  assert_equals " (20.71)" "$(run_tmux_load_avg_native plan9)"
}

function test_help_flag_prints_usage_exits_zero_and_skips_metrics() {
  local output
  output="$(run_tmux_load_avg_with_counted_memory success 63 --help)"
  local exit_code=$?

  assert_contains "usage:" "${output}"
  assert_contains " (<load>/<memory>%)" "${output}"
  assert_equals "0" "${exit_code}"
  assert_empty "$(calls)"
}

function test_unrecognized_argument_is_rejected_before_metrics() {
  local output
  output="$(run_tmux_load_avg_with_counted_memory success 63 --bogus 2>&1)"
  local exit_code=$?

  assert_equals "2" "${exit_code}"
  assert_contains "unrecognized argument" "${output}"
  assert_empty "$(calls)"
}

function test_linux_meminfo_calculates_total_minus_available() {
  assert_equals "63" "$(linux_percent_from_fixture "$(linux_fixture)")"
}

function test_linux_meminfo_treats_leading_zeroes_as_decimal() {
  local fixture
  fixture=$'MemTotal:       01000 kB\nMemAvailable:   00370 kB'

  assert_equals "63" "$(linux_percent_from_fixture "${fixture}")"
}

function test_linux_meminfo_uses_available_not_free_or_cache_totals() {
  local fixture
  fixture=$'MemTotal:       1000 kB\nMemFree:           1 kB\nCached:            1 kB\nMemAvailable:    900 kB'

  assert_equals "10" "$(linux_percent_from_fixture "${fixture}")"
}

function test_linux_meminfo_rounds_half_up() {
  local fixture
  fixture=$'MemTotal:       200 kB\nMemAvailable:    75 kB'

  assert_equals "63" "$(linux_percent_from_fixture "${fixture}")"
}

function test_linux_meminfo_all_available_is_zero_percent() {
  local fixture
  fixture=$'MemTotal:       1000 kB\nMemAvailable:   1000 kB'

  assert_equals "0" "$(linux_percent_from_fixture "${fixture}")"
}

function test_linux_meminfo_none_available_is_one_hundred_percent() {
  local fixture
  fixture=$'MemTotal:       1000 kB\nMemAvailable:      0 kB'

  assert_equals "100" "$(linux_percent_from_fixture "${fixture}")"
}

function test_linux_meminfo_accepts_reordered_fields_and_ignores_unrelated_fields() {
  local fixture
  fixture=$'SwapTotal:      9999 kB\nMemAvailable:    370 kB\nBuffers:           50 kB\nMemTotal:       1000 kB'

  assert_equals "63" "$(linux_percent_from_fixture "${fixture}")"
}

function test_linux_meminfo_missing_field_fails_quietly() {
  local output
  output="$(linux_percent_from_fixture 'MemTotal:       1000 kB')"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_linux_meminfo_malformed_field_fails_quietly() {
  local fixture output
  fixture=$'MemTotal:       1000 kB\nMemAvailable:   nope kB'
  output="$(linux_percent_from_fixture "${fixture}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_linux_meminfo_unreadable_input_fails_quietly() {
  local stderr_file output
  stderr_file="${TEST_TMP}/stderr"
  output="$(linux_percent_from_file "${TEST_TMP}/missing-meminfo" 2> "${stderr_file}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
  assert_empty "$(cat "${stderr_file}")"
}

function test_linux_meminfo_zero_total_fails() {
  local fixture output
  fixture=$'MemTotal:          0 kB\nMemAvailable:      0 kB'
  output="$(linux_percent_from_fixture "${fixture}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_linux_meminfo_available_greater_than_total_fails() {
  local fixture output
  fixture=$'MemTotal:       1000 kB\nMemAvailable:   1001 kB'
  output="$(linux_percent_from_fixture "${fixture}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_darwin_vm_stat_uses_counter_formula_with_4096_byte_pages() {
  assert_equals "50" "$(darwin_percent_from_fixture 8589934592 "$(darwin_fixture_4096)")"
}

function test_darwin_vm_stat_calculates_captured_mac_snapshot() {
  assert_equals "79" "$(darwin_percent_from_fixture 8589934592 "$(darwin_fixture_16384)")"
}

function test_darwin_vm_stat_accepts_old_compressor_label_and_zero_counts() {
  local fixture
  fixture=$'Mach Virtual Memory Statistics: (page size of 4096 bytes)\nAnonymous pages:                         100000.\nPages purgeable:                         0.\nPages wired down:                        100000.\nPages used by VM compressor:             0.'

  assert_equals "8" "$(darwin_percent_from_fixture 10737418240 "${fixture}")"
}

function test_darwin_vm_stat_missing_required_field_fails() {
  local fixture output
  fixture=$'Mach Virtual Memory Statistics: (page size of 4096 bytes)\nAnonymous pages:                         100000.\nPages wired down:                        100000.\nPages occupied by compressor:            0.'
  output="$(darwin_percent_from_fixture 10737418240 "${fixture}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_darwin_vm_stat_malformed_value_fails() {
  local fixture output
  fixture=$'Mach Virtual Memory Statistics: (page size of 4096 bytes)\nAnonymous pages:                         nope.\nPages purgeable:                         0.\nPages wired down:                        100000.\nPages occupied by compressor:            0.'
  output="$(darwin_percent_from_fixture 10737418240 "${fixture}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_darwin_vm_stat_bad_page_size_fails() {
  local fixture output
  fixture=$'Mach Virtual Memory Statistics: (page size of 0 bytes)\nAnonymous pages:                         100000.\nPages purgeable:                         0.\nPages wired down:                        100000.\nPages occupied by compressor:            0.'
  output="$(darwin_percent_from_fixture 10737418240 "${fixture}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_darwin_vm_stat_bad_total_fails() {
  local output
  output="$(darwin_percent_from_fixture nope "$(darwin_fixture_4096)")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_darwin_vm_stat_purgeable_greater_than_anonymous_fails() {
  local fixture output
  fixture=$'Mach Virtual Memory Statistics: (page size of 4096 bytes)\nAnonymous pages:                         10.\nPages purgeable:                         11.\nPages wired down:                        0.\nPages occupied by compressor:            0.'
  output="$(darwin_percent_from_fixture 10737418240 "${fixture}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_darwin_vm_stat_used_bytes_greater_than_physical_ram_fails() {
  local fixture output
  fixture=$'Mach Virtual Memory Statistics: (page size of 4096 bytes)\nAnonymous pages:                         3000000.\nPages purgeable:                         0.\nPages wired down:                        0.\nPages occupied by compressor:            0.'
  output="$(darwin_percent_from_fixture 10737418240 "${fixture}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_darwin_dispatch_invokes_vm_stat_and_sysctl_once() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 3.36 3.26 2.94'
  stub_vm_stat "$(darwin_fixture_4096)"
  stub_sysctl_memsize 8589934592

  assert_equals " (3.36/50%)" "$(run_tmux_load_avg_native darwin23)"
  assert_equals "1" "$(call_count uptime)"
  assert_equals "1" "$(call_count vm_stat)"
  assert_equals "1" "$(call_count 'sysctl -n hw.memsize')"
}

function test_missing_vm_stat_preserves_load_only_output_and_stderr_is_quiet() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 3.36 3.26 2.94'

  local stderr_file output
  stderr_file="${TEST_TMP}/stderr"
  output="$(run_tmux_load_avg_native_fake_path_only darwin23 2> "${stderr_file}")"
  local exit_code=$?

  assert_equals " (3.36)" "${output}"
  assert_equals "0" "${exit_code}"
  assert_empty "$(cat "${stderr_file}")"
  assert_equals "1" "$(call_count uptime)"
}

function test_failing_vm_stat_preserves_load_only_output() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 3.36 3.26 2.94'
  stub_vm_stat_failing
  stub_sysctl_memsize 8589934592

  assert_equals " (3.36)" "$(run_tmux_load_avg_native darwin23)"
  assert_equals "1" "$(call_count vm_stat)"
  assert_equals "0" "$(call_count 'sysctl -n hw.memsize')"
}

function test_failing_sysctl_preserves_load_only_output() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 3.36 3.26 2.94'
  stub_vm_stat "$(darwin_fixture_4096)"
  stub_sysctl_failing

  assert_equals " (3.36)" "$(run_tmux_load_avg_native darwin23)"
  assert_equals "1" "$(call_count vm_stat)"
  assert_equals "1" "$(call_count 'sysctl -n hw.memsize')"
}
