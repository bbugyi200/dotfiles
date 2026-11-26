#!/bin/bash

#################################################################################
# Regression tests for the `tmux_battery` tmux status-line helper.              #
#                                                                               #
# tmux's status-right runs this every `status-interval` (2s), so it must       #
# never error or hang: a missing/failing `pmset`, output that does not parse,  #
# or a host with no battery must degrade quietly rather than breaking the      #
# status line.                                                                  #
#                                                                               #
# `pmset` is stubbed where the full helper runs. Parsers and the pure           #
# formatter are also tested directly so the suite never depends on the host's   #
# live battery by accident. The fixture table replays realistic `pmset`         #
# captures end to end under a stubbed PATH.                                     #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_tmux_battery"
FIXTURE="${PWD}/tests/fixtures/tmux_battery_cases.tsv"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  BASH_BIN="$(command -v bash)"
  CALL_LOG="${TEST_TMP}/calls.log"
  TEST_RUNNER="${TEST_TMP}/run_tmux_battery"

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

function stub_pmset() {
  export PMSET_OUTPUT="$1"
  export PMSET_FAIL="${2:-0}"

  cat > "${FAKE_BIN}/pmset" <<'EOF'
#!/bin/bash
printf 'pmset\n' >> "${CALL_LOG}"
if [[ "${PMSET_FAIL:-0}" == 1 ]]; then
  exit 1
fi
printf '%s' "${PMSET_OUTPUT}"
EOF
  chmod +x "${FAKE_BIN}/pmset"
}

function run_tmux_battery_native() {
  local ostype="$1"
  shift

  TEST_OSTYPE="${ostype}" \
    PATH="${FAKE_BIN}:${PATH}" \
    "${BASH_BIN}" "${TEST_RUNNER}" "${SCRIPT}" "$@"
}

function run_tmux_battery_native_fake_path_only() {
  local ostype="$1"
  shift

  TEST_OSTYPE="${ostype}" \
    PATH="${FAKE_BIN}" \
    "${BASH_BIN}" "${TEST_RUNNER}" "${SCRIPT}" "$@"
}

function render_segment_of() {
  "${BASH_BIN}" -c 'source "$1"; render_segment "$2" "$3"' bash "${SCRIPT}" "$1" "$2"
}

function battery_glyph_bytes() {
  "${BASH_BIN}" -c 'source "$1"; printf "%s" "${BATTERY_GLYPHS[$2]}"' \
    bash "${SCRIPT}" "$1" \
    | od -An -tx1 | tr -s ' ' | sed -e 's/^ //'
}

function charging_glyph_bytes() {
  "${BASH_BIN}" -c 'source "$1"; printf "%s" "${CHARGING_GLYPHS[$2]}"' \
    bash "${SCRIPT}" "$1" \
    | od -An -tx1 | tr -s ' ' | sed -e 's/^ //'
}

function const_bytes() {
  "${BASH_BIN}" -c 'source "$1"; printf "%s" "$2"' bash "${SCRIPT}" "$1" \
    | od -An -tx1 | tr -s ' ' | sed -e 's/^ //'
}

################################################################################
# Fixture table: every row runs end to end through the stub
################################################################################

function test_fixture_table_renders_exact_markup_end_to_end() {
  local line name pmset_raw expected pmset_out output exit_code failures total
  local stderr_file expected_bytes output_bytes
  failures=0
  total=0

  while IFS= read -r line || [[ -n "${line}" ]]; do
    case "${line}" in
    '#'*)
      continue
      ;;
    '')
      continue
      ;;
    esac

    IFS=$'\t' read -r name pmset_raw expected <<< "${line}"
    pmset_out="$(printf '%b' "${pmset_raw}")"
    stub_pmset "${pmset_out}"

    total=$((total + 1))
    stderr_file="${TEST_TMP}/stderr_${total}"
    output="$(run_tmux_battery_native darwin 2> "${stderr_file}")"
    exit_code=$?

    if [[ "${output}" != "${expected}" ]]; then
      printf 'row <%s>: expected <%s>, got <%s>\n' "${name}" "${expected}" "${output}" >&2
      failures=$((failures + 1))
      continue
    fi

    if [[ "${exit_code}" != '0' ]]; then
      printf 'row <%s>: exit code <%s>, want <0>\n' "${name}" "${exit_code}" >&2
      failures=$((failures + 1))
    fi

    if [[ -n "$(cat "${stderr_file}")" ]]; then
      printf 'row <%s>: stderr <%s>, want empty\n' "${name}" "$(cat "${stderr_file}")" >&2
      failures=$((failures + 1))
    fi

    expected_bytes="$(printf '%s' "${expected}" | wc -c | tr -d ' ')"
    output_bytes="$(run_tmux_battery_native darwin 2> /dev/null | wc -c | tr -d ' ')"
    if [[ "${output_bytes}" != "${expected_bytes}" ]]; then
      printf 'row <%s>: output bytes <%s>, want <%s> (trailing newline?)\n' \
        "${name}" "${output_bytes}" "${expected_bytes}" >&2
      failures=$((failures + 1))
    fi
  done < "${FIXTURE}"

  if ((total == 0)); then
    printf 'fixture table <%s> yielded no rows\n' "${FIXTURE}" >&2
    return 1
  fi

  assert_equals "0" "${failures}"
}

