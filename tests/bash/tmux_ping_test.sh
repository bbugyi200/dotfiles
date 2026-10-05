#!/bin/bash

#################################################################################
# Regression tests for `tmux_ping`, the shared-state reader with a fallback   #
# pinger feeding the tmux status line.                                         #
#                                                                               #
# tmux's status-right runs this every `status-interval` (2s), so it must       #
# never error or hang: a missing or invalid state file, a busy lock, a         #
# missing `flock`, or a failing `ping` must degrade quietly rather than       #
# breaking the status line.                                                   #
#                                                                               #
# `date`, `ping`, and `flock` are stubbed on a hermetic PATH (plus symlinks   #
# to the real `basename`, `cat`, `mkdir`, `mv`, and `rm` for usage output     #
# and atomic state writes). A second stub dir without `flock` covers hosts   #
# where `flock` is not installed. HOME points at a temp dir so the real      #
# state file is never touched. A runner sources the script and overrides     #
# OSTYPE, so composition tests never depend on the host platform. Pure       #
# helpers are also tested directly.                                          #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_tmux_ping"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  FAKE_NOFLOCK_BIN="${TEST_TMP}/bin-noflock"
  BASH_BIN="$(command -v bash)"
  CALL_LOG="${TEST_TMP}/calls.log"
  TEST_RUNNER="${TEST_TMP}/run_tmux_ping"
  TEST_HOME="${TEST_TMP}/home"

  export CALL_LOG TEST_HOME

  mkdir -p "${FAKE_BIN}" "${FAKE_NOFLOCK_BIN}" "${TEST_HOME}"

  local util
  for util in basename cat mkdir mv rm; do
    ln -s "$(command -v "${util}")" "${FAKE_BIN}/${util}"
    ln -s "$(command -v "${util}")" "${FAKE_NOFLOCK_BIN}/${util}"
  done

  cat >"${FAKE_BIN}/date" <<'EOF'
#!/bin/bash
printf 'date %s\n' "$*" >>"${CALL_LOG}"
printf '%s' "${TEST_NOW}"
EOF

  cat >"${FAKE_BIN}/ping" <<'EOF'
#!/bin/bash
printf 'ping %s\n' "$*" >>"${CALL_LOG}"
exit "${PING_EXIT:-0}"
EOF

  cat >"${FAKE_BIN}/flock" <<'EOF'
#!/bin/bash
printf 'flock %s\n' "$*" >>"${CALL_LOG}"
exit "${FLOCK_EXIT:-0}"
EOF

  cp "${FAKE_BIN}/date" "${FAKE_NOFLOCK_BIN}/date"
  cp "${FAKE_BIN}/ping" "${FAKE_NOFLOCK_BIN}/ping"

  chmod +x "${FAKE_BIN}/date" "${FAKE_BIN}/ping" "${FAKE_BIN}/flock" \
    "${FAKE_NOFLOCK_BIN}/date" "${FAKE_NOFLOCK_BIN}/ping"

  cat >"${TEST_RUNNER}" <<'EOF'
#!/bin/bash
script="$1"
shift

source "${script}"

if [[ -n "${TEST_OSTYPE:-}" ]]; then
  OSTYPE="${TEST_OSTYPE}"
fi

HOME="${TEST_HOME}"

run "$@"
EOF
  chmod +x "${TEST_RUNNER}"

  export TEST_NOW=1759680010
  export TEST_OSTYPE='darwin23'
  export PING_EXIT=0
  export FLOCK_EXIT=0
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function state_file() {
  printf '%s' "${TEST_HOME}/tmp/tmux_ping_state"
}

function write_state() {
  mkdir -p "${TEST_HOME}/tmp"
  printf '%s\n' "$1" >"$(state_file)"
}

function read_state() {
  cat "$(state_file)"
}

function calls() {
  if [[ -f "${CALL_LOG}" ]]; then
    cat "${CALL_LOG}"
  fi
}

function call_count() {
  local name="$1"

  if [[ -f "${CALL_LOG}" ]]; then
    grep -F -c "${name}" "${CALL_LOG}" || true
  else
    printf '0'
  fi
}

