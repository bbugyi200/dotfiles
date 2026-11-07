#!/bin/bash

#################################################################################
# Tests for `cronctl sync`, the only crontab installer, and for the            #
# run_onchange hook that runs it. Every run uses a fake HOME and a fake         #
# crontab on PATH, under `env -i`; the real crontab is never touched.           #
#                                                                               #
# These use the chezmoi on PATH. athena runs chezmoi v2.13.1 and CI the latest  #
# release, so run them against both, e.g.                                       #
#   PATH="$HOME/.nix-profile/bin:$PATH" bashunit tests/bash/cron_sync_test.sh   #
#################################################################################

# Crontab lines hold literal "$HOME" on purpose.
# shellcheck disable=SC2016

REPO_ROOT="${PWD}"
SCRIPT="${REPO_ROOT}/home/bin/executable_cronctl"
HOOK_REL="home/.chezmoiscripts/run_onchange_after_sync_crontab.sh.tmpl"

BLOCK_V1='# BEGIN chezmoi-cron (machine: athena; source: cron: in home/.chezmoidata.yaml; manage with cronctl)
MAILTO=someone@example.com
# nightly: Nightly maintenance
30 3 * * * "$HOME/bin/cronrun" nightly '\''bob nightly'\''
# END chezmoi-cron'

BLOCK_V2='# BEGIN chezmoi-cron (machine: athena; source: cron: in home/.chezmoidata.yaml; manage with cronctl)
MAILTO=someone@example.com
# nightly: Nightly maintenance
45 3 * * * "$HOME/bin/cronrun" nightly '\''bob nightly --full'\''
@hourly "$HOME/bin/cronrun" hourly '\''echo "it'\''\'\'''\''s $(date +\%F)"'\''
# END chezmoi-cron'

# A legacy table with a trailing-whitespace line and an agent watchdog line.
FOREIGN_TABLE="$(printf '%s\n' \
  "# Edit this file to introduce tasks to be run by cron." \
  "#" \
  "DISPLAY=:0" \
  "MAILTO=old@example.com" \
  "# Nightly Bob maintenance" \
  "30 3 * * * bob nightly" \
  "0 * * * * pass_git_sync   " \
  "*/5 * * * * /usr/bin/true # sase-epic-watchdog:sase-1r2")"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  TEST_HOME="${TEST_TMP}/home"
  FAKE_BIN="${TEST_TMP}/bin"
  TABLE="${TEST_TMP}/table"
  CALLS="${TEST_TMP}/calls"
  OUT_FILE="${TEST_TMP}/stdout"
  ERR_FILE="${TEST_TMP}/stderr"
  STATE_DIR="${TEST_HOME}/.local/state/cron"
  CRON_CONFIG="${TEST_HOME}/.config/cron"
  SOURCE="${TEST_HOME}/.local/share/chezmoi"
  EMPTY_CONFIG="${TEST_TMP}/empty.yaml"
  : >"${EMPTY_CONFIG}"
  : >"${CALLS}"
  mkdir -p "${FAKE_BIN}" "${CRON_CONFIG}" "${SOURCE}/home/bin"
  HOSTNAME_OVERRIDE="athena"
  LOCK_IMPL=""
  LOCK_TIMEOUT="5"
  RUN_ENV=()
  RUN_PREFIX=()
  HOLDER_PID=""
  UNWRITABLE_DIR=""
  write_fake_crontab
  write_source

  # The default chezmoi source of the fake HOME, so sync can resolve the
  # machine through the cron-machine partial.
  cp "${REPO_ROOT}/.chezmoiroot" "${SOURCE}/"
  cp -R "${REPO_ROOT}/home/.chezmoitemplates" "${SOURCE}/home/"
  mkdir -p "${SOURCE}/home/dot_config/cron" "${SOURCE}/home/.chezmoiscripts"
  cp "${REPO_ROOT}/home/dot_config/cron/managed.crontab.tmpl" \
    "${REPO_ROOT}/home/dot_config/cron/retire.crontab.tmpl" "${SOURCE}/home/dot_config/cron/"
  cp "${REPO_ROOT}/${HOOK_REL}" "${SOURCE}/home/.chezmoiscripts/"
  cp "${SCRIPT}" "${SOURCE}/home/bin/executable_cronctl"
}

function tear_down() {
  if [[ -n "${HOLDER_PID}" ]]; then
    kill "${HOLDER_PID}" 2>/dev/null || true
    wait "${HOLDER_PID}" 2>/dev/null || true
  fi
  if [[ -n "${UNWRITABLE_DIR}" ]]; then
    chmod 755 "${UNWRITABLE_DIR}" 2>/dev/null || true
  fi
  rm -rf "${TEST_TMP}"
}

function require_chezmoi() {
  if ! command -v chezmoi >/dev/null 2>&1; then
    bashunit::skip "chezmoi is required to resolve the cron machine"
    return 1
  fi
}

# Writes the cron: data of the fake HOME's chezmoi source.
function write_source() {
  cat >"${SOURCE}/home/.chezmoidata.yaml" <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
    mac: [Kellys-MacBook-Pro]
  env:
    MAILTO: someone@example.com
  jobs:
    - name: nightly
      machines: [athena]
      schedule: "30 3 * * *"
      description: Nightly maintenance
      command: bob nightly
  retire:
    athena:
      - "30 3 * * * bob nightly"
EOF
}

