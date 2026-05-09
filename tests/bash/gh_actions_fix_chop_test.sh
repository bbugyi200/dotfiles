#!/bin/bash

#################################################################################
# Regression tests for the GitHub Actions failure fixer chop.                   #
#################################################################################

GH_ACTIONS_FIX_SCRIPT="${PWD}/home/bin/executable_sase_chop_gh_actions_fix"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  STATE_DIR="${TEST_TMP}/state"
  CONTEXT_FILE="${TEST_TMP}/context.json"
  PROMPTS_FILE="${TEST_TMP}/prompts.txt"
  mkdir -p "${FAKE_BIN}" "${STATE_DIR}"
  printf '{"state_dir": "%s"}\n' "${STATE_DIR}" >"${CONTEXT_FILE}"
  write_fake_sase
  write_fake_gh
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function write_fake_sase() {
  cat >"${FAKE_BIN}/sase" <<'EOF'
#!/bin/bash
set -euo pipefail

if [[ "$1" == "run" && "$2" == "-d" ]]; then
  {
    printf '%s\n' '---PROMPT---'
    printf '%s\n' "$3"
  } >>"${FAKE_SASE_PROMPTS}"
  exit 0
fi

printf 'unexpected sase args: %s\n' "$*" >&2
exit 1
EOF
  chmod +x "${FAKE_BIN}/sase"
}

function write_fake_gh() {
  cat >"${FAKE_BIN}/gh" <<'EOF'
#!/bin/bash
set -euo pipefail

if [[ "$1" == "run" && "$2" == "list" ]]; then
  printf '%s' "${FAKE_GH_LIST_JSON}"
  exit 0
fi

if [[ "$1" == "run" && "$2" == "view" ]]; then
  for arg in "$@"; do
    if [[ "${arg}" == "--log-failed" ]]; then
      if [[ "${FAKE_GH_LOG_FAILED_RC:-0}" != "0" ]]; then
        printf '%s' "${FAKE_GH_LOG_FAILED_OUTPUT:-log failed}" >&2
        exit "${FAKE_GH_LOG_FAILED_RC}"
      fi
      printf '%s' "${FAKE_GH_LOG_FAILED_OUTPUT:-failed log output}"
      exit 0
    fi
    if [[ "${arg}" == "--verbose" ]]; then
      if [[ "${FAKE_GH_VERBOSE_RC:-0}" != "0" ]]; then
        printf '%s' "${FAKE_GH_VERBOSE_OUTPUT:-verbose failed}" >&2
        exit "${FAKE_GH_VERBOSE_RC}"
      fi
      printf '%s' "${FAKE_GH_VERBOSE_OUTPUT:-verbose run output}"
      exit 0
    fi
  done
fi

printf 'unexpected gh args: %s\n' "$*" >&2
exit 1
EOF
  chmod +x "${FAKE_BIN}/gh"
}

function run_chop() {
  PATH="${FAKE_BIN}:${PATH}" \
    FAKE_SASE_PROMPTS="${PROMPTS_FILE}" \
    SASE_GHA_FIX_REPOS="owner/repo" \
    python3 "${GH_ACTIONS_FIX_SCRIPT}" --context "${CONTEXT_FILE}" 2>&1
}

function prompt_count() {
  if [[ ! -f "${PROMPTS_FILE}" ]]; then
    printf '0'
    return
  fi
  grep -c '^---PROMPT---$' "${PROMPTS_FILE}"
}

function set_latest_run() {
  local conclusion="$1"
  local attempt="${2:-1}"
  export FAKE_GH_LIST_JSON
  FAKE_GH_LIST_JSON='[{"attempt": '"${attempt}"', "conclusion": "'"${conclusion}"'", "databaseId": 12345, "displayTitle": "Fix CI", "event": "push", "headBranch": "main", "headSha": "abc123", "name": "Unit Tests", "status": "completed", "url": "https://github.com/owner/repo/actions/runs/12345", "workflowName": "Unit Tests"}]'
}

function test_success_conclusion_does_not_launch_agent() {
  set_latest_run "success"

  local output
  output="$(run_chop)"

  assert_contains "latest run conclusion is success, skipping" "${output}"
  assert_same "0" "$(prompt_count)"
}

function test_failure_launches_agent_with_failed_logs() {
  set_latest_run "failure"
  export FAKE_GH_LOG_FAILED_OUTPUT="boom failed in pytest"

  local output
  output="$(run_chop)"

  assert_contains "launched fixer agent for run 12345 attempt 1" "${output}"
  assert_same "1" "$(prompt_count)"
  assert_contains "#gh:owner/repo %t:gact %n:gha-fix-owner-repo-12345-a1" "$(cat "${PROMPTS_FILE}")"
  assert_contains "Workflow: Unit Tests" "$(cat "${PROMPTS_FILE}")"
  assert_contains "boom failed in pytest" "$(cat "${PROMPTS_FILE}")"
}

function test_dedupe_skips_same_run_attempt() {
  set_latest_run "failure"
  export FAKE_GH_LOG_FAILED_OUTPUT="first failure"

  run_chop >/dev/null
  local output
  output="$(run_chop)"

  assert_contains "already launched agent for run 12345 attempt 1" "${output}"
  assert_same "1" "$(prompt_count)"
}

function test_new_attempt_launches_again() {
  set_latest_run "failure" "1"
  export FAKE_GH_LOG_FAILED_OUTPUT="attempt one"
  run_chop >/dev/null

  set_latest_run "failure" "2"
  export FAKE_GH_LOG_FAILED_OUTPUT="attempt two"
  run_chop >/dev/null

  assert_same "2" "$(prompt_count)"
  assert_contains "%n:gha-fix-owner-repo-12345-a2" "$(cat "${PROMPTS_FILE}")"
  assert_contains "attempt two" "$(cat "${PROMPTS_FILE}")"
}

function test_log_failed_failure_falls_back_to_verbose_output() {
  set_latest_run "timed_out"
  export FAKE_GH_LOG_FAILED_RC="1"
  export FAKE_GH_LOG_FAILED_OUTPUT="failed logs unavailable"
  export FAKE_GH_VERBOSE_OUTPUT="verbose fallback output"

  local output
  output="$(run_chop)"

  assert_contains "falling back to verbose run view" "${output}"
  assert_same "1" "$(prompt_count)"
  assert_contains "verbose fallback output" "$(cat "${PROMPTS_FILE}")"
}