function run_tmux_ping() {
  PATH="${FAKE_BIN}" \
    "${BASH_BIN}" "${TEST_RUNNER}" "${SCRIPT}" "$@"
}

function run_tmux_ping_noflock() {
  PATH="${FAKE_NOFLOCK_BIN}" \
    "${BASH_BIN}" "${TEST_RUNNER}" "${SCRIPT}" "$@"
}

function parse_state_exit() {
  "${BASH_BIN}" -c 'source "$1"; parse_state_line "$2" >/dev/null 2>&1' \
    bash "${SCRIPT}" "$1"
}

function parse_state_fields() {
  "${BASH_BIN}" -c '
    source "$1"
    parse_state_line "$2" || exit 1
    printf "[%s][%s][%s][%s]" \
      "${STATE_HEARTBEAT}" "${STATE_PRODUCER}" "${STATE_SAMPLED}" "${STATE_RESULTS}"
  ' bash "${SCRIPT}" "$1"
}

function classify_of() {
  "${BASH_BIN}" -c 'source "$1"; classify "$2" "$3" "$4"; printf "%s" "${REPLY}"' \
    bash "${SCRIPT}" "$1" "$2" "$3"
}

function append_of() {
  "${BASH_BIN}" -c 'source "$1"; window_append "$2" "$3" "$4" "$5"; printf "%s" "${REPLY}"' \
    bash "${SCRIPT}" "$1" "$2" "$3" "$4"
}

function summarize_of() {
  "${BASH_BIN}" -c '
    source "$1"
    summarize "$2"
    printf "%s/%s/%s/%s" \
      "${SUM_SUCCESSES}" "${SUM_TOTAL}" "${SUM_TRAILING_FAILURES}" "${SUM_NEWEST_OK}"
  ' bash "${SCRIPT}" "$1"
}

function render_of() {
  "${BASH_BIN}" -c 'source "$1"; render_state "$2" "$3" "$4"' \
    bash "${SCRIPT}" "$1" "$2" "$3"
}

# Assert the script's stdout is exactly the expected markup: no trailing
# newline, so the byte count must match the expected string length.
function assert_exact_output() {
  local expected="$1"
  local out_file="$2"

  assert_equals "${expected}" "$(cat "${out_file}")"
  assert_equals \
    "$(printf '%s' "${expected}" | wc -c | tr -d ' ')" \
    "$(wc -c <"${out_file}" | tr -d ' ')"
}

################################################################################
# Contract fixtures and state parsing
################################################################################

function test_contract_fixtures_parse_as_valid() {
  local fixture exit_code
  for fixture in \
    '1759680002 hammerspoon 1759680002 11111111111111111111' \
    '1759680010 hammerspoon 1759680002 11111111111111111111' \
    '1759680004 tmux 1759680004 0111' \
    '1759680000 hammerspoon 0 -'; do
    exit_code=0
    parse_state_exit "${fixture}" >/dev/null 2>&1 || exit_code=$?
    assert_equals "0" "${exit_code}"
  done
}

function test_empty_results_dash_parses_to_empty_window() {
  assert_equals \
    '[1759680000][hammerspoon][0][]' \
    "$(parse_state_fields '1759680000 hammerspoon 0 -')"
}

function test_invalid_forms_are_rejected() {
  local bad exit_code
  for bad in \
    '' \
    '1759680002 hammerspoon 1759680002' \
    '1759680002 hammerspoon 1759680002 11 extra' \
    '1759680002 aqua 1759680002 11' \
    'abc hammerspoon 1759680002 11' \
    '1759680002 hammerspoon xyz 11' \
    '1759680002 hammerspoon 1759680002 111111111111111111111' \
    '1759680002 hammerspoon 1759680002 1121' \
    '1759680002 hammerspoon 1759680002 ' \
    '1759680002  hammerspoon 1759680002 11' \
    ' 1759680002 hammerspoon 1759680002 11'; do
    exit_code=0
    parse_state_exit "${bad}" >/dev/null 2>&1 || exit_code=$?
    assert_equals "1" "${exit_code}"
  done
}

################################################################################
# Window append, summarize, classify
################################################################################