# A fake crontab whose table lives in $FAKE_CRONTAB_TABLE (absent means "no
# crontab"). Every call is logged to $FAKE_CRONTAB_CALLS. Knobs:
#   FAKE_CRONTAB_DIALECT=debian       usage text advertises `-n` (dry run)
#   FAKE_CRONTAB_LIST_ERROR=<msg>     `crontab -l` fails with <msg>
#   FAKE_CRONTAB_MUTATE_ON_LIST="N.." the Nth `crontab -l` first appends a line
#   FAKE_CRONTAB_INSTALL_FAIL=1       installs fail like macOS TCC
#   FAKE_CRONTAB_MANGLE_INSTALLS=N    the first N installs store a changed table
function write_fake_crontab() {
  cat >"${FAKE_BIN}/crontab" <<'EOF'
#!/bin/bash
table="${FAKE_CRONTAB_TABLE}"
calls="${FAKE_CRONTAB_CALLS}"
bump() {
  local n=0
  [ -f "${calls}.$1" ] && n="$(cat "${calls}.$1")"
  n=$((n + 1))
  printf '%s\n' "${n}" >"${calls}.$1"
  printf '%s' "${n}"
}
case "$*" in
-h)
  printf 'crontab -h\n' >>"${calls}"
  if [ "${FAKE_CRONTAB_DIALECT:-}" = debian ]; then
    printf 'usage:\tcrontab [-u user] [-n] file\n\t-n\t(dry run: checks the syntax, then bails out)\n' >&2
  else
    printf 'crontab: illegal option -- h\nusage: crontab [-u user] file\n' >&2
  fi
  exit 1
  ;;
-l)
  printf 'crontab -l\n' >>"${calls}"
  n="$(bump list)"
  if [ -n "${FAKE_CRONTAB_LIST_ERROR:-}" ]; then
    printf '%s\n' "${FAKE_CRONTAB_LIST_ERROR}" >&2
    exit 1
  fi
  for m in ${FAKE_CRONTAB_MUTATE_ON_LIST:-}; do
    [ "${m}" = "${n}" ] && printf '# changed by someone else (list %s)\n' "${n}" >>"${table}"
  done
  if [ -f "${table}" ]; then
    cat "${table}"
  else
    printf 'no crontab for tester\n' >&2
    exit 1
  fi
  ;;
'-n -')
  printf 'crontab -n -\n' >>"${calls}"
  if grep -q '^99 ' -; then
    printf '"-":1: bad minute\nerrors in crontab file, can'\''t install.\n' >&2
    exit 1
  fi
  printf 'The syntax of the crontab file was successfully checked.\n'
  ;;
-)
  printf 'crontab -\n' >>"${calls}"
  n="$(bump install)"
  if [ -n "${FAKE_CRONTAB_INSTALL_FAIL:-}" ]; then
    cat >/dev/null
    printf 'crontab: tmp/tmp.123: Operation not permitted\n' >&2
    exit 1
  fi
  if [ "${n}" -le "${FAKE_CRONTAB_MANGLE_INSTALLS:-0}" ]; then
    { cat; printf '# mangled\n'; } >"${table}"
  else
    cat >"${table}"
  fi
  ;;
*)
  printf 'crontab UNEXPECTED %s\n' "$*" >>"${calls}"
  exit 64
  ;;
esac
EOF
  chmod +x "${FAKE_BIN}/crontab"
}

function write_table() {
  printf '%s\n' "$1" >"${TABLE}"
}

function write_managed() {
  printf '%s\n' "$1" >"${CRON_CONFIG}/managed.crontab"
}

function write_retire() {
  printf '%s\n' "$@" >"${CRON_CONFIG}/retire.crontab"
}

# Runs cronctl with a cron-like environment; sets RC, OUT_FILE, and ERR_FILE.
function run_cronctl() {
  ${RUN_PREFIX[@]+"${RUN_PREFIX[@]}"} env -i \
    HOME="${TEST_HOME}" \
    PATH="${FAKE_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    TMPDIR="${TEST_TMP}" \
    CRONCTL_CHEZMOI="$(command -v chezmoi)" \
    CRONCTL_HOSTNAME="${HOSTNAME_OVERRIDE}" \
    CRONCTL_LOCK_IMPL="${LOCK_IMPL}" \
    CRONCTL_LOCK_TIMEOUT="${LOCK_TIMEOUT}" \
    FAKE_CRONTAB_TABLE="${TABLE}" \
    FAKE_CRONTAB_CALLS="${CALLS}" \
    ${RUN_ENV[@]+"${RUN_ENV[@]}"} \
    "${BASH}" "${SCRIPT}" "$@" </dev/null >"${OUT_FILE}" 2>"${ERR_FILE}"
  RC=$?
}

# bound_runs <seconds>: kill every later run_cronctl after <seconds> (exit
# 124 from timeout, or 142 from perl's alarm on a Mac without timeout), so a
# regression that spins fails the test instead of hanging the suite.
function bound_runs() {
  if command -v timeout >/dev/null 2>&1; then
    RUN_PREFIX=(timeout "$1")
  else
    RUN_PREFIX=(perl -e 'alarm shift; exec @ARGV or die "exec: $!\n"' "$1")
  fi
}

function install_count() {
  grep -c '^crontab -$' "${CALLS}"
}

