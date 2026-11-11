#!/bin/bash

#################################################################################
# Regression tests for nvim_lazy_doctor, the lazy.nvim interrupted-checkout    #
# repair script. Builds a temp NVIM_LAZY_ROOT with real git repos (clean,      #
# interrupted, local-edits, interrupted+doc/tags, and a path with a space) and #
# stubs nvim on PATH to log its argv.                                          #
#################################################################################

DOCTOR="${PWD}/home/bin/executable_nvim_lazy_doctor"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  mkdir -p "${FAKE_BIN}"
  export TEST_TMP FAKE_BIN

  export NVIM_LAZY_ROOT="${TEST_TMP}/lazy"
  mkdir -p "${NVIM_LAZY_ROOT}"
  export NVIM_LOG="${TEST_TMP}/nvim.log"
  export GIT_AUTHOR_NAME="test"
  export GIT_AUTHOR_EMAIL="test@test"
  export GIT_COMMITTER_NAME="test"
  export GIT_COMMITTER_EMAIL="test@test"

  make_repo "clean_plugin"
  make_repo "interrupted_plugin"
  git -C "${NVIM_LAZY_ROOT}/interrupted_plugin" rm -q --cached foo.txt >/dev/null 2>&1 || true
  # Recreate as a plain deletion: restore index, then delete the file.
  git -C "${NVIM_LAZY_ROOT}/interrupted_plugin" checkout -q HEAD -- foo.txt 2>/dev/null || true
  rm "${NVIM_LAZY_ROOT}/interrupted_plugin/foo.txt"

  make_repo "local_plugin"
  printf 'local change\n' >>"${NVIM_LAZY_ROOT}/local_plugin/foo.txt"

  make_repo "doctags_plugin"
  mkdir -p "${NVIM_LAZY_ROOT}/doctags_plugin/doc"
  printf 'tags\n' >"${NVIM_LAZY_ROOT}/doctags_plugin/doc/tags"
  git -C "${NVIM_LAZY_ROOT}/doctags_plugin" add -f doc/tags >/dev/null
  git -C "${NVIM_LAZY_ROOT}/doctags_plugin" commit -qm "add tags" >/dev/null
  rm "${NVIM_LAZY_ROOT}/doctags_plugin/foo.txt"
  # doc/tags is ignored: simulate lazy's own tags file changing.
  printf 'more tags\n' >>"${NVIM_LAZY_ROOT}/doctags_plugin/doc/tags"

  make_repo "sp ace_plugin"
  rm "${NVIM_LAZY_ROOT}/sp ace_plugin/foo.txt"
  # A file with a space in its own name, also deleted.
  printf 'spaced\n' >"${NVIM_LAZY_ROOT}/sp ace_plugin/inner file.txt"
  git -C "${NVIM_LAZY_ROOT}/sp ace_plugin" add "inner file.txt" >/dev/null
  git -C "${NVIM_LAZY_ROOT}/sp ace_plugin" commit -qm "add spaced file" >/dev/null
  rm "${NVIM_LAZY_ROOT}/sp ace_plugin/inner file.txt"

  # Stub nvim: log argv, optionally re-break one repo to simulate a bad update.
  cat >"${FAKE_BIN}/nvim" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >>"${NVIM_LOG:-/dev/null}"
if [[ -n "${FAKE_NVIM_REBREAK:-}" && -d "${FAKE_NVIM_REBREAK}" ]]; then
  rm -f "${FAKE_NVIM_REBREAK}/foo.txt"
fi
exit 0
EOF
  chmod +x "${FAKE_BIN}/nvim"

  export PATH="${FAKE_BIN}:/usr/bin:/bin"
  : >"${NVIM_LOG}"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function make_repo() {
  local name="$1"
  mkdir -p "${NVIM_LAZY_ROOT}/${name}"
  git -C "${NVIM_LAZY_ROOT}/${name}" init -q >/dev/null
  printf 'hello\n' >"${NVIM_LAZY_ROOT}/${name}/foo.txt"
  printf 'tags\n' >"${NVIM_LAZY_ROOT}/${name}/doc_tags.txt"
  git -C "${NVIM_LAZY_ROOT}/${name}" add foo.txt doc_tags.txt >/dev/null
  git -C "${NVIM_LAZY_ROOT}/${name}" commit -qm "init" >/dev/null
}