function test_append_to_empty_window_starts_fresh() {
  assert_equals "1" "$(append_of '' 1 "${TEST_NOW}" 0)"
  assert_equals "0" "$(append_of '' 0 "${TEST_NOW}" 0)"
}

function test_append_after_long_gap_resets_window() {
  assert_equals "1" "$(append_of '1111' 1 "${TEST_NOW}" "$((TEST_NOW - 41))")"
}

function test_append_at_exactly_window_seconds_appends() {
  assert_equals "11111" "$(append_of '1111' 1 "${TEST_NOW}" "$((TEST_NOW - 40))")"
}

function test_append_trims_to_twenty_samples() {
  assert_equals \
    '11111111111111111111' \
    "$(append_of '01111111111111111111' 1 "${TEST_NOW}" "$((TEST_NOW - 5))")"
}

function test_summarize_mixed_window() {
  assert_equals '3/5/1/0' "$(summarize_of '10110')"
  assert_equals '1/4/3/0' "$(summarize_of '1000')"
  assert_equals '4/4/0/1' "$(summarize_of '1111')"
}

function test_classify_tier_boundaries() {
  local now="${TEST_NOW}"
  local twenty='11111111111111111111'

  assert_equals 'online' "$(classify_of "${twenty}" "${now}" "${now}")"
  assert_equals 'online' "$(classify_of "${twenty}" "$((now - 6))" "${now}")"
  assert_equals 'stale' "$(classify_of "${twenty}" "$((now - 7))" "${now}")"
  assert_equals 'stale' "$(classify_of '' 0 "${now}")"
  assert_equals 'offline' "$(classify_of '11111111111111111000' "${now}" "${now}")"
  assert_equals 'down' "$(classify_of '11111111111111111110' "${now}" "${now}")"
  assert_equals 'down' "$(classify_of '11111111111111111100' "${now}" "${now}")"
  assert_equals 'lossy' "$(classify_of '00011111111111111111' "${now}" "${now}")"
  assert_equals 'online' "$(classify_of '00111111111111111111' "${now}" "${now}")"
}

################################################################################
# Reader path and fallback pinger
################################################################################

function test_non_darwin_prints_nothing_and_forks_nothing() {
  export TEST_OSTYPE='linux-gnu'

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"
  assert_equals "0" "$(wc -c <"${out}" | tr -d ' ')"
  assert_empty "$(calls)"
  local unexpected=''
  if [[ -e "$(state_file)" ]]; then
    unexpected="state file must not exist on non-darwin hosts: $(state_file)"
  fi
  assert_empty "${unexpected}"
}

function test_help_flag_describes_shared_state_role() {
  local out
  out="$(run_tmux_ping --help)"
  assert_equals "0" "$?"
  assert_contains "usage:" "${out}"
  assert_contains "shared" "${out}"
  assert_contains "fallback" "${out}"
  assert_empty "$(calls)"
}

function test_unrecognized_argument_is_rejected() {
  local out exit_code
  out="$(run_tmux_ping --bogus 2>&1)"
  exit_code=$?
  assert_equals "2" "${exit_code}"
  assert_contains "unrecognized argument" "${out}"
  assert_empty "$(calls)"
}

function test_fresh_hammerspoon_heartbeat_renders_without_ping_or_flock() {
  write_state "$((TEST_NOW - 5)) hammerspoon $((TEST_NOW - 5)) 11"
  local before
  before="$(read_state)"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_exact_output '#[fg=green]✓#[default] 2/2 | ' "${out}"
  assert_equals "0" "$(call_count 'ping ')"
  assert_equals "0" "$(call_count 'flock ')"
  assert_equals "1" "$(call_count 'date ')"
  assert_equals "${before}" "$(read_state)"
}

function test_hammerspoon_heartbeat_at_handoff_age_pings_and_claims_tmux() {
  write_state "$((TEST_NOW - 6)) hammerspoon $((TEST_NOW - 6)) 11"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_equals "1" "$(call_count 'ping ')"
  assert_contains "ping -n -q -c 1 -t 1 8.8.8.8" "$(calls)"
  assert_exact_output '#[fg=green]✓#[default] 3/3 | ' "${out}"
  assert_equals "${TEST_NOW} tmux ${TEST_NOW} 111" "$(read_state)"
}