################################################################################
# Bucket and glyph boundaries, tested directly
################################################################################

function test_draining_bucket_boundaries_pick_level_glyphs() {
  local b0=$'\xf3\xb0\x82\x8e'
  local b10=$'\xf3\xb0\x81\xba'
  local b20=$'\xf3\xb0\x81\xbb'
  local alert=$'\xf3\xb0\x82\x83'

  assert_equals \
    " #[fg=white,bg=red,bold] ${alert} 0% #[default]" \
    "$(render_segment_of draining 0)"
  assert_equals \
    " #[fg=white,bg=red,bold] ${alert} 4% #[default]" \
    "$(render_segment_of draining 4)"
  assert_equals \
    " #[fg=white,bg=red,bold] ${alert} 5% #[default]" \
    "$(render_segment_of draining 5)"
  assert_equals \
    " #[fg=#ffc777]${b10} 14%#[default]" \
    "$(render_segment_of draining 14)"
  assert_equals \
    " #[fg=#ffc777]${b20} 15%#[default]" \
    "$(render_segment_of draining 15)"
}

function test_draining_threshold_edges_warn_only_while_draining() {
  local b10=$'\xf3\xb0\x81\xba'
  local b20=$'\xf3\xb0\x81\xbb'
  local b70=$'\xf3\xb0\x82\x80'
  local b90=$'\xf3\xb0\x82\x82'
  local b100=$'\xf3\xb0\x81\xb9'
  local alert=$'\xf3\xb0\x82\x83'

  assert_equals \
    " #[fg=#ffc777]${b20} 20%#[default]" \
    "$(render_segment_of draining 20)"
  assert_equals \
    " #[fg=#828bb8]${b20} #[default]21%#[default]" \
    "$(render_segment_of draining 21)"
  assert_equals \
    " #[fg=#ffc777]${b10} 11%#[default]" \
    "$(render_segment_of draining 11)"
  assert_equals \
    " #[fg=white,bg=red,bold] ${alert} 10% #[default]" \
    "$(render_segment_of draining 10)"
  assert_equals \
    " #[fg=#828bb8]${b70} #[default]72%#[default]" \
    "$(render_segment_of draining 72)"
  assert_equals \
    " #[fg=#828bb8]${b90} #[default]94%#[default]" \
    "$(render_segment_of draining 94)"
  assert_equals \
    " #[fg=#828bb8]${b100} #[default]95%#[default]" \
    "$(render_segment_of draining 95)"
  assert_equals \
    " #[fg=#828bb8]${b100} #[default]100%#[default]" \
    "$(render_segment_of draining 100)"
}

function test_charging_bucket_boundaries_pick_charging_glyphs() {
  local c0=$'\xf3\xb0\xa2\x9f'
  local c10=$'\xf3\xb0\xa2\x9c'
  local c20=$'\xf3\xb0\x82\x86'
  local c60=$'\xf3\xb0\x82\x89'
  local c90=$'\xf3\xb0\x82\x8b'
  local c100=$'\xf3\xb0\x82\x85'

  assert_equals \
    " #[fg=green]${c0} #[default]0%#[default]" \
    "$(render_segment_of charging 0)"
  assert_equals \
    " #[fg=green]${c0} #[default]4%#[default]" \
    "$(render_segment_of charging 4)"
  assert_equals \
    " #[fg=green]${c10} #[default]5%#[default]" \
    "$(render_segment_of charging 5)"
  assert_equals \
    " #[fg=green]${c10} #[default]14%#[default]" \
    "$(render_segment_of charging 14)"
  assert_equals \
    " #[fg=green]${c20} #[default]15%#[default]" \
    "$(render_segment_of charging 15)"
  assert_equals \
    " #[fg=green]${c60} #[default]64%#[default]" \
    "$(render_segment_of charging 64)"
  assert_equals \
    " #[fg=green]${c90} #[default]94%#[default]" \
    "$(render_segment_of charging 94)"
  assert_equals \
    " #[fg=green]${c100} #[default]95%#[default]" \
    "$(render_segment_of charging 95)"
  assert_equals \
    " #[fg=green]${c100} #[default]100%#[default]" \
    "$(render_segment_of charging 100)"
}

