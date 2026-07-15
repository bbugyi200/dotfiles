#!/bin/bash

#################################################################################
# Regression tests for the reusable, locked toobig_split script chop.           #
#################################################################################

TOOBIG_SPLIT_SCRIPT="${PWD}/home/bin/executable_sase_chop_toobig_split"
ATHENA_CONFIG="${PWD}/home/dot_config/sase/sase_athena.yml"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  REPO_ROOT="${TEST_TMP}/repo"
  STATE_DIR="${TEST_TMP}/state"
  CONTEXT_FILE="${TEST_TMP}/context.json"
  PROMPTS_FILE="${TEST_TMP}/prompts.txt"
  SASE_CALLS_FILE="${TEST_TMP}/sase_calls.txt"
  TOOBIG_CALLS_FILE="${TEST_TMP}/toobig_calls.txt"
  PROJECT_NAME="demo"
  SRC_OUTPUT=""
  TESTS_OUTPUT=""
  LIB_OUTPUT=""
  SPEC_OUTPUT=""
  PROJECT_FAILURE="0"
  SCANNER_FAILURE_TREE=""
  LAUNCH_FAILURE="0"
  BLOCK_TREE=""
  BLOCK_BASE="${TEST_TMP}/scanner_block"

  mkdir -p "${FAKE_BIN}" "${REPO_ROOT}/src" "${REPO_ROOT}/tests"
  printf '{}\n' >"${CONTEXT_FILE}"
  write_fake_sase
  write_fake_toobig
}

function tear_down() {
  if [[ -n "${TEST_TMP:-}" ]]; then
    touch "${BLOCK_BASE:-${TEST_TMP}/scanner_block}.release" 2>/dev/null || true
    rm -rf "${TEST_TMP}"
  fi
}

function write_fake_sase() {
  cat >"${FAKE_BIN}/sase" <<'EOF'
#!/bin/bash
set -euo pipefail

printf '%s\n' "$*" >>"${FAKE_SASE_CALLS}"

if [[ "$1" == "project" && "$2" == "show" && "$4" == "--json" ]]; then
  if [[ "${FAKE_PROJECT_FAILURE}" == "1" ]]; then
    printf 'project unavailable\n' >&2
    exit 17
  fi
  printf '{"workspace_dir":"%s","vcs_kind":"gh","effective_project_name":"%s"}\n' \
    "${FAKE_REPO_ROOT}" "$3"
  exit 0
fi

if [[ "$1" == "run" && "$#" == "2" ]]; then
  if [[ "${FAKE_LAUNCH_FAILURE}" == "1" ]]; then
    printf 'launch refused\n' >&2
    exit 19
  fi
  {
    printf '%s\n' '---PROMPT---'
    printf '%s\n' "$2"
  } >>"${FAKE_SASE_PROMPTS}"
  printf 'fake launch accepted\n'
  exit 0
fi

printf 'unexpected sase args: %s\n' "$*" >&2
exit 2
EOF
  chmod +x "${FAKE_BIN}/sase"
}

function write_fake_toobig() {
  cat >"${FAKE_BIN}/toobig" <<'EOF'
#!/bin/bash
set -euo pipefail

printf '%s\n' "$*" >>"${FAKE_TOOBIG_CALLS}"
tree="$2"
if [[ "${FAKE_SCANNER_FAILURE_TREE}" == "${tree}" ]]; then
  printf 'scanner exploded for %s\n' "${tree}" >&2
  exit 23
fi
if [[ -n "${FAKE_BLOCK_TREE}" && "${FAKE_BLOCK_TREE}" == "${tree}" ]]; then
  touch "${FAKE_BLOCK_BASE}.started"
  while [[ ! -f "${FAKE_BLOCK_BASE}.release" ]]; do
    sleep 0.02
  done
fi

case "${tree}" in
  src) output="${FAKE_TOOBIG_SRC_OUTPUT}" ;;
  tests) output="${FAKE_TOOBIG_TESTS_OUTPUT}" ;;
  lib) output="${FAKE_TOOBIG_LIB_OUTPUT}" ;;
  spec) output="${FAKE_TOOBIG_SPEC_OUTPUT}" ;;
  *)
    printf 'unexpected scan tree: %s\n' "${tree}" >&2
    exit 24
    ;;