function test_tmux_sample_under_interval_skips_ping() {
  write_state "$((TEST_NOW - 1)) tmux $((TEST_NOW - 1)) 11"
  local before
  before="$(read_state)"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_exact_output '#[fg=green]✓#[default] 2/2 | ' "${out}"
  assert_equals "0" "$(call_count 'ping ')"
  assert_equals "1" "$(call_count 'flock ')"
  assert_equals "${before}" "$(read_state)"
}

function test_tmux_sample_at_interval_pings() {
  write_state "$((TEST_NOW - 2)) tmux $((TEST_NOW - 2)) 11"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_equals "1" "$(call_count 'ping ')"
  assert_exact_output '#[fg=green]✓#[default] 3/3 | ' "${out}"
  assert_equals "${TEST_NOW} tmux ${TEST_NOW} 111" "$(read_state)"
}

function test_missing_state_pings_into_fresh_window() {
  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_equals "1" "$(call_count 'ping ')"
  assert_exact_output '#[fg=green]✓#[default] 1/1 | ' "${out}"
  assert_equals "${TEST_NOW} tmux ${TEST_NOW} 1" "$(read_state)"
}

function test_empty_state_pings_into_fresh_window() {
  write_state ''

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_equals "1" "$(call_count 'ping ')"
  assert_exact_output '#[fg=green]✓#[default] 1/1 | ' "${out}"
  assert_equals "${TEST_NOW} tmux ${TEST_NOW} 1" "$(read_state)"
}

function test_invalid_states_ping_into_fresh_windows() {
  local bad
  for bad in \
    '1759680002 aqua 1759680002 11' \
    '1759680002 hammerspoon 1759680002 111111111111111111111' \
    '1759680002 hammerspoon 1759680002'; do
    rm -f "$(state_file)"
    write_state "${bad}"

    local out="${TEST_TMP}/out"
    run_tmux_ping >"${out}"
    assert_equals "0" "$?"
    assert_exact_output '#[fg=green]✓#[default] 1/1 | ' "${out}"
    assert_equals "${TEST_NOW} tmux ${TEST_NOW} 1" "$(read_state)"
  done
  assert_equals "3" "$(call_count 'ping ')"
}

function test_failing_ping_appends_miss() {
  export PING_EXIT=2
  write_state "$((TEST_NOW - 5)) tmux $((TEST_NOW - 5)) 11"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_equals "1" "$(call_count 'ping ')"
  assert_exact_output '#[fg=red]✗#[default] 2/3 | ' "${out}"
  assert_equals "${TEST_NOW} tmux ${TEST_NOW} 110" "$(read_state)"
}

function test_busy_lock_renders_without_pinging() {
  export FLOCK_EXIT=1
  write_state "$((TEST_NOW - 5)) tmux $((TEST_NOW - 5)) 11"
  local before
  before="$(read_state)"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_equals "1" "$(call_count 'flock ')"
  assert_equals "0" "$(call_count 'ping ')"
  assert_exact_output '#[fg=green]✓#[default] 2/2 | ' "${out}"
  assert_equals "${before}" "$(read_state)"
}

function test_missing_flock_pings_unlocked() {
  local out="${TEST_TMP}/out"
  run_tmux_ping_noflock >"${out}"
  assert_equals "0" "$?"

  assert_equals "1" "$(call_count 'ping ')"
  assert_exact_output '#[fg=green]✓#[default] 1/1 | ' "${out}"
  assert_equals "${TEST_NOW} tmux ${TEST_NOW} 1" "$(read_state)"
}

function test_long_gap_resets_window_end_to_end() {
  write_state "$((TEST_NOW - 41)) tmux $((TEST_NOW - 41)) 1111"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_exact_output '#[fg=green]✓#[default] 1/1 | ' "${out}"
  assert_equals "${TEST_NOW} tmux ${TEST_NOW} 1" "$(read_state)"
}