function backup_count() {
  if [[ -d "${STATE_DIR}/backups" ]]; then
    find "${STATE_DIR}/backups" -type f | wc -l | tr -d ' '
  else
    printf '0'
  fi
}

#############################
#  Installing               #
#############################
function test_first_install_puts_the_block_on_top_and_keeps_foreign_lines() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  : >"${CRON_CONFIG}/retire.crontab"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_same "$(printf '%s\n%s' "${BLOCK_V1}" "${FOREIGN_TABLE}")" "$(cat "${TABLE}")"
  assert_contains "cronctl sync: athena: inserted the managed block at the top (5 lines); removed 0 retire lines" \
    "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"
  assert_same "${BLOCK_V1}" "$(cat "${STATE_DIR}/installed.block")"
  assert_same "1" "$(install_count)"
  assert_same "1" "$(backup_count)"
  assert_same "${FOREIGN_TABLE}" "$(cat "${STATE_DIR}"/backups/crontab.*)"
}

function test_an_unchanged_table_is_a_byte_identical_no_op() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  run_cronctl sync
  assert_same "0" "${RC}"
  cp "${TABLE}" "${TEST_TMP}/after-first"
  : >"${CALLS}"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_empty "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"
  assert_same "0" "$(install_count)"
  assert_not_contains "crontab -n" "$(cat "${CALLS}")"
  assert_same "1" "$(backup_count)"
  cmp -s "${TEST_TMP}/after-first" "${TABLE}"
  assert_same "0" "$?"
}

function test_a_block_update_keeps_foreign_lines_in_place() {
  require_chezmoi || return 0
  write_table "$(printf '%s\n%s\n%s\n%s' "# above the block" "${BLOCK_V1}" \
    "*/5 * * * * /usr/bin/true # sase-epic-watchdog:sase-1r2" "# below the block")"
  write_managed "${BLOCK_V2}"
  printf '%s\n' "${BLOCK_V1}" >"${TEST_TMP}/v1"
  mkdir -p "${STATE_DIR}"
  cp "${TEST_TMP}/v1" "${STATE_DIR}/installed.block"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_same "$(printf '%s\n%s\n%s\n%s' "# above the block" "${BLOCK_V2}" \
    "*/5 * * * * /usr/bin/true # sase-epic-watchdog:sase-1r2" "# below the block")" \
    "$(cat "${TABLE}")"
  assert_contains "updated the managed block in place (6 lines)" "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"
  assert_same "${BLOCK_V2}" "$(cat "${STATE_DIR}/installed.block")"
}

# A block file whose "# END chezmoi-cron" has no final newline (a trimmed
# partial, or a --block saved from $(cronctl render ...)) must not swallow
# the line after it.
function test_an_unterminated_block_on_top_keeps_the_next_line_intact() {
  require_chezmoi || return 0
  printf '%s' "${BLOCK_V1}" >"${CRON_CONFIG}/managed.crontab"
  write_table "${FOREIGN_TABLE}"
  : >"${CRON_CONFIG}/retire.crontab"

  run_cronctl sync

  assert_same "0" "${RC}"
  printf '%s\n%s\n' "${BLOCK_V1}" "${FOREIGN_TABLE}" >"${TEST_TMP}/want"
  assert_files_equals "${TEST_TMP}/want" "${TABLE}"
  assert_contains "inserted the managed block at the top (5 lines)" "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"
  printf '%s\n' "${BLOCK_V1}" >"${TEST_TMP}/want.block"
  assert_files_equals "${TEST_TMP}/want.block" "${STATE_DIR}/installed.block"
  : >"${CALLS}"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_empty "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"
  assert_same "0" "$(install_count)"
  assert_files_equals "${TEST_TMP}/want" "${TABLE}"
}

function test_an_unterminated_block_in_place_keeps_the_next_line_intact() {
  require_chezmoi || return 0
  write_table "$(printf '%s\n%s\n%s' "# above the block" "${BLOCK_V1}" "MAILTO=old@example.com")"
  printf '%s' "${BLOCK_V2}" >"${CRON_CONFIG}/managed.crontab"
  mkdir -p "${STATE_DIR}"
  printf '%s\n' "${BLOCK_V1}" >"${STATE_DIR}/installed.block"

  run_cronctl sync

  assert_same "0" "${RC}"
  printf '%s\n%s\n%s\n' "# above the block" "${BLOCK_V2}" "MAILTO=old@example.com" \
    >"${TEST_TMP}/want"
  assert_files_equals "${TEST_TMP}/want" "${TABLE}"
  assert_contains "updated the managed block in place (6 lines)" "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"
  : >"${CALLS}"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_empty "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"
  assert_same "0" "$(install_count)"
  assert_files_equals "${TEST_TMP}/want" "${TABLE}"

  # A dry run against it reports no changes and no hand edit either.
  run_cronctl sync --dry-run

  assert_same "0" "${RC}"
  assert_contains "no changes: the crontab already matches" "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"
}

function test_no_crontab_reads_as_an_empty_table() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  rm -f "${TABLE}"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_same "${BLOCK_V1}" "$(cat "${TABLE}")"
  assert_contains "inserted the managed block at the top" "$(cat "${OUT_FILE}")"
}

