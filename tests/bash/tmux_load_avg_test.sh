#!/bin/bash

#################################################################################
# Regression tests for the `tmux_load_avg` tmux status-line helper.             #
#                                                                               #
# tmux's status-right runs this every `status-interval` (2s), so it must       #
# never error or hang: a missing/failing `uptime`, output that does not parse, #
# or a CPU count / memory reading that cannot be collected must degrade        #
# quietly rather than breaking the status line.                                 #
#                                                                               #
# `uptime`, `vm_stat`, and `sysctl` are stubbed where the full helper runs.     #
# The Linux CPU count and memory come from builtin reads (`/sys`, `/proc`),    #
# not forked commands, so composition tests override the internal collector   #
# functions (`linux_cpu_count`, `linux_memory_percent`) instead of stubbing a  #
# PATH entry. Parsers and the pure formatter are also tested directly so the  #
# suite never depends on the host's live load, CPU count, or RAM by accident. #
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

if [[ -n "${TEST_LINUX_CPU_MODE:-}" ]]; then
  function linux_cpu_count() {
    if [[ -n "${TEST_LINUX_CPU_CALL_LOG:-}" ]]; then
      printf 'linux_cpu_count\n' >> "${TEST_LINUX_CPU_CALL_LOG}"
    fi

    case "${TEST_LINUX_CPU_MODE}" in
    success)
      printf '%s' "${TEST_LINUX_CPU_VALUE}"
      ;;
    fail)
      return 1
      ;;
    esac
  }
fi

if [[ -n "${TEST_LINUX_MEM_MODE:-}" ]]; then
  function linux_memory_percent() {
    if [[ -n "${TEST_LINUX_MEM_CALL_LOG:-}" ]]; then
      printf 'linux_memory_percent\n' >> "${TEST_LINUX_MEM_CALL_LOG}"
    fi

    case "${TEST_LINUX_MEM_MODE}" in
    success)
      printf '%s' "${TEST_LINUX_MEM_VALUE}"
      ;;
    fail)
      return 1
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
  local log="${2:-${CALL_LOG}}"

  if [[ -f "${log}" ]]; then
    grep -F -x -c "${name}" "${log}" || true
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

# Stub the single combined `sysctl -n hw.logicalcpu hw.memsize` call.
function stub_sysctl() {
  export SYSCTL_CPUS="$1"
  export SYSCTL_MEMSIZE="$2"
  export SYSCTL_FAIL=0

  cat > "${FAKE_BIN}/sysctl" <<'EOF'
#!/bin/bash
printf 'sysctl %s\n' "$*" >> "${CALL_LOG}"
if [[ "${SYSCTL_FAIL:-0}" == 1 ]]; then
  exit 1
fi
if [[ "$*" != "-n hw.logicalcpu hw.memsize" ]]; then
  exit 64
fi
printf '%s\n%s\n' "${SYSCTL_CPUS}" "${SYSCTL_MEMSIZE}"
EOF
  chmod +x "${FAKE_BIN}/sysctl"
}