function run_doctor() {
  OUT_FILE="${TEST_TMP}/out.txt"
  bash "${DOCTOR}" "$@" >"${OUT_FILE}" 2>&1
  DOCTOR_RC=$?
  DOCTOR_OUT="$(cat "${OUT_FILE}")"
}

function test_check_reports_classes_and_exits_one() {
  run_doctor

  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "interrupted_plugin" "${DOCTOR_OUT}"
  assert_contains "interrupted" "${DOCTOR_OUT}"
  assert_contains "local_plugin" "${DOCTOR_OUT}"
  assert_contains "local-edits" "${DOCTOR_OUT}"
  assert_contains "doctags_plugin" "${DOCTOR_OUT}"
  assert_not_contains "clean_plugin" "${DOCTOR_OUT}"
}

function test_check_clean_root_exits_zero() {
  CLEAN_ROOT="${TEST_TMP}/cleanroot"
  mkdir -p "${CLEAN_ROOT}/only_clean"
  git -C "${CLEAN_ROOT}/only_clean" init -q >/dev/null
  printf 'x\n' >"${CLEAN_ROOT}/only_clean/foo.txt"
  git -C "${CLEAN_ROOT}/only_clean" add foo.txt >/dev/null
  git -C "${CLEAN_ROOT}/only_clean" commit -qm "init" >/dev/null
  NVIM_LAZY_ROOT="${CLEAN_ROOT}" bash "${DOCTOR}" >"${TEST_TMP}/clean.txt" 2>&1
  assert_equals 0 "$?"
  assert_equals "" "$(cat "${TEST_TMP}/clean.txt")"
}

function test_fix_restores_interrupted_and_leaves_local_edits() {
  before=$(sha256sum "${NVIM_LAZY_ROOT}/local_plugin/foo.txt" | cut -d' ' -f1)
  run_doctor --fix

  # Local-edits remain, so exit 1, and only the local plugin is still reported.
  assert_equals 1 "${DOCTOR_RC}"
  assert_contains "local_plugin" "${DOCTOR_OUT}"
  assert_not_contains "interrupted_plugin" "${DOCTOR_OUT}"
  assert_equals "hello" "$(cat "${NVIM_LAZY_ROOT}/interrupted_plugin/foo.txt")"
  assert_equals "hello" "$(cat "${NVIM_LAZY_ROOT}/doctags_plugin/foo.txt")"
  assert_equals "hello" "$(cat "${NVIM_LAZY_ROOT}/sp ace_plugin/foo.txt")"
  assert_equals "spaced" "$(cat "${NVIM_LAZY_ROOT}/sp ace_plugin/inner file.txt")"
  after=$(sha256sum "${NVIM_LAZY_ROOT}/local_plugin/foo.txt" | cut -d' ' -f1)
  assert_equals "${before}" "${after}"
}

function test_update_invokes_nvim_with_repaired_names() {
  run_doctor --update

  assert_equals 1 "${DOCTOR_RC}"
  log="$(cat "${NVIM_LOG}")"
  assert_contains "interrupted_plugin" "${log}"
  assert_contains "doctags_plugin" "${log}"
  assert_contains "sp ace_plugin" "${log}"
  assert_not_contains "clean_plugin" "${log}"
  assert_not_contains "local_plugin" "${log}"
  assert_contains "+Lazy! update" "${log}"
  # The fix ran before the update, so the files are back.
  assert_equals "hello" "$(cat "${NVIM_LAZY_ROOT}/interrupted_plugin/foo.txt")"
}

function test_update_rebreak_triggers_second_fix_and_exits_one() {
  export FAKE_NVIM_REBREAK="${NVIM_LAZY_ROOT}/interrupted_plugin"
  run_doctor --update

  assert_equals 1 "${DOCTOR_RC}"
  # Second --fix restored the re-broken repo at its old HEAD.
  assert_equals "hello" "$(cat "${NVIM_LAZY_ROOT}/interrupted_plugin/foo.txt")"
}

function test_unknown_flag_exits_two() {
  run_doctor --bogus

  assert_equals 2 "${DOCTOR_RC}"
  assert_contains "unknown arg" "${DOCTOR_OUT}"
}

function test_help_exits_zero() {
  run_doctor --help

  assert_equals 0 "${DOCTOR_RC}"
  assert_contains "Interrupted-checkout" "${DOCTOR_OUT}"
  assert_contains ":Lazy update" "${DOCTOR_OUT}"
}