function test_a_list_failure_is_not_treated_as_an_empty_table() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  RUN_ENV=(FAKE_CRONTAB_LIST_ERROR="crontab: Operation not permitted")

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_contains "crontab -l failed (exit 1), so the crontab is left untouched" \
    "$(cat "${ERR_FILE}")"
  assert_contains "Operation not permitted" "$(cat "${ERR_FILE}")"
  assert_same "0" "$(install_count)"
  assert_same "${FOREIGN_TABLE}" "$(cat "${TABLE}")"
}

function assert_markers_refused() {
  write_table "$1"
  cp "${TABLE}" "${TEST_TMP}/before"
  : >"${CALLS}"

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_contains "refusing to sync: the crontab has $2" "$(cat "${ERR_FILE}")"
  assert_same "0" "$(install_count)"
  cmp -s "${TEST_TMP}/before" "${TABLE}"
  assert_same "0" "$?"
}

function test_corrupt_markers_are_refused() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"

  assert_markers_refused "$(printf '%s\n%s' "${BLOCK_V1}" "${BLOCK_V1}")" \
    "2 BEGIN markers and 2 END markers"
  assert_markers_refused "$(printf '%s\n%s' "# BEGIN chezmoi-cron (machine: athena)" \
    "${BLOCK_V1}")" "2 BEGIN markers and 1 END marker"
  assert_markers_refused "$(printf '%s\n%s' "# END chezmoi-cron" \
    "# BEGIN chezmoi-cron (machine: athena)")" "1 BEGIN marker and 1 END marker"
  assert_markers_refused "$(printf '%s\n%s' "# BEGIN chezmoi-cron (machine: athena)" \
    "0 * * * * true")" "1 BEGIN marker and 0 END markers"
  assert_markers_refused "$(printf '%s\n%s' "0 * * * * true" "# END chezmoi-cron  ")" \
    "0 BEGIN markers and 1 END marker"
}

function test_a_failed_verify_restores_the_backup() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  RUN_ENV=(FAKE_CRONTAB_MANGLE_INSTALLS=1)

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_contains "does not read back as the candidate" "$(cat "${ERR_FILE}")"
  assert_contains "restored the previous crontab from ${STATE_DIR}/backups/crontab." \
    "$(cat "${ERR_FILE}")"
  assert_same "${FOREIGN_TABLE}" "$(cat "${TABLE}")"
  assert_same "2" "$(install_count)"
  assert_file_not_exists "${STATE_DIR}/installed.block"
}

function test_a_failed_install_leaves_the_table_and_hints_on_macos_tcc() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  RUN_ENV=(FAKE_CRONTAB_INSTALL_FAIL=1)

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_contains "crontab install failed (exit 1)" "$(cat "${ERR_FILE}")"
  assert_contains "the crontab is unchanged (backup: ${STATE_DIR}/backups/crontab." \
    "$(cat "${ERR_FILE}")"
  assert_same "${FOREIGN_TABLE}" "$(cat "${TABLE}")"
  assert_same "1" "$(install_count)"
  assert_file_not_exists "${STATE_DIR}/installed.block"
}

function test_a_hand_edit_inside_the_block_warns_and_is_overwritten() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  run_cronctl sync
  assert_same "0" "${RC}"
  write_table "$(printf '%s\n' "${BLOCK_V1}" | sed 's/^30 3 /15 3 /')
${FOREIGN_TABLE}"

  run_cronctl sync --dry-run

  assert_same "0" "${RC}"
  assert_contains "cronctl: WARNING: inside the block is being overwritten" "$(cat "${ERR_FILE}")"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_contains "cronctl: WARNING: differs from the block cronctl last installed: a hand edit" \
    "$(cat "${ERR_FILE}")"
  assert_contains 'cronctl: WARNING: +15 3 * * * "$HOME/bin/cronrun" nightly' "$(cat "${ERR_FILE}")"
  assert_same "$(printf '%s\n%s' "${BLOCK_V1}" "${FOREIGN_TABLE}")" "$(cat "${TABLE}")"
}

function test_a_changed_block_without_a_hand_edit_does_not_warn() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  run_cronctl sync
  write_managed "${BLOCK_V2}"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_empty "$(cat "${ERR_FILE}")"
}

function test_retire_removes_only_exact_matches_outside_the_block() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  # The block itself holds the retire lines MAILTO=someone@example.com and
  # 30 3 ...; only the outside copies may go.
  write_table "$(printf '%s\n' \
    "MAILTO=someone@example.com" \
    "${BLOCK_V1}" \
    "# Nightly Bob maintenance" \
    "30 3 * * * bob nightly   " \
    " 30 3 * * * bob nightly" \
    "30 3 * * * bob nightly --full" \
    "0 * * * * pass_git_sync" \
    "*/5 * * * * /usr/bin/true # sase-epic-watchdog:sase-1r2")"
  write_retire "MAILTO=someone@example.com" "# Nightly Bob maintenance" \
    "30 3 * * * bob nightly" "0 * * * * pass_git_sync  " \
    '30 3 * * * "$HOME/bin/cronrun" nightly '\''bob nightly'\'''

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_same "$(printf '%s\n' \
    "${BLOCK_V1}" \
    " 30 3 * * * bob nightly" \
    "30 3 * * * bob nightly --full" \
    "*/5 * * * * /usr/bin/true # sase-epic-watchdog:sase-1r2")" "$(cat "${TABLE}")"
  assert_contains "updated the managed block in place (5 lines); removed 4 retire lines" \
    "$(cat "${OUT_FILE}")"
}