function test_full_window_drops_oldest_end_to_end() {
  write_state "$((TEST_NOW - 5)) tmux $((TEST_NOW - 5)) 01111111111111111111"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_exact_output '#[fg=green]✓#[default] 20/20 | ' "${out}"
  assert_equals "${TEST_NOW} tmux ${TEST_NOW} 11111111111111111111" "$(read_state)"
}

################################################################################
# Exact tier output
################################################################################

function test_online_tier_output() {
  write_state "${TEST_NOW} hammerspoon ${TEST_NOW} 11111111111111111111"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_exact_output '#[fg=green]✓#[default] 20/20 | ' "${out}"
  assert_equals "0" "$(call_count 'ping ')"
}

function test_lossy_tier_output() {
  write_state "${TEST_NOW} hammerspoon ${TEST_NOW} 00011111111111111111"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_exact_output '#[fg=#ffc777]✓#[default] 17/20 | ' "${out}"
}

function test_down_tier_output() {
  write_state "${TEST_NOW} hammerspoon ${TEST_NOW} 11111111111111111110"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_exact_output '#[fg=red]✗#[default] 19/20 | ' "${out}"
}

function test_offline_tier_output() {
  write_state "${TEST_NOW} hammerspoon ${TEST_NOW} 11111111111111111000"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_exact_output '#[fg=white,bg=red,bold] ✗ 17/20 #[default] | ' "${out}"
}

function test_stale_tier_output_for_paused_hammerspoon() {
  write_state "${TEST_NOW} hammerspoon $((TEST_NOW - 8)) 11111111111111111111"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_exact_output '#[fg=#828bb8]◌ 20/20#[default] | ' "${out}"
  assert_equals "0" "$(call_count 'ping ')"
}

function test_stale_tier_output_for_empty_window() {
  write_state "${TEST_NOW} hammerspoon 0 -"

  local out="${TEST_TMP}/out"
  run_tmux_ping >"${out}"
  assert_equals "0" "$?"

  assert_exact_output '#[fg=#828bb8]◌ –#[default] | ' "${out}"
  assert_equals "0" "$(call_count 'ping ')"
}

function test_render_helper_exact_strings() {
  local now="${TEST_NOW}"

  assert_equals \
    '#[fg=green]✓#[default] 20/20 | ' \
    "$(render_of '11111111111111111111' "${now}" "${now}")"
  assert_equals \
    '#[fg=#ffc777]✓#[default] 17/20 | ' \
    "$(render_of '00011111111111111111' "${now}" "${now}")"
  assert_equals \
    '#[fg=red]✗#[default] 19/20 | ' \
    "$(render_of '11111111111111111110' "${now}" "${now}")"
  assert_equals \
    '#[fg=white,bg=red,bold] ✗ 0/3 #[default] | ' \
    "$(render_of '000' "${now}" "${now}")"
  assert_equals \
    '#[fg=#828bb8]◌ –#[default] | ' \
    "$(render_of '' 0 "${now}")"

  local rendered_file="${TEST_TMP}/rendered"
  render_of '11111111111111111111' "${now}" "${now}" >"${rendered_file}"
  assert_exact_output '#[fg=green]✓#[default] 20/20 | ' "${rendered_file}"
}

################################################################################
# Written state contract
################################################################################

function test_written_state_matches_contract_and_leaves_no_temp_files() {
  run_tmux_ping >/dev/null
  assert_equals "0" "$?"

  local line
  line="$(read_state)"
  local pattern='^[0-9]+ (hammerspoon|tmux) [0-9]+ ([01]{1,20}|-)$'
  local mismatch=''
  if [[ ! "${line}" =~ ${pattern} ]]; then
    mismatch="written state breaks the contract: '${line}'"
  fi
  assert_empty "${mismatch}"

  # Command substitution strips trailing newlines, so an empty result
  # proves the file ends in exactly one LF byte.
  assert_empty "$(tail -c 1 "$(state_file)")"

  local leftovers=''
  local entry
  for entry in "${TEST_HOME}/tmp"/*; do
    case "$(basename "${entry}")" in
    tmux_ping_state | tmux_ping_state.lock) ;;
    *)
      leftovers="${leftovers} ${entry}"
      ;;
    esac
  done
  assert_empty "${leftovers}"
}