function test_charging_never_warns_even_at_low_percent() {
  local c10=$'\xf3\xb0\xa2\x9c'

  assert_equals \
    " #[fg=green]${c10} #[default]7%#[default]" \
    "$(render_segment_of charging 7)"
}

function test_plugged_renders_dim_plug() {
  local plug=$'\xf3\xb0\x9a\xa5'

  assert_equals \
    " #[fg=#828bb8]${plug} #[default]100%#[default]" \
    "$(render_segment_of plugged 100)"
  assert_equals \
    " #[fg=#828bb8]${plug} #[default]80%#[default]" \
    "$(render_segment_of plugged 80)"
}

function test_render_segment_empty_inputs_print_nothing() {
  assert_empty "$(render_segment_of '' '')"
  assert_empty "$(render_segment_of draining '')"
  assert_empty "$(render_segment_of '' 72)"
}

################################################################################
# Byte checks for every glyph constant
################################################################################

function test_level_glyph_bytes_match_code_points() {
  assert_equals "f3 b0 82 8e" "$(battery_glyph_bytes 0)"
  assert_equals "f3 b0 81 ba" "$(battery_glyph_bytes 1)"
  assert_equals "f3 b0 81 bb" "$(battery_glyph_bytes 2)"
  assert_equals "f3 b0 81 bc" "$(battery_glyph_bytes 3)"
  assert_equals "f3 b0 81 bd" "$(battery_glyph_bytes 4)"
  assert_equals "f3 b0 81 be" "$(battery_glyph_bytes 5)"
  assert_equals "f3 b0 81 bf" "$(battery_glyph_bytes 6)"
  assert_equals "f3 b0 82 80" "$(battery_glyph_bytes 7)"
  assert_equals "f3 b0 82 81" "$(battery_glyph_bytes 8)"
  assert_equals "f3 b0 82 82" "$(battery_glyph_bytes 9)"
  assert_equals "f3 b0 81 b9" "$(battery_glyph_bytes 10)"
}

function test_charging_glyph_bytes_match_code_points() {
  assert_equals "f3 b0 a2 9f" "$(charging_glyph_bytes 0)"
  assert_equals "f3 b0 a2 9c" "$(charging_glyph_bytes 1)"
  assert_equals "f3 b0 82 86" "$(charging_glyph_bytes 2)"
  assert_equals "f3 b0 82 87" "$(charging_glyph_bytes 3)"
  assert_equals "f3 b0 82 88" "$(charging_glyph_bytes 4)"
  assert_equals "f3 b0 a2 9d" "$(charging_glyph_bytes 5)"
  assert_equals "f3 b0 82 89" "$(charging_glyph_bytes 6)"
  assert_equals "f3 b0 a2 9e" "$(charging_glyph_bytes 7)"
  assert_equals "f3 b0 82 8a" "$(charging_glyph_bytes 8)"
  assert_equals "f3 b0 82 8b" "$(charging_glyph_bytes 9)"
  assert_equals "f3 b0 82 85" "$(charging_glyph_bytes 10)"
}

function test_plug_and_alert_bytes_match_code_points() {
  local plug alert
  plug="$("${BASH_BIN}" -c 'source "$1"; printf "%s" "${PLUG}"' bash "${SCRIPT}")"
  alert="$("${BASH_BIN}" -c 'source "$1"; printf "%s" "${ALERT}"' bash "${SCRIPT}")"

  assert_equals "f3 b0 9a a5" "$(printf '%s' "${plug}" | od -An -tx1 | tr -s ' ' | sed -e 's/^ //')"
  assert_equals "f3 b0 82 83" "$(printf '%s' "${alert}" | od -An -tx1 | tr -s ' ' | sed -e 's/^ //')"
}

################################################################################
# Failure paths, platform gate, arguments
################################################################################