function test_retire_and_enrolment_happen_in_one_install() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  write_retire "MAILTO=old@example.com" "# Nightly Bob maintenance" "30 3 * * * bob nightly"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_same "1" "$(install_count)"
  assert_same "$(printf '%s\n' "${BLOCK_V1}" \
    "# Edit this file to introduce tasks to be run by cron." "#" "DISPLAY=:0" \
    "0 * * * * pass_git_sync   " \
    "*/5 * * * * /usr/bin/true # sase-epic-watchdog:sase-1r2")" "$(cat "${TABLE}")"
  assert_contains "removed 3 retire lines" "$(cat "${OUT_FILE}")"
}

#############################
#  Dry runs and previews    #
#############################
function test_dry_run_installs_nothing_and_writes_no_state() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  write_retire "30 3 * * * bob nightly"

  run_cronctl sync --dry-run

  assert_same "0" "${RC}"
  local out
  out="$(cat "${OUT_FILE}")"
  assert_contains "cronctl sync --dry-run: athena (block from ${CRON_CONFIG}/managed.crontab); nothing is changed" "${out}"
  assert_contains "--- crontab (live)" "${out}"
  assert_contains "+++ crontab (candidate)" "${out}"
  assert_contains "+# BEGIN chezmoi-cron (machine: athena;" "${out}"
  assert_contains "-30 3 * * * bob nightly" "${out}"
  assert_contains "retire lines that would be removed (1):" "${out}"
  assert_same "0" "$(install_count)"
  assert_same "${FOREIGN_TABLE}" "$(cat "${TABLE}")"
  assert_directory_not_exists "${STATE_DIR}"
}

function test_dry_run_reports_no_changes_when_in_sync() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${BLOCK_V1}"

  run_cronctl sync --dry-run

  assert_same "0" "${RC}"
  assert_contains "no changes: the crontab already matches" "$(cat "${OUT_FILE}")"
  assert_directory_not_exists "${STATE_DIR}"
}

function test_block_previews_another_rendering_and_needs_dry_run() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${BLOCK_V1}"
  printf '%s\n' "${BLOCK_V2}" >"${TEST_TMP}/checkout.block"
  printf '%s\n' "MAILTO=someone@example.com" >"${TEST_TMP}/checkout.retire"

  run_cronctl sync --block "${TEST_TMP}/checkout.block"
  assert_same "2" "${RC}"
  assert_contains "--block needs --dry-run" "$(cat "${ERR_FILE}")"

  run_cronctl sync --dry-run --retire "${TEST_TMP}/checkout.retire"
  assert_same "0" "${RC}"
  run_cronctl sync --retire "${TEST_TMP}/checkout.retire"
  assert_same "2" "${RC}"

  run_cronctl sync --dry-run --block "${TEST_TMP}/checkout.block" \
    --retire "${TEST_TMP}/checkout.retire"

  assert_same "0" "${RC}"
  assert_contains "athena (block from ${TEST_TMP}/checkout.block)" "$(cat "${OUT_FILE}")"
  assert_contains "+45 3 * * * " "$(cat "${OUT_FILE}")"
  assert_same "0" "$(install_count)"
  assert_same "${BLOCK_V1}" "$(cat "${TABLE}")"
}

function test_block_for_another_machine_is_refused() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  printf '%s\n' "${BLOCK_V1}" | sed 's/machine: athena;/machine: mac;/' >"${TEST_TMP}/mac.block"

  run_cronctl sync --dry-run --block "${TEST_TMP}/mac.block"

  assert_same "2" "${RC}"
  assert_contains "holds the block for mac, but this host (athena) is athena" \
    "$(cat "${ERR_FILE}")"
}

#############################
#  Resolution and guards    #
#############################
function test_an_unknown_machine_is_left_untouched() {
  require_chezmoi || return 0
  HOSTNAME_OVERRIDE="stranger"
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_contains "this host (stranger) is not enrolled in cron.machines" "$(cat "${ERR_FILE}")"
  assert_empty "$(cat "${CALLS}")"
  assert_same "${FOREIGN_TABLE}" "$(cat "${TABLE}")"
}

function test_a_missing_managed_block_is_left_untouched() {
  require_chezmoi || return 0
  write_table "${FOREIGN_TABLE}"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_contains "managed.crontab is missing (run chezmoi apply first)" "$(cat "${ERR_FILE}")"
  assert_empty "$(cat "${CALLS}")"
}

function test_a_managed_block_for_another_machine_is_refused() {
  require_chezmoi || return 0
  HOSTNAME_OVERRIDE="Kellys-MacBook-Pro"
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_contains "holds the block for athena, but this host (Kellys-MacBook-Pro) is mac" \
    "$(cat "${ERR_FILE}")"
  assert_empty "$(cat "${CALLS}")"
}

function test_a_malformed_managed_block_is_refused() {
  require_chezmoi || return 0
  write_managed "$(printf '%s\n' "${BLOCK_V1}" | sed '$d')"
  write_table "${FOREIGN_TABLE}"

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_contains "is not one marked block" "$(cat "${ERR_FILE}")"
  assert_empty "$(cat "${CALLS}")"
}

