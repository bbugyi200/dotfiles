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
  CHANGESPECS_FILE="${TEST_TMP}/all_changespecs.json"
  PROMPTS_FILE="${TEST_TMP}/prompts.txt"
  GH_CALLS_FILE="${TEST_TMP}/gh_calls.txt"
  mkdir -p "${FAKE_BIN}" "${STATE_DIR}"
  printf '[]\n' >"${CHANGESPECS_FILE}"
  printf '{"state_dir": "%s", "all_changespecs_file": "%s"}\n' \
    "${STATE_DIR}" "${CHANGESPECS_FILE}" >"${CONTEXT_FILE}"
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

printf '%s\n' "$*" >>"${FAKE_GH_CALLS}"

if [[ "$1" == "run" && "$2" == "list" ]]; then
  if [[ "${FAKE_GH_LIST_RC:-0}" != "0" ]]; then
    printf '%s' "${FAKE_GH_LIST_OUTPUT:-gh list failed}" >&2
    exit "${FAKE_GH_LIST_RC}"
  fi
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
    FAKE_GH_CALLS="${GH_CALLS_FILE}" \
    SASE_GHA_FIX_REPOS="owner/repo" \
    python3 "${GH_ACTIONS_FIX_SCRIPT}" --context "${CONTEXT_FILE}" 2>&1
}

function run_chop_without_repos() {
  PATH="${FAKE_BIN}:${PATH}" \
    FAKE_SASE_PROMPTS="${PROMPTS_FILE}" \
    FAKE_GH_CALLS="${GH_CALLS_FILE}" \
    SASE_GHA_FIX_REPOS="" \
    python3 "${GH_ACTIONS_FIX_SCRIPT}" --context "${CONTEXT_FILE}" 2>&1
}

function prompt_count() {
  if [[ ! -f "${PROMPTS_FILE}" ]]; then
    printf '0'
    return
  fi
  grep -c '^---PROMPT---$' "${PROMPTS_FILE}"
}

function gh_call_count() {
  if [[ ! -f "${GH_CALLS_FILE}" ]]; then
    printf '0'
    return
  fi
  wc -l <"${GH_CALLS_FILE}" | tr -d ' '
}

function write_changespecs() {
  cat >"${CHANGESPECS_FILE}"
}

function set_latest_run() {
  local conclusion="$1"
  local attempt="${2:-1}"
  export FAKE_GH_LIST_JSON
  FAKE_GH_LIST_JSON='[{"attempt": '"${attempt}"', "conclusion": "'"${conclusion}"'", "databaseId": 12345, "displayTitle": "Fix CI", "event": "push", "headBranch": "main", "headSha": "abc123", "name": "Unit Tests", "status": "completed", "url": "https://github.com/owner/repo/actions/runs/12345", "workflowName": "Unit Tests"}]'
}

function test_open_gha_changespec_blocks_before_gh_calls() {
  write_changespecs <<'JSON'
[
  {"name": "sase_gha_fix_owner_repo_12345", "status": "Draft"},
  {"name": "sase_gha_fix_terminal", "status": "Submitted"},
  {"name": "sase_fix_just_existing", "status": "Draft"}
]
JSON

  local output
  output="$(run_chop)"

  assert_contains "open ChangeSpecs block launch: prefix='sase_gha_fix_'" "${output}"
  assert_contains "sase_gha_fix_owner_repo_12345" "${output}"
  assert_contains "no fixer agents launched" "${output}"
  assert_same "0" "$(gh_call_count)"
  assert_same "0" "$(prompt_count)"
}

function test_terminal_gha_changespec_does_not_block() {
  write_changespecs <<'JSON'
[
  {"name": "sase_gha_fix_submitted", "status": "Submitted"},
  {"name": "sase_gha_fix_archived", "status": "Archived"},
  {"name": "sase_gha_fix_reverted", "status": "Reverted"}
]
JSON
  set_latest_run "failure"
  export FAKE_GH_LOG_FAILED_OUTPUT="terminal specs should not block"

  local output
  output="$(run_chop)"

  assert_contains "launched fixer agent for run 12345 attempt 1" "${output}"
  assert_same "1" "$(prompt_count)"
  assert_contains "terminal specs should not block" "$(cat "${PROMPTS_FILE}")"
}

function test_success_conclusion_does_not_launch_agent() {
  set_latest_run "success"

  local output
  output="$(run_chop)"

  assert_contains "latest run conclusion is success, skipping" "${output}"
  assert_contains "repo=owner/repo status=completed conclusion=success run=12345 attempt=1" "${output}"
  assert_contains "decision=conclusion_success_skip" "${output}"
  assert_contains "summary: repos_configured=1 repos_checked=1 actionable_failures=0 dedupe_skips=0 non_action_skips=1 launch_successes=0 launch_failures=0 check_errors=0" "${output}"
  assert_same "0" "$(prompt_count)"
}

function test_failure_launches_agent_with_failed_logs() {
  set_latest_run "failure"
  export FAKE_GH_LOG_FAILED_OUTPUT="boom failed in pytest"

  local output
  output="$(run_chop)"

  assert_contains "launched fixer agent for run 12345 attempt 1" "${output}"
  assert_contains "repo=owner/repo status=completed conclusion=failure run=12345 attempt=1" "${output}"
  assert_contains "workflow='Unit Tests'" "${output}"
  assert_contains "title='Fix CI'" "${output}"
  assert_contains "decision=launched" "${output}"
  assert_contains "summary: repos_configured=1 repos_checked=1 actionable_failures=1 dedupe_skips=0 non_action_skips=0 launch_successes=1 launch_failures=0 check_errors=0" "${output}"
  assert_same "1" "$(prompt_count)"
  assert_contains "#gh:owner/repo %g:chop #pr(gha_fix_owner_repo_12345_a1) %n:gha-fix-owner-repo-12345-a1" "$(cat "${PROMPTS_FILE}")"
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
  assert_contains "decision=duplicate_skip" "${output}"
  assert_contains "summary: repos_configured=1 repos_checked=1 actionable_failures=1 dedupe_skips=1 non_action_skips=0 launch_successes=0 launch_failures=0 check_errors=0" "${output}"
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
  assert_contains "#pr(gha_fix_owner_repo_12345_a2)" "$(cat "${PROMPTS_FILE}")"
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

function test_no_repos_configured_prints_summary() {
  local output
  output="$(run_chop_without_repos)"

  assert_contains "SASE_GHA_FIX_REPOS is empty; nothing to check" "${output}"
  assert_contains "summary: repos_configured=0 repos_checked=0 actionable_failures=0 dedupe_skips=0 non_action_skips=0 launch_successes=0 launch_failures=0 check_errors=0" "${output}"
  assert_contains "no fixer agents launched" "${output}"
  assert_same "0" "$(prompt_count)"
}

function test_gh_list_failure_prints_summary() {
  export FAKE_GH_LIST_RC="1"
  export FAKE_GH_LIST_OUTPUT="api exploded while listing runs"

  local output
  output="$(run_chop)"

  assert_contains "gh run list failed: api exploded while listing runs" "${output}"
  assert_contains "repo=owner/repo status=unknown conclusion=unknown run=unknown attempt=unknown" "${output}"
  assert_contains "decision=check_error" "${output}"
  assert_contains "summary: repos_configured=1 repos_checked=1 actionable_failures=0 dedupe_skips=0 non_action_skips=0 launch_successes=0 launch_failures=0 check_errors=1" "${output}"
  assert_same "0" "$(prompt_count)"
}