esac
printf '%b' "${output}"
EOF
  chmod +x "${FAKE_BIN}/toobig"
}

function run_chop_with_args() {
  PATH="${FAKE_BIN}:${PATH}" \
    FAKE_REPO_ROOT="${REPO_ROOT}" \
    FAKE_SASE_CALLS="${SASE_CALLS_FILE}" \
    FAKE_SASE_PROMPTS="${PROMPTS_FILE}" \
    FAKE_PROJECT_FAILURE="${PROJECT_FAILURE}" \
    FAKE_LAUNCH_FAILURE="${LAUNCH_FAILURE}" \
    FAKE_TOOBIG_CALLS="${TOOBIG_CALLS_FILE}" \
    FAKE_TOOBIG_SRC_OUTPUT="${SRC_OUTPUT}" \
    FAKE_TOOBIG_TESTS_OUTPUT="${TESTS_OUTPUT}" \
    FAKE_TOOBIG_LIB_OUTPUT="${LIB_OUTPUT}" \
    FAKE_TOOBIG_SPEC_OUTPUT="${SPEC_OUTPUT}" \
    FAKE_SCANNER_FAILURE_TREE="${SCANNER_FAILURE_TREE}" \
    FAKE_BLOCK_TREE="${BLOCK_TREE}" \
    FAKE_BLOCK_BASE="${BLOCK_BASE}" \
    SASE_TOOBIG_SPLIT_PROJECT="${PROJECT_NAME}" \
    SASE_TOOBIG_SPLIT_STATE_DIR="${STATE_DIR}" \
    python3 "${TOOBIG_SPLIT_SCRIPT}" --context "${CONTEXT_FILE}" "$@" 2>&1
}

function run_chop() {
  run_chop_with_args
}

function prompt_count() {
  if [[ ! -f "${PROMPTS_FILE}" ]]; then
    printf '0'
    return
  fi
  grep -c '^---PROMPT---$' "${PROMPTS_FILE}"
}

function occurrence_count() {
  local needle="$1"
  local file="$2"
  if [[ ! -f "${file}" ]]; then
    printf '0'
    return
  fi
  grep -oF -- "${needle}" "${file}" | wc -l | tr -d ' '
}

function wait_for_file() {
  local path="$1"
  local attempt
  for attempt in $(seq 1 250); do
    if [[ -f "${path}" ]]; then
      return 0
    fi
    sleep 0.02
  done
  return 1
}

function test_project_resolution_deduplicates_paths_and_builds_wait_chain() {
  SRC_OUTPUT=$'src/pkg/large.py\nsrc/pkg/shared.py\n'
  TESTS_OUTPUT=$'src/pkg/shared.py\ntests/large.py\n'

  local output
  output="$(run_chop)"

  assert_contains "scanned_trees=src,tests limits=1000 850 700 file_count=3" "${output}"
  assert_contains "launched=3" "${output}"
  assert_same "1" "$(prompt_count)"
  assert_contains "project show demo --json" "$(cat "${SASE_CALLS_FILE}")"
  assert_contains "--files-only src 1000 850 700" "$(cat "${TOOBIG_CALLS_FILE}")"
  assert_contains "--files-only tests 1000 850 700" "$(cat "${TOOBIG_CALLS_FILE}")"

  local prompt
  prompt="$(cat "${PROMPTS_FILE}")"
  assert_same "3" "$(occurrence_count "%w(runners=0)" "${PROMPTS_FILE}")"
  assert_same "2" "$(grep -c '^%wait$' "${PROMPTS_FILE}")"
  assert_same "3" "$(occurrence_count "#split_file:" "${PROMPTS_FILE}")"
  assert_same "2" "$(occurrence_count "%name:split_file.large-@" "${PROMPTS_FILE}")"
  assert_contains "%name:split_file.shared-@" "${prompt}"
  assert_contains "#gh:demo %group:chop %auto #split_file:src/pkg/large.py" "${prompt}"
  assert_contains "#split_file:src/pkg/shared.py" "${prompt}"
  assert_contains "#split_file:tests/large.py" "${prompt}"
  assert_contains $'%wait\n%name:split_file.shared-@' "${prompt}"
}