function test_invalid_data_aborts_before_reading_the_table() {
  require_chezmoi || return 0
  sed -i.bak 's/schedule: "30 3 \* \* \*"/schedule: "30 3 * *"/' \
    "${SOURCE}/home/.chezmoidata.yaml"
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"

  run_cronctl sync

  assert_same "2" "${RC}"
  assert_contains "cronctl: invalid cron: data: cron.jobs[0] (nightly): invalid schedule" \
    "$(cat "${ERR_FILE}")"
  assert_empty "$(cat "${CALLS}")"
}

function test_the_native_syntax_check_runs_on_stdin_and_blocks_bad_tables() {
  require_chezmoi || return 0
  RUN_ENV=(FAKE_CRONTAB_DIALECT=debian)
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_contains "crontab -n -" "$(cat "${CALLS}")"
  assert_not_contains "UNEXPECTED" "$(cat "${CALLS}")"

  : >"${CALLS}"
  write_managed "$(printf '%s\n' "${BLOCK_V1}" | sed 's/^30 3 /99 3 /')"
  cp "${TABLE}" "${TEST_TMP}/before"

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_contains "crontab -n rejects the candidate crontab" "$(cat "${ERR_FILE}")"
  assert_contains "bad minute" "$(cat "${ERR_FILE}")"
  assert_same "0" "$(install_count)"
  cmp -s "${TEST_TMP}/before" "${TABLE}"
  assert_same "0" "$?"
}

function test_a_table_changed_mid_sync_is_rebuilt_once() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  RUN_ENV=(FAKE_CRONTAB_MUTATE_ON_LIST=2)

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_contains "the crontab changed while syncing; rebuilding once" "$(cat "${ERR_FILE}")"
  assert_same "$(printf '%s\n%s\n%s' "${BLOCK_V1}" "${FOREIGN_TABLE}" \
    "# changed by someone else (list 2)")" "$(cat "${TABLE}")"
  assert_same "1" "$(install_count)"
}

function test_a_table_that_keeps_changing_is_left_alone() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  RUN_ENV=(FAKE_CRONTAB_MUTATE_ON_LIST="2 3")

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_contains "the crontab changed twice while syncing; nothing changed" \
    "$(cat "${ERR_FILE}")"
  assert_same "0" "$(install_count)"
}

function test_backups_keep_the_newest_twenty() {
  require_chezmoi || return 0
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  mkdir -p "${STATE_DIR}/backups"
  local i
  for ((i = 10; i < 35; i++)); do
    printf 'old %s\n' "${i}" >"${STATE_DIR}/backups/crontab.20200101T0000${i}Z"
  done

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_same "20" "$(backup_count)"
  assert_file_not_exists "${STATE_DIR}/backups/crontab.20200101T000015Z"
  assert_file_exists "${STATE_DIR}/backups/crontab.20200101T000016Z"
}

#############################
#  Locking                  #
#############################
function test_the_mkdir_lock_fallback_works_and_releases() {
  require_chezmoi || return 0
  LOCK_IMPL="mkdir"
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_contains "inserted the managed block" "$(cat "${OUT_FILE}")"
  assert_directory_not_exists "${STATE_DIR}/sync.lock.d"
}

function test_the_mkdir_lock_fallback_breaks_stale_locks() {
  require_chezmoi || return 0
  LOCK_IMPL="mkdir"
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  local dead_pid
  bash -c 'exit 0' &
  dead_pid=$!
  wait "${dead_pid}"
  mkdir -p "${STATE_DIR}/sync.lock.d"
  printf '%s\n' "${dead_pid}" >"${STATE_DIR}/sync.lock.d/pid"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_contains "inserted the managed block" "$(cat "${OUT_FILE}")"
  assert_directory_not_exists "${STATE_DIR}/sync.lock.d"
}

function test_the_mkdir_lock_fallback_waits_for_a_live_holder() {
  require_chezmoi || return 0
  LOCK_IMPL="mkdir"
  LOCK_TIMEOUT="1"
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  bash -c 'exec -a cronctl-lock-holder sleep 30' </dev/null >/dev/null 2>&1 &
  HOLDER_PID=$!
  mkdir -p "${STATE_DIR}/sync.lock.d"
  printf '%s\n' "${HOLDER_PID}" >"${STATE_DIR}/sync.lock.d/pid"

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_contains "another cronctl sync still holds" "$(cat "${ERR_FILE}")"
  assert_same "0" "$(install_count)"
  assert_same "${FOREIGN_TABLE}" "$(cat "${TABLE}")"
  assert_same "${HOLDER_PID}" "$(cat "${STATE_DIR}/sync.lock.d/pid")"

  # A dry run changes nothing, so it does not wait for the lock.
  run_cronctl sync --dry-run
  assert_same "0" "${RC}"
}

function test_the_mkdir_lock_fails_at_once_when_a_file_has_its_name() {
  require_chezmoi || return 0
  LOCK_IMPL="mkdir"
  LOCK_TIMEOUT="30"
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  mkdir -p "${STATE_DIR}"
  printf 'not a lock\n' >"${STATE_DIR}/sync.lock.d"
  bound_runs 15
  local start="${SECONDS}"

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_less_than "10" "$((SECONDS - start))"
  assert_contains "cannot take the sync lock in ${STATE_DIR}" "$(cat "${ERR_FILE}")"
  assert_same "0" "$(install_count)"
  assert_same "${FOREIGN_TABLE}" "$(cat "${TABLE}")"
}

