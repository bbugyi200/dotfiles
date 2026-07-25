#!/bin/bash

#################################################################################
# Regression tests for the `tmp_trash_empty` backstop.                          #
#                                                                               #
# Trash directories that live on the /tmp tmpfs hold "deleted" data in RAM and  #
# reclaim nothing, so `tmp_trash_empty` must find them under both /tmp and      #
# $TMPDIR and hand each one to `trash-empty`.                                   #
#                                                                               #
# `trash-empty` is stubbed so the arguments the script builds can be inspected  #
# without touching any real trash directory.                                    #
#################################################################################

TRASH_SCRIPT="${PWD}/home/bin/executable_tmp_trash_empty"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  CALLS_FILE="${TEST_TMP}/calls.txt"
  CACHE_DIR="${TEST_TMP}/cache"

  mkdir -p "${FAKE_BIN}" "${CACHE_DIR}"

  # Stub trash-empty: append the full argument list to a log and exit clean.
  cat > "${FAKE_BIN}/trash-empty" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >>"${CALLS_FILE}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/trash-empty"

  UID_NUM="$(id -u)"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

# Run the script with the stubbed trash-empty first on PATH and a throwaway
# cache dir so the --periodic stamp never touches the real one.
function run_tmp_trash_empty() {
  PATH="${FAKE_BIN}:${PATH}" \
    CALLS_FILE="${CALLS_FILE}" \
    XDG_CACHE_HOME="${CACHE_DIR}" \
    bash "${TRASH_SCRIPT}" "$@"
}

function calls() {
  cat "${CALLS_FILE}" 2> /dev/null
}

function test_purges_tmpdir_trash_dir() {
  local tmpdir="${TEST_TMP}/mytmp"
  mkdir -p "${tmpdir}/.Trash-${UID_NUM}"

  TMPDIR="${tmpdir}" run_tmp_trash_empty

  assert_contains "--trash-dir ${tmpdir}/.Trash-${UID_NUM} 0" "$(calls)"
}

function test_purges_alternate_spec_layout() {
  local tmpdir="${TEST_TMP}/mytmp"
  mkdir -p "${tmpdir}/.Trash/${UID_NUM}"

  TMPDIR="${tmpdir}" run_tmp_trash_empty

  assert_contains "--trash-dir ${tmpdir}/.Trash/${UID_NUM} 0" "$(calls)"
}

function test_skips_trash_dirs_that_do_not_exist() {
  local tmpdir="${TEST_TMP}/mytmp"
  mkdir -p "${tmpdir}"

  TMPDIR="${tmpdir}" run_tmp_trash_empty

  assert_not_contains "${tmpdir}" "$(calls)"
}

function test_dry_run_is_forwarded() {
  local tmpdir="${TEST_TMP}/mytmp"
  mkdir -p "${tmpdir}/.Trash-${UID_NUM}"

  TMPDIR="${tmpdir}" run_tmp_trash_empty --dry-run

  assert_contains "--dry-run" "$(calls)"
}

function test_dry_run_does_not_write_the_stamp() {
  local tmpdir="${TEST_TMP}/mytmp"
  mkdir -p "${tmpdir}/.Trash-${UID_NUM}"

  TMPDIR="${tmpdir}" run_tmp_trash_empty --dry-run

  assert_file_not_exists "${CACHE_DIR}/tmp_trash_empty.stamp"
}

function test_periodic_run_is_skipped_when_stamp_is_fresh() {
  local tmpdir="${TEST_TMP}/mytmp"
  mkdir -p "${tmpdir}/.Trash-${UID_NUM}"
  : > "${CACHE_DIR}/tmp_trash_empty.stamp"

  TMPDIR="${tmpdir}" run_tmp_trash_empty --periodic

  assert_empty "$(calls)"
}

function test_periodic_run_proceeds_when_stamp_is_stale() {
  local tmpdir="${TEST_TMP}/mytmp"
  mkdir -p "${tmpdir}/.Trash-${UID_NUM}"
  : > "${CACHE_DIR}/tmp_trash_empty.stamp"
  touch -d "2 days ago" "${CACHE_DIR}/tmp_trash_empty.stamp"

  TMPDIR="${tmpdir}" run_tmp_trash_empty --periodic

  assert_contains "--trash-dir ${tmpdir}/.Trash-${UID_NUM} 0" "$(calls)"
}

function test_unrecognized_argument_is_rejected() {
  assert_exit_code "2" "$(run_tmp_trash_empty --bogus 2>&1)"
}