function test_direct_mode_honors_custom_trees_limits_and_launch_ref() {
  PROJECT_NAME=""
  LIB_OUTPUT=$'lib/huge.py\n'
  SPEC_OUTPUT=$'spec/huge_test.py\n'
  mkdir -p "${REPO_ROOT}/lib" "${REPO_ROOT}/spec"

  local output
  output="$(run_chop_with_args \
    --repo-root "${REPO_ROOT}" \
    --launch-ref git:other \
    --trees lib spec \
    --limits 40 30 20)"

  assert_contains "scanned_trees=lib,spec limits=40 30 20 file_count=2" "${output}"
  assert_contains "launch_ref=#git:other" "${output}"
  assert_same "0" "$(occurrence_count "project show" "${SASE_CALLS_FILE}")"
  assert_contains "--files-only lib 40 30 20" "$(cat "${TOOBIG_CALLS_FILE}")"
  assert_contains "--files-only spec 40 30 20" "$(cat "${TOOBIG_CALLS_FILE}")"
  assert_contains "#git:other %group:chop %auto #split_file:lib/huge.py" "$(cat "${PROMPTS_FILE}")"
}

function test_no_oversized_files_reports_noop_without_launching() {
  local output
  output="$(run_chop)"

  assert_contains "file_count=0 sample_files=-" "${output}"
  assert_contains "launched=0 reason=no_files_over_limits" "${output}"
  assert_same "0" "$(prompt_count)"
}

function test_project_resolution_failure_is_visible_and_nonzero() {
  PROJECT_FAILURE="1"

  local output status
  output="$(run_chop)" && status=0 || status=$?

  assert_same "1" "${status}"
  assert_contains "project resolution failed" "${output}"
  assert_contains "project unavailable" "${output}"
  assert_same "0" "$(prompt_count)"
}

function test_scanner_failure_is_visible_and_prevents_launch() {
  SRC_OUTPUT=$'src/large.py\n'
  SCANNER_FAILURE_TREE="tests"

  local output status
  output="$(run_chop)" && status=0 || status=$?

  assert_same "1" "${status}"
  assert_contains "scanner failed: tree='tests' exit_code=23" "${output}"
  assert_contains "scanner exploded for tests" "${output}"
  assert_same "0" "$(prompt_count)"
}

function test_launcher_failure_is_visible_and_nonzero() {
  SRC_OUTPUT=$'src/large.py\n'
  LAUNCH_FAILURE="1"

  local output status
  output="$(run_chop)" && status=0 || status=$?

  assert_same "1" "${status}"
  assert_contains "launch_failed=1 exit_code=19 detail=launch refused" "${output}"
  assert_same "0" "$(prompt_count)"
}

function test_repo_scoped_lock_skips_overlapping_process() {
  SRC_OUTPUT=$'src/large.py\n'
  BLOCK_TREE="src"
  local first_output="${TEST_TMP}/first_output.txt"

  run_chop >"${first_output}" 2>&1 &
  local first_pid=$!
  local wait_status
  wait_for_file "${BLOCK_BASE}.started" && wait_status=0 || wait_status=$?
  assert_same "0" "${wait_status}" "first chop did not reach scanner"

  local second_output second_status
  second_output="$(run_chop)" && second_status=0 || second_status=$?
  assert_same "0" "${second_status}"
  assert_contains "launched=0 reason=lock_busy" "${second_output}"

  touch "${BLOCK_BASE}.release"
  local first_status
  wait "${first_pid}" && first_status=0 || first_status=$?
  assert_same "0" "${first_status}"
  assert_contains "launched=1" "$(cat "${first_output}")"
  assert_same "1" "$(prompt_count)"
}

function test_athena_config_selects_script_chop_and_target_project() {
  local actual
  actual="$("${PWD}/.venv/bin/python" - "${ATHENA_CONFIG}" <<'PY'
import sys
from pathlib import Path

import yaml


config = yaml.safe_load(Path(sys.argv[1]).read_text())
chops = config["axe"]["lumberjacks"]["run_every"]["chops"]
toobig = next(chop for chop in chops if chop["name"] == "toobig_split")
print(
    f"{toobig['name']}\t{'agent' in toobig}\t"
    f"{toobig['env']['SASE_TOOBIG_SPLIT_PROJECT']}"
)
print(sum(chop["name"] == "sase_toobig_split" for chop in chops))
PY
)"

  assert_same $'toobig_split\tFalse\tsase\n0' "${actual}"
}
