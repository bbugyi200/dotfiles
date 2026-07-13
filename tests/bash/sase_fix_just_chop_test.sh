#!/bin/bash

#################################################################################
# Regression tests for the guarded fix_just workflow chop.                      #
#################################################################################

SASE_FIX_JUST_SCRIPT="${PWD}/home/bin/executable_sase_chop_sase_fix_just"
FIX_JUST_PROMPT="%n:sase_fix_just-@ %w(runners=0) #gh:sase %g:chop #!sase/fix_just"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  CONTEXT_FILE="${TEST_TMP}/context.json"
  CHANGESPECS_FILE="${TEST_TMP}/all_changespecs.json"
  PROMPTS_FILE="${TEST_TMP}/prompts.txt"
  mkdir -p "${FAKE_BIN}"
  printf '[]\n' >"${CHANGESPECS_FILE}"
  printf '{"all_changespecs_file": "%s"}\n' "${CHANGESPECS_FILE}" >"${CONTEXT_FILE}"
  write_fake_sase
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

function run_chop() {
  PATH="${FAKE_BIN}:${PATH}" \
    FAKE_SASE_PROMPTS="${PROMPTS_FILE}" \
    python3 "${SASE_FIX_JUST_SCRIPT}" --context "${CONTEXT_FILE}" 2>&1
}

function prompt_count() {
  if [[ ! -f "${PROMPTS_FILE}" ]]; then
    printf '0'
    return
  fi
  grep -c '^---PROMPT---$' "${PROMPTS_FILE}"
}

function write_changespecs() {
  cat >"${CHANGESPECS_FILE}"
}

function test_open_fix_just_changespec_blocks_launch() {
  write_changespecs <<'JSON'
[
  {"name": "sase_fix_just_tests_1", "status": "WIP"},
  {"name": "sase_gha_fix_other", "status": "Draft"}
]
JSON

  local output
  output="$(run_chop)"

  assert_contains "open ChangeSpecs block launch: prefix='sase_fix_just_'" "${output}"
  assert_contains "sase_fix_just_tests_1" "${output}"
  assert_contains "no fix_just workflow launched" "${output}"
  assert_same "0" "$(prompt_count)"
}

function test_terminal_fix_just_changespec_allows_launch() {
  write_changespecs <<'JSON'
[
  {"name": "sase_fix_just_old", "status": "Submitted"},
  {"name": "sase_fix_just_archived", "status": "Archived"},
  {"name": "sase_fix_just_reverted", "status": "Reverted"}
]
JSON

  local output
  output="$(run_chop)"

  assert_contains "launching fix_just workflow" "${output}"
  assert_contains "launched fix_just workflow" "${output}"
  assert_same "1" "$(prompt_count)"
  assert_contains "${FIX_JUST_PROMPT}" "$(cat "${PROMPTS_FILE}")"
  assert_same "1" "$(grep -o '%w(runners=0)' "${PROMPTS_FILE}" | wc -l | tr -d ' ')"
}

function test_missing_changespec_snapshot_skips_safely() {
  rm -f "${CHANGESPECS_FILE}"

  local output
  output="$(run_chop)"

  assert_contains "changespec guard check_error:" "${output}"
  assert_contains "failed to read ChangeSpec snapshot" "${output}"
  assert_contains "skipping fix_just workflow launch" "${output}"
  assert_same "0" "$(prompt_count)"
}