function stub_sysctl_failing() {
  stub_sysctl '' ''
  export SYSCTL_FAIL=1
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

# Run the Linux path with stubbed internal collectors (CPU count, memory),
# since those come from builtin `/sys` / `/proc` reads rather than forked
# commands and cannot be intercepted via PATH.
function run_tmux_load_avg_linux() {
  local cpu_mode="$1" cpu_value="$2" mem_mode="$3" mem_value="$4"
  shift 4

  TEST_OSTYPE='linux-gnu' \
    TEST_LINUX_CPU_MODE="${cpu_mode}" \
    TEST_LINUX_CPU_VALUE="${cpu_value}" \
    TEST_LINUX_CPU_CALL_LOG="${TEST_LINUX_CPU_CALL_LOG:-}" \
    TEST_LINUX_MEM_MODE="${mem_mode}" \
    TEST_LINUX_MEM_VALUE="${mem_value}" \
    TEST_LINUX_MEM_CALL_LOG="${TEST_LINUX_MEM_CALL_LOG:-}" \
    PATH="${FAKE_BIN}:${PATH}" \
    "${BASH_BIN}" "${TEST_RUNNER}" "${SCRIPT}" "$@"
}

function render_segment_of() {
  "${BASH_BIN}" -c 'source "$1"; render_segment "$2" "$3"' bash "${SCRIPT}" "$1" "$2"
}

function level_style_of() {
  "${BASH_BIN}" -c 'source "$1"; level_style "$2" "$3" "$4"; printf "%s" "${REPLY}"' \
    bash "${SCRIPT}" "$1" "$2" "$3"
}

function load_to_hundredths_of() {
  "${BASH_BIN}" -c 'source "$1"; load_to_hundredths "$2" || exit 1; printf "%s" "${REPLY}"' \
    bash "${SCRIPT}" "$1"
}

function cpu_percent_from_load_of() {
  "${BASH_BIN}" -c 'source "$1"; cpu_percent_from_load "$2" "$3"' bash "${SCRIPT}" "$1" "$2"
}

function cpu_percent_from_uptime_line() {
  local uptime_line="$1" cpus="$2"

  "${BASH_BIN}" -c '
    source "$1"
    load="$(parse_uptime_load "$2")" || exit 1
    cpu_percent_from_load "${load}" "$3"
  ' bash "${SCRIPT}" "${uptime_line}" "${cpus}"
}

function linux_cpu_count_from_online_of() {
  "${BASH_BIN}" -c 'source "$1"; linux_cpu_count_from_online "$2"' bash "${SCRIPT}" "$1"
}

function linux_cpu_count_from_file_of() {
  local path="$1"

  "${BASH_BIN}" -c 'source "$1"; linux_cpu_count_from_file "$2"' bash "${SCRIPT}" "${path}"
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

function strip_markup() {
  local text="$1"

  while [[ "${text}" == *'#['*']'* ]]; do
    local before="${text%%#[*}"
    local rest="${text#*#[}"
    rest="${rest#*]}"
    text="${before}${rest}"
  done

  printf '%s' "${text}"
}

################################################################################
# Formatter exact strings
################################################################################

function test_render_segment_both_metrics_healthy() {
  assert_equals \
    ' #[fg=#828bb8]cpu #[default]40% #[fg=#828bb8]mem #[default]65%#[default]' \
    "$(render_segment_of 40 65)"
}

function test_render_segment_cpu_only() {
  assert_equals \
    ' #[fg=#828bb8]cpu #[default]40%#[default]' \
    "$(render_segment_of 40 '')"
}

function test_render_segment_mem_only() {
  assert_equals \
    ' #[fg=#828bb8]mem #[default]65%#[default]' \
    "$(render_segment_of '' 65)"
}

function test_render_segment_neither_is_empty() {
  assert_empty "$(render_segment_of '' '')"
}

function test_render_segment_has_no_trailing_newline() {
  local expected=' #[fg=#828bb8]cpu #[default]40% #[fg=#828bb8]mem #[default]65%#[default]'

  assert_equals "${#expected}" "$(render_segment_of 40 65 | wc -c | tr -d ' ')"
  assert_equals "0" "$(render_segment_of '' '' | wc -c | tr -d ' ')"
}

function test_render_segment_visible_text_strips_to_plain_words() {
  assert_equals ' cpu 40% mem 65%' "$(strip_markup "$(render_segment_of 40 65)")"
}

function test_render_segment_percent_sign_is_always_followed_by_markup_or_end() {
  local output
  output="$(render_segment_of 87 65)"

  assert_not_contains '%%' "${output}"

  local after_first
  after_first="${output#*87%}"
  assert_equals ' #[fg=#828bb8]mem #[default]65%#[default]' "${after_first}"

  local after_second
  after_second="${output#*65%}"
  assert_equals '#[default]' "${after_second}"
}

################################################################################
# Threshold boundaries
################################################################################

function test_cpu_threshold_boundaries() {
  assert_equals "default" "$(level_style_of 0 80 100)"
  assert_equals "default" "$(level_style_of 79 80 100)"
  assert_equals "fg=#ffc777" "$(level_style_of 80 80 100)"
  assert_equals "fg=#ffc777" "$(level_style_of 99 80 100)"
  assert_equals "fg=#ff757f" "$(level_style_of 100 80 100)"
  assert_equals "fg=#ff757f" "$(level_style_of 250 80 100)"
}

function test_mem_threshold_boundaries() {
  assert_equals "default" "$(level_style_of 84 85 95)"
  assert_equals "fg=#ffc777" "$(level_style_of 85 85 95)"
  assert_equals "fg=#ffc777" "$(level_style_of 94 85 95)"
  assert_equals "fg=#ff757f" "$(level_style_of 95 85 95)"
  assert_equals "fg=#ff757f" "$(level_style_of 100 85 95)"
}

function test_render_segment_mixed_healthy_cpu_and_critical_mem() {
  assert_equals \
    ' #[fg=#828bb8]cpu #[default]40% #[fg=#828bb8]mem #[fg=#ff757f]96%#[default]' \
    "$(render_segment_of 40 96)"
}

################################################################################
# Load to CPU percent
################################################################################

function test_load_2556_on_64_cpus_gives_40() {
  assert_equals "40" "$(cpu_percent_from_load_of 25.56 64)"
}

function test_load_420_on_8_cpus_gives_53() {
  assert_equals "53" "$(cpu_percent_from_load_of 4.20 8)"
}

function test_comma_decimal_load_is_accepted_via_uptime_parsing() {
  assert_equals "32" "$(cpu_percent_from_uptime_line 'load average: 20,71' 64)"
}

function test_integer_only_load_pads_to_two_fraction_digits() {
  assert_equals "300" "$(load_to_hundredths_of 3)"
}

function test_one_digit_fraction_is_right_padded() {
  assert_equals "50" "$(load_to_hundredths_of 0.5)"
}

function test_three_digit_fraction_is_truncated_not_rounded() {
  assert_equals "123" "$(load_to_hundredths_of 1.234)"
}

function test_leading_zeroes_are_not_read_as_octal() {
  assert_equals "809" "$(load_to_hundredths_of 08.09)"
}

function test_half_up_rounding_of_small_load() {
  assert_equals "1" "$(cpu_percent_from_load_of 0.01 2)"
}

function test_cpu_percent_can_exceed_one_hundred() {
  assert_equals "200" "$(cpu_percent_from_load_of 128.00 64)"
}

function test_zero_cpu_count_is_unavailable() {
  local output
  output="$(cpu_percent_from_load_of 25.56 0)"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_invalid_cpu_count_is_unavailable() {
  local output
  output="$(cpu_percent_from_load_of 25.56 nope)"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_overlong_integer_part_is_unavailable() {
  local output
  output="$(load_to_hundredths_of 1234567.5)"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

################################################################################
# Linux CPU list parser
################################################################################

function test_linux_cpu_list_full_range() {
  assert_equals "64" "$(linux_cpu_count_from_online_of '0-63')"
}

function test_linux_cpu_list_single_cpu() {
  assert_equals "1" "$(linux_cpu_count_from_online_of '0')"
}

function test_linux_cpu_list_mixed_ranges() {
  assert_equals "8" "$(linux_cpu_count_from_online_of '0-3,8-11')"
}

function test_linux_cpu_list_singles_and_range() {
  assert_equals "4" "$(linux_cpu_count_from_online_of '0,2,4-5')"
}

function test_linux_cpu_list_empty_input_fails() {
  local output
  output="$(linux_cpu_count_from_online_of '')"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_linux_cpu_list_reversed_range_fails() {
  local output
  output="$(linux_cpu_count_from_online_of '3-1')"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_linux_cpu_list_non_digits_fail() {
  local output
  output="$(linux_cpu_count_from_online_of 'a-b')"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_linux_cpu_list_dangling_hyphen_fails() {
  local output
  output="$(linux_cpu_count_from_online_of '0-')"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_linux_cpu_list_dangling_comma_fails() {
  local output
  output="$(linux_cpu_count_from_online_of '0,,1')"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
}

function test_linux_cpu_list_unreadable_file_fails_quietly() {
  local stderr_file output
  stderr_file="${TEST_TMP}/stderr"
  output="$(linux_cpu_count_from_file_of "${TEST_TMP}/missing-online" 2> "${stderr_file}")"
  local exit_code=$?

  assert_empty "${output}"
  assert_equals "1" "${exit_code}"
  assert_empty "$(cat "${stderr_file}")"
}

################################################################################
# Darwin shared sysctl
################################################################################

function test_darwin_dispatch_invokes_sysctl_and_vm_stat_once_each() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 4.20 3.26 2.94'
  stub_vm_stat "$(darwin_fixture_16384)"
  stub_sysctl 8 8589934592

  assert_equals \
    ' #[fg=#828bb8]cpu #[default]53% #[fg=#828bb8]mem #[default]79%#[default]' \
    "$(run_tmux_load_avg_native darwin23)"
  assert_equals "1" "$(call_count uptime)"
  assert_equals "1" "$(call_count vm_stat)"
  assert_equals "1" "$(call_count 'sysctl -n hw.logicalcpu hw.memsize')"
}

function test_darwin_sysctl_failure_yields_empty_and_skips_vm_stat() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 4.20 3.26 2.94'
  stub_sysctl_failing

  local stderr_file output exit_code
  stderr_file="${TEST_TMP}/stderr"
  output="$(run_tmux_load_avg_native darwin23 2> "${stderr_file}")"
  exit_code=$?

  assert_empty "${output}"
  assert_equals "0" "${exit_code}"
  assert_empty "$(cat "${stderr_file}")"
  assert_equals "0" "$(call_count vm_stat)"
}

function test_darwin_invalid_cpu_line_renders_mem_only() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 4.20 3.26 2.94'
  stub_vm_stat "$(darwin_fixture_16384)"
  stub_sysctl nope 8589934592

  assert_equals \
    ' #[fg=#828bb8]mem #[default]79%#[default]' \
    "$(run_tmux_load_avg_native darwin23)"
}

function test_darwin_zero_cpu_line_renders_mem_only() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 4.20 3.26 2.94'
  stub_vm_stat "$(darwin_fixture_16384)"
  stub_sysctl 0 8589934592

  assert_equals \
    ' #[fg=#828bb8]mem #[default]79%#[default]' \
    "$(run_tmux_load_avg_native darwin23)"
}

function test_darwin_invalid_memsize_renders_cpu_only_with_no_vm_stat_call() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 4.20 3.26 2.94'
  stub_vm_stat "$(darwin_fixture_16384)"
  stub_sysctl 8 nope

  assert_equals \
    ' #[fg=#828bb8]cpu #[default]53%#[default]' \
    "$(run_tmux_load_avg_native darwin23)"
  assert_equals "0" "$(call_count vm_stat)"
}

function test_darwin_zero_memsize_renders_cpu_only_with_no_vm_stat_call() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 4.20 3.26 2.94'
  stub_vm_stat "$(darwin_fixture_16384)"
  stub_sysctl 8 0

  assert_equals \
    ' #[fg=#828bb8]cpu #[default]53%#[default]' \
    "$(run_tmux_load_avg_native darwin23)"
  assert_equals "0" "$(call_count vm_stat)"
}

function test_darwin_missing_vm_stat_renders_cpu_only() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 4.20 3.26 2.94'
  stub_sysctl 8 8589934592

  local stderr_file output exit_code
  stderr_file="${TEST_TMP}/stderr"
  output="$(run_tmux_load_avg_native_fake_path_only darwin23 2> "${stderr_file}")"
  exit_code=$?

  assert_equals ' #[fg=#828bb8]cpu #[default]53%#[default]' "${output}"
  assert_equals "0" "${exit_code}"
  assert_empty "$(cat "${stderr_file}")"
}

function test_darwin_failing_vm_stat_renders_cpu_only() {
  stub_uptime '11:03  up 5 days, 23:50, 4 users, load averages: 4.20 3.26 2.94'
  stub_vm_stat_failing
  stub_sysctl 8 8589934592

  assert_equals ' #[fg=#828bb8]cpu #[default]53%#[default]' "$(run_tmux_load_avg_native darwin23)"
  assert_equals "1" "$(call_count vm_stat)"
}

function test_darwin_failing_uptime_renders_mem_only() {
  stub_uptime_failing
  stub_vm_stat "$(darwin_fixture_16384)"
  stub_sysctl 8 8589934592

  assert_equals ' #[fg=#828bb8]mem #[default]79%#[default]' "$(run_tmux_load_avg_native darwin23)"
}

################################################################################
# Composition
################################################################################

function test_linux_success_reads_uptime_once() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 25.56, 24.19, 24.33'

  assert_equals \
    ' #[fg=#828bb8]cpu #[default]40% #[fg=#828bb8]mem #[default]65%#[default]' \
    "$(run_tmux_load_avg_linux success 64 success 65)"
  assert_equals "1" "$(call_count uptime)"
}

function test_linux_load_failure_still_renders_mem_and_exits_zero_with_quiet_stderr() {
  stub_uptime_failing

  local stderr_file output exit_code
  stderr_file="${TEST_TMP}/stderr"
  output="$(run_tmux_load_avg_linux success 64 success 65 2> "${stderr_file}")"
  exit_code=$?

  assert_equals ' #[fg=#828bb8]mem #[default]65%#[default]' "${output}"
  assert_equals "0" "${exit_code}"
  assert_empty "$(cat "${stderr_file}")"
}

function test_linux_missing_cpu_count_renders_mem_only() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 25.56, 24.19, 24.33'

  assert_equals ' #[fg=#828bb8]mem #[default]65%#[default]' "$(run_tmux_load_avg_linux fail '' success 65)"
}