function test_the_mkdir_lock_gives_up_on_an_unwritable_state_dir() {
  require_chezmoi || return 0
  if [[ "$(id -u)" = 0 ]]; then
    bashunit::skip "root writes to a mode 555 directory anyway"
    return 0
  fi
  LOCK_IMPL="mkdir"
  LOCK_TIMEOUT="2"
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  mkdir -p "${STATE_DIR}"
  chmod 555 "${STATE_DIR}"
  UNWRITABLE_DIR="${STATE_DIR}"
  bound_runs 20
  local start="${SECONDS}"

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_less_or_equal_than "$((LOCK_TIMEOUT + 6))" "$((SECONDS - start))"
  assert_contains "cannot take the sync lock in ${STATE_DIR}" "$(cat "${ERR_FILE}")"
  assert_same "0" "$(install_count)"
  assert_same "${FOREIGN_TABLE}" "$(cat "${TABLE}")"
}

function test_the_mkdir_lock_breaks_a_lock_whose_pid_is_now_another_bash() {
  require_chezmoi || return 0
  LOCK_IMPL="mkdir"
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  # A recycled pid: a live bash that is not cronctl. The trailing ":" keeps
  # bash from exec-ing sleep, so ps shows the bash command line.
  bash -c 'sleep 30; :' </dev/null >/dev/null 2>&1 &
  HOLDER_PID=$!
  local i command_line=""
  for ((i = 0; i < 50; i++)); do
    command_line="$(ps -ww -p "${HOLDER_PID}" -o command= 2>/dev/null)"
    [[ "${command_line}" == *"sleep 30; :"* ]] && break
    sleep 0.1
  done
  assert_contains "bash" "${command_line}"
  assert_not_contains "cronctl" "${command_line}"
  mkdir -p "${STATE_DIR}/sync.lock.d"
  printf '%s\n' "${HOLDER_PID}" >"${STATE_DIR}/sync.lock.d/pid"

  run_cronctl sync

  assert_same "0" "${RC}"
  assert_contains "inserted the managed block" "$(cat "${OUT_FILE}")"
  assert_same "1" "$(install_count)"
  assert_directory_not_exists "${STATE_DIR}/sync.lock.d"
  kill -0 "${HOLDER_PID}"
  assert_same "0" "$?"
}

function test_the_flock_lock_waits_for_a_live_holder() {
  require_chezmoi || return 0
  if ! command -v flock >/dev/null 2>&1; then
    bashunit::skip "flock is not installed (macOS uses the mkdir lock)"
    return 0
  fi
  LOCK_IMPL="flock"
  LOCK_TIMEOUT="1"
  # Homebrew's flock lives outside the default run PATH.
  RUN_ENV=(PATH="${FAKE_BIN}:$(dirname "$(command -v flock)"):/usr/bin:/bin:/usr/sbin:/sbin")
  write_managed "${BLOCK_V1}"
  write_table "${FOREIGN_TABLE}"
  mkdir -p "${STATE_DIR}"
  # The holder execs sleep while holding the lock, so killing it frees the lock.
  bash -c 'exec 9>>"$1"; flock 9; touch "$2"; exec sleep 30' _ \
    "${STATE_DIR}/sync.lock" "${TEST_TMP}/held" </dev/null >/dev/null 2>&1 &
  HOLDER_PID=$!
  local i
  for ((i = 0; i < 50; i++)); do
    [[ -e "${TEST_TMP}/held" ]] && break
    sleep 0.1
  done

  run_cronctl sync

  assert_same "1" "${RC}"
  assert_contains "another cronctl sync still holds" "$(cat "${ERR_FILE}")"
  assert_same "0" "$(install_count)"
}

#############################
#  The run_onchange hook    #
#############################
# Renders the hook of the fake HOME's source as if .chezmoi.hostname were $1.
function render_hook() {
  sed "s/\.chezmoi\.hostname/\"$1\"/" "${SOURCE}/${HOOK_REL}" |
    chezmoi --config "${EMPTY_CONFIG}" --source "${SOURCE}" execute-template
}

function test_the_hook_renders_empty_for_an_unknown_hostname() {
  require_chezmoi || return 0

  local hook
  hook="$(render_hook stranger)"

  assert_same "0" "$?"
  assert_empty "$(printf '%s' "${hook}" | tr -d '[:space:]')"
}

function test_the_hook_carries_the_block_retire_lines_and_cronctl_hash() {
  require_chezmoi || return 0

  local hook sha
  hook="$(render_hook athena)"
  if command -v sha256sum >/dev/null 2>&1; then
    sha="$(sha256sum "${SCRIPT}" | cut -d' ' -f1)"
  else
    sha="$(shasum -a 256 "${SCRIPT}" | cut -d' ' -f1)"
  fi

  assert_same "#!/bin/bash" "$(printf '%s\n' "${hook}" | head -n 1)"
  assert_contains "# BEGIN chezmoi-cron (machine: athena;" "${hook}"
  assert_contains '30 3 * * * "$HOME/bin/cronrun" nightly '\''bob nightly'\''' "${hook}"
  assert_contains "$(printf '# retire:\n30 3 * * * bob nightly\nCHEZMOI_CRON_INPUTS_END')" "${hook}"
  assert_contains "# cronctl sha256: ${sha}" "${hook}"
  assert_same 'exec "$HOME/bin/cronctl" sync' "$(printf '%s\n' "${hook}" | tail -n 1)"
  assert_not_contains "machine: mac" "${hook}"
}