function test_full_run_forks_pmset_exactly_once() {
  stub_pmset "$(printf "Now drawing from 'Battery Power'\n -InternalBattery-0 (id=1)\t72%%; discharging; 5:12 remaining present: true\n")"

  local b70=$'\xf3\xb0\x82\x80'
  assert_equals \
    " #[fg=#828bb8]${b70} #[default]72%#[default]" \
    "$(run_tmux_battery_native darwin)"
  assert_equals "1" "$(call_count pmset)"
}

function test_failing_pmset_prints_nothing_and_exits_zero_quietly() {
  stub_pmset '' 1

  local stderr_file output exit_code
  stderr_file="${TEST_TMP}/stderr"
  output="$(run_tmux_battery_native darwin 2> "${stderr_file}")"
  exit_code=$?

  assert_empty "${output}"
  assert_equals "0" "${exit_code}"
  assert_empty "$(cat "${stderr_file}")"
}

function test_missing_pmset_prints_nothing_and_exits_zero_quietly() {
  local stderr_file output exit_code
  stderr_file="${TEST_TMP}/stderr"
  output="$(run_tmux_battery_native_fake_path_only darwin 2> "${stderr_file}")"
  exit_code=$?

  assert_empty "${output}"
  assert_equals "0" "${exit_code}"
  assert_empty "$(cat "${stderr_file}")"
}

function test_non_darwin_prints_nothing_and_forks_nothing() {
  stub_pmset "$(printf "Now drawing from 'Battery Power'\n -InternalBattery-0 (id=1)\t72%%; discharging; 5:12 remaining present: true\n")"

  local output
  output="$(run_tmux_battery_native linux-gnu)"

  assert_empty "${output}"
  assert_empty "$(calls)"
}

function test_help_flag_prints_legend_exits_zero_and_forks_nothing() {
  local output
  output="$(run_tmux_battery_native darwin --help)"
  local exit_code=$?

  assert_contains "usage:" "${output}"
  assert_contains "draining" "${output}"
  assert_contains "charging" "${output}"
  assert_contains "plugged" "${output}"
  assert_contains "11-20%" "${output}"
  assert_contains "10%" "${output}"
  assert_equals "0" "${exit_code}"
  assert_empty "$(calls)"
}

function test_unrecognized_argument_is_rejected_before_pmset() {
  local output
  output="$(run_tmux_battery_native darwin --bogus 2>&1)"
  local exit_code=$?

  assert_equals "2" "${exit_code}"
  assert_contains "unrecognized argument" "${output}"
  assert_empty "$(calls)"
}

function test_output_never_ends_with_a_newline() {
  stub_pmset "$(printf "Now drawing from 'Battery Power'\n -InternalBattery-0 (id=1)\t72%%; discharging; 5:12 remaining present: true\n")"

  local b70=$'\xf3\xb0\x82\x80'
  local expected=" #[fg=#828bb8]${b70} #[default]72%#[default]"
  local expected_bytes
  expected_bytes="$(printf '%s' "${expected}" | wc -c | tr -d ' ')"

  assert_equals "${expected_bytes}" "$(run_tmux_battery_native darwin | wc -c | tr -d ' ')"

  rm -f "${FAKE_BIN}/pmset"
  assert_equals "0" "$(run_tmux_battery_native_fake_path_only darwin | wc -c | tr -d ' ')"
}

################################################################################
# Static Bash 3.2 guard
################################################################################

function test_source_avoids_bash32_forbidden_constructs() {
  local filtered="${TEST_TMP}/battery_code_only.sh"
  grep -v '^[[:space:]]*#' "${SCRIPT}" > "${filtered}"

  local code
  code="$(cat "${filtered}")"

  assert_not_contains "\$'\\u" "${code}"
  assert_not_contains "\$'\\U" "${code}"
  assert_not_contains "declare -A" "${code}"
  assert_not_contains "typeset -A" "${code}"
  assert_not_contains "mapfile" "${code}"
  assert_not_contains "readarray" "${code}"
  assert_not_contains ",,}" "${code}"
  assert_not_contains "^^}" "${code}"
  assert_not_contains "local -n" "${code}"
  assert_not_contains "EPOCHSECONDS" "${code}"
  assert_not_contains "%(" "${code}"
  assert_not_contains ";&" "${code}"

  assert_equals "0" "$(grep -c -E '\[-[$0-9]' "${filtered}" || true)"
}