function test_linux_memory_failure_renders_cpu_only() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 25.56, 24.19, 24.33'

  assert_equals ' #[fg=#828bb8]cpu #[default]40%#[default]' "$(run_tmux_load_avg_linux success 64 fail '')"
}

function test_unsupported_ostype_renders_nothing_and_logs_no_calls() {
  stub_uptime '11:01:57 up 4 days, 18:56,  3 users,  load average: 25.56, 24.19, 24.33'

  local output
  output="$(run_tmux_load_avg_native plan9)"

  assert_empty "${output}"
  assert_empty "$(calls)"
}

function test_help_flag_prints_usage_exits_zero_and_logs_no_calls() {
  local output
  output="$(run_tmux_load_avg_native linux-gnu --help)"
  local exit_code=$?

  assert_contains "usage:" "${output}"
  assert_contains "cpu" "${output}"
  assert_contains "mem" "${output}"
  assert_contains "unavailable" "${output}"
  assert_equals "0" "${exit_code}"
  assert_empty "$(calls)"
}

function test_unrecognized_argument_is_rejected_before_metrics() {
  local output
  output="$(run_tmux_load_avg_native linux-gnu --bogus 2>&1)"
  local exit_code=$?

  assert_equals "2" "${exit_code}"
  assert_contains "unrecognized argument" "${output}"
  assert_empty "$(calls)"
}

################################################################################
# Linux meminfo parser (unchanged formulas, still validated directly)
################################################################################

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

################################################################################
# Darwin vm_stat parser (unchanged formulas, still validated directly)
################################################################################

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