function test_the_hook_runs_cronctl_sync_and_nothing_else() {
  require_chezmoi || return 0
  render_hook athena >"${TEST_TMP}/hook.sh"
  mkdir -p "${TEST_HOME}/bin"
  cat >"${TEST_HOME}/bin/cronctl" <<'EOF'
#!/bin/bash
printf 'cronctl %s\n' "$*" >>"${HOME}/hook-calls"
EOF
  chmod +x "${TEST_HOME}/bin/cronctl"

  env -i HOME="${TEST_HOME}" PATH="/usr/bin:/bin" "${BASH}" "${TEST_TMP}/hook.sh" \
    </dev/null >"${OUT_FILE}" 2>"${ERR_FILE}"

  assert_same "0" "$?"
  assert_same "cronctl sync" "$(cat "${TEST_HOME}/hook-calls")"
  assert_empty "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${ERR_FILE}")"
}

function test_the_hook_changes_with_the_block_the_retire_lines_and_cronctl() {
  require_chezmoi || return 0
  local base
  base="$(render_hook athena)"

  sed -i.bak 's/command: bob nightly/command: bob nightly --full/' \
    "${SOURCE}/home/.chezmoidata.yaml"
  assert_not_same "${base}" "$(render_hook athena)"
  cp "${SOURCE}/home/.chezmoidata.yaml.bak" "${SOURCE}/home/.chezmoidata.yaml"
  assert_same "${base}" "$(render_hook athena)"

  printf '      - "0 * * * * pass_git_sync"\n' >>"${SOURCE}/home/.chezmoidata.yaml"
  assert_not_same "${base}" "$(render_hook athena)"
  cp "${SOURCE}/home/.chezmoidata.yaml.bak" "${SOURCE}/home/.chezmoidata.yaml"

  printf '# changed\n' >>"${SOURCE}/home/bin/executable_cronctl"
  assert_not_same "${base}" "$(render_hook athena)"
}

# End to end: chezmoi apply writes managed.crontab, retire.crontab, and
# ~/bin/cronctl, then runs the hook, whose cronctl sync installs the block
# into the fake crontab. The hook only re-runs when this machine's inputs
# change.
function test_chezmoi_apply_converges_the_crontab_through_the_hook() {
  require_chezmoi || return 0
  local chezmoi hostname
  chezmoi="$(command -v chezmoi)"
  hostname="$(chezmoi --config "${EMPTY_CONFIG}" execute-template '{{ .chezmoi.hostname }}')"
  sed -i.bak "s/athena: \[athena\]/athena: [\"${hostname}\"]/" "${SOURCE}/home/.chezmoidata.yaml"
  if [[ "${hostname}" == "Kellys-MacBook-Pro" ]]; then
    sed -i.bak 's/mac: \[Kellys-MacBook-Pro\]/mac: [other-mac]/' "${SOURCE}/home/.chezmoidata.yaml"
  fi
  rm -f "${SOURCE}/home/.chezmoidata.yaml.bak"
  write_table "${FOREIGN_TABLE}"
  local apply=(
    env -i HOME="${TEST_HOME}" PATH="${FAKE_BIN}:/usr/bin:/bin:/usr/sbin:/sbin"
    TMPDIR="${TEST_TMP}" CRONCTL_CHEZMOI="${chezmoi}"
    FAKE_CRONTAB_TABLE="${TABLE}" FAKE_CRONTAB_CALLS="${CALLS}"
    "${chezmoi}" apply --force
  )

  "${apply[@]}" </dev/null >"${OUT_FILE}" 2>"${ERR_FILE}"

  assert_same "0" "$?"
  assert_contains "cronctl sync: athena: inserted the managed block at the top (5 lines); removed 1 retire line" \
    "$(cat "${OUT_FILE}")"
  assert_same "$(printf '%s\n' "${BLOCK_V1}" "# Edit this file to introduce tasks to be run by cron." \
    "#" "DISPLAY=:0" "MAILTO=old@example.com" "# Nightly Bob maintenance" \
    "0 * * * * pass_git_sync   " "*/5 * * * * /usr/bin/true # sase-epic-watchdog:sase-1r2")" \
    "$(cat "${TABLE}")"
  assert_same "1" "$(install_count)"

  # Unchanged inputs: chezmoi does not re-run the hook.
  : >"${CALLS}"
  "${apply[@]}" </dev/null >"${OUT_FILE}" 2>"${ERR_FILE}"
  assert_same "0" "$?"
  assert_empty "$(cat "${CALLS}")"

  # A changed job re-runs it and updates the block in place.
  sed -i.bak 's/schedule: "30 3 \* \* \*"/schedule: "45 3 * * *"/' \
    "${SOURCE}/home/.chezmoidata.yaml"
  "${apply[@]}" </dev/null >"${OUT_FILE}" 2>"${ERR_FILE}"
  assert_same "0" "$?"
  assert_contains "updated the managed block in place" "$(cat "${OUT_FILE}")"
  assert_contains '45 3 * * * "$HOME/bin/cronrun" nightly' "$(cat "${TABLE}")"
  assert_contains "# sase-epic-watchdog:sase-1r2" "$(cat "${TABLE}")"
}
