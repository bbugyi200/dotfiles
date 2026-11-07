#!/bin/bash

#################################################################################
# Tests for cronctl's offline commands (list, render, check) and its help and   #
# usage errors. They read cron: data only; crontab is a fake on PATH.           #
#                                                                               #
# These use the chezmoi on PATH. athena runs chezmoi v2.13.1 and CI the latest  #
# release, so run them against both, e.g.                                       #
#   PATH="$HOME/.nix-profile/bin:$PATH" bashunit tests/bash/cronctl_offline_test.sh
#################################################################################

# Crontab lines hold literal "$HOME" on purpose.
# shellcheck disable=SC2016

REPO_ROOT="${PWD}"
SCRIPT="${REPO_ROOT}/home/bin/executable_cronctl"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  TEST_HOME="${TEST_TMP}/home"
  FAKE_BIN="${TEST_TMP}/bin"
  OUT_FILE="${TEST_TMP}/stdout"
  ERR_FILE="${TEST_TMP}/stderr"
  EMPTY_CONFIG="${TEST_TMP}/empty.yaml"
  : >"${EMPTY_CONFIG}"
  mkdir -p "${TEST_HOME}" "${FAKE_BIN}"
  CRONTAB_DIALECT="plain"
  write_fake_crontab

  # A minimal copy of the source tree whose data each test replaces.
  FIXTURE="${TEST_TMP}/src"
  mkdir -p "${FIXTURE}/home"
  cp "${REPO_ROOT}/.chezmoiroot" "${FIXTURE}/"
  cp -R "${REPO_ROOT}/home/.chezmoitemplates" "${FIXTURE}/home/"
  write_fixture
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function require_chezmoi() {
  if ! command -v chezmoi >/dev/null 2>&1; then
    bashunit::skip "chezmoi is required to render the cron templates"
    return 1
  fi
}

function write_fixture() {
  cat >"${FIXTURE}/home/.chezmoidata.yaml" <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
    apollo: [apollo]
    mac: [Kellys-MacBook-Pro]
  env:
    MAILTO: someone@example.com
  jobs:
    - name: nightly
      machines: [athena]
      schedule: "30 3 * * *"
      description: Nightly maintenance
      command: . "$HOME/.config/nvm/nvm.sh"; bob nightly
    - name: everywhere
      machines: [all]
      schedule: "@hourly"
      command: 'echo "it''s $(date +%F)" | tee -a "$HOME/x.log"'
    - name: parked
      machines: [athena, mac]
      schedule: "0 4 * * *"
      enabled: false
      command: tman start
  retire:
    athena:
      - "30 3 * * * bob nightly"
      - "MAILTO=old@example.com"
    mac: []
EOF
}

# A fake crontab that only answers the syntax-check probe and `-n -`.
function write_fake_crontab() {
  cat >"${FAKE_BIN}/crontab" <<'EOF'
#!/bin/bash
case "$*" in
-h)
  if [ "${FAKE_CRONTAB_DIALECT}" = debian ]; then
    printf 'usage:\tcrontab [-u user] [-n] file\n\t-n\t(dry run: checks the syntax, then bails out)\n' >&2
  else
    printf 'crontab: illegal option -- h\nusage: crontab [-u user] file\n' >&2
  fi
  exit 1
  ;;
'-n -')
  if grep -q '^99 ' -; then
    printf '"-":2: bad minute\nerrors in crontab file, can'\''t install.\n' >&2
    exit 1
  fi
  printf 'The syntax of the crontab file was successfully checked.\n'
  ;;
*)
  printf 'fake crontab: unexpected %s\n' "$*" >&2
  exit 64
  ;;
esac
EOF
  chmod +x "${FAKE_BIN}/crontab"
}

# Runs cronctl in a clean environment; sets RC, OUT_FILE, and ERR_FILE.
function run_cronctl() {
  env -i \
    HOME="${TEST_HOME}" \
    PATH="${FAKE_BIN}:/usr/bin:/bin" \
    TMPDIR="${TEST_TMP}" \
    CRONCTL_CHEZMOI="$(command -v chezmoi)" \
    FAKE_CRONTAB_DIALECT="${CRONTAB_DIALECT}" \
    "${BASH}" "${SCRIPT}" "$@" </dev/null >"${OUT_FILE}" 2>"${ERR_FILE}"
  RC=$?
}

#############################
#  list                     #
#############################
function test_list_prints_the_job_by_machine_matrix() {
  require_chezmoi || return 0

  run_cronctl list --source "${FIXTURE}"

  assert_same "0" "${RC}"
  assert_empty "$(cat "${ERR_FILE}")"
  assert_same "$(
    cat <<'EOF'
JOB         SCHEDULE    apollo  athena  mac  ENABLED  COMMAND
nightly     30 3 * * *  -       x       -    yes      . "$HOME/.config/nvm/nvm.sh"; bob nightly
everywhere  @hourly     x       x       x    yes      echo "it's $(date +%F)" | tee -a "$HOME/x.log"
parked      0 4 * * *   -       x       x    no       tman start
retire: athena (2 lines) still listed for removal by cronctl sync
EOF
  )" "$(cat "${OUT_FILE}")"
}

function test_list_with_no_jobs_says_so() {
  require_chezmoi || return 0
  sed -i.bak '/^  jobs:/,$d' "${FIXTURE}/home/.chezmoidata.yaml"
  printf '  jobs: []\n' >>"${FIXTURE}/home/.chezmoidata.yaml"

  run_cronctl list --source "${FIXTURE}"

  assert_same "0" "${RC}"
  assert_same "$(printf '%s\n' "JOB  SCHEDULE  apollo  athena  mac  ENABLED  COMMAND" \
    "(no jobs in cron.jobs)")" "$(cat "${OUT_FILE}")"
}

function test_list_json_is_valid_and_expands_all() {
  require_chezmoi || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    bashunit::skip "python3 is required to check the JSON"
    return 0
  fi

  run_cronctl list --json --source "${FIXTURE}"

  assert_same "0" "${RC}"
  python3 -m json.tool "${OUT_FILE}" >/dev/null
  assert_same "0" "$?"
  local summary
  summary="$(
    python3 - "${OUT_FILE}" <<'EOF'
import json, sys
data = json.load(open(sys.argv[1]))
for job in data["jobs"]:
    print(job["name"], ",".join(job["machines"]), ",".join(job["targets"]),
          job["enabled"], repr(job["description"]), job["command"])
print("machines", " ".join(sorted(data["machines"])))
print("env", data["env"])
print("retire", sorted(data["retire"]), data["version"])
EOF
  )"
  assert_same "$(
    cat <<'EOF'
nightly athena athena True 'Nightly maintenance' . "$HOME/.config/nvm/nvm.sh"; bob nightly
everywhere all apollo,athena,mac True '' echo "it's $(date +%F)" | tee -a "$HOME/x.log"
parked athena,mac athena,mac False '' tman start
machines apollo athena mac
env {'MAILTO': 'someone@example.com'}
retire ['athena', 'mac'] 1
EOF
  )" "${summary}"
}

function test_list_rejects_invalid_data() {
  require_chezmoi || return 0
  sed -i.bak 's/      enabled: false/      enabled: "no"/' "${FIXTURE}/home/.chezmoidata.yaml"

  run_cronctl list --source "${FIXTURE}"

  assert_same "2" "${RC}"
  assert_same "cronctl: invalid cron: data: cron.jobs[2] (parked): enabled must be true or false" \
    "$(cat "${ERR_FILE}")"
  assert_empty "$(cat "${OUT_FILE}")"
}

#############################
#  render                   #
#############################
function test_render_prints_the_cron_block_for_any_machine() {
  require_chezmoi || return 0
  local machine expected
  for machine in athena apollo mac; do
    expected="$(printf '{{ template "cron-block" (dict "machine" "%s" "cron" .cron) }}' "${machine}" |
      chezmoi --config "${EMPTY_CONFIG}" --source "${FIXTURE}" execute-template)"

    run_cronctl render "${machine}" --source "${FIXTURE}"

    assert_same "0" "${RC}"
    assert_same "${expected}" "$(cat "${OUT_FILE}")"
    assert_same "# END chezmoi-cron" "$(tail -n 1 "${OUT_FILE}")"
    assert_same "" "$(tail -c 1 "${OUT_FILE}" | tr -d '\n')"
  done
  assert_contains '@hourly "$HOME/bin/cronrun" everywhere '\''echo "it'\''\'\'''\''s $(date +\%F)" | tee -a "$HOME/x.log"'\''' \
    "$(cat "${OUT_FILE}")"
  assert_contains '# parked (disabled): 0 4 * * * "$HOME/bin/cronrun" parked '\''tman start'\''' \
    "$(cat "${OUT_FILE}")"
}

function test_render_rejects_unknown_and_invalid_machines() {
  require_chezmoi || return 0

  run_cronctl render stranger --source "${FIXTURE}"
  assert_same "2" "${RC}"
  assert_contains "cronctl: unknown machine: 'stranger' (enrolled: apollo, athena, mac)" \
    "$(cat "${ERR_FILE}")"
  assert_empty "$(cat "${OUT_FILE}")"

  run_cronctl render 'athena" "x' --source "${FIXTURE}"
  assert_same "2" "${RC}"
  assert_contains "invalid machine name" "$(cat "${ERR_FILE}")"

  run_cronctl render --source "${FIXTURE}"
  assert_same "2" "${RC}"
  assert_contains "missing <machine>" "$(cat "${ERR_FILE}")"

  run_cronctl render athena mac --source "${FIXTURE}"
  assert_same "2" "${RC}"
}

function test_render_defaults_to_the_local_chezmoi_source() {
  require_chezmoi || return 0
  mkdir -p "${TEST_HOME}/.local/share"
  cp -R "${FIXTURE}" "${TEST_HOME}/.local/share/chezmoi"

  run_cronctl render athena

  assert_same "0" "${RC}"
  assert_contains '30 3 * * * "$HOME/bin/cronrun" nightly' "$(cat "${OUT_FILE}")"
}

#############################
#  check                    #
#############################
function test_check_passes_on_the_real_data() {
  require_chezmoi || return 0

  run_cronctl check --source "${REPO_ROOT}"

  assert_same "0" "${RC}"
  assert_contains "ok    athena: block of " "$(cat "${OUT_FILE}")"
  assert_contains "cronctl check: ok (3 machines, " "$(cat "${OUT_FILE}")"
}

function test_check_reports_every_machine() {
  require_chezmoi || return 0

  run_cronctl check --source "${FIXTURE}"

  assert_same "0" "${RC}"
  assert_same "$(
    cat <<'EOF'
ok    apollo: block of 4 lines (1 enabled, 0 disabled), 0 retire lines
ok    athena: block of 7 lines (2 enabled, 1 disabled), 2 retire lines
ok    mac: block of 5 lines (1 enabled, 1 disabled), 0 retire lines
cronctl check: ok (3 machines, 3 jobs; native syntax check: unavailable)
EOF
  )" "$(cat "${OUT_FILE}")"
}

function test_check_fails_on_invalid_data_with_a_clean_message() {
  require_chezmoi || return 0
  sed -i.bak 's/      machines: \[athena, mac\]/      machine: [athena, mac]/' \
    "${FIXTURE}/home/.chezmoidata.yaml"

  run_cronctl check --source "${FIXTURE}"

  assert_same "2" "${RC}"
  assert_same 'cronctl: invalid cron: data: cron.jobs[2] (parked): unknown key "machine" (allowed: name, machines, schedule, description, enabled, command)' \
    "$(cat "${ERR_FILE}")"
}

function test_check_uses_the_native_syntax_check_when_crontab_has_one() {
  require_chezmoi || return 0
  CRONTAB_DIALECT="debian"

  run_cronctl check --source "${FIXTURE}"
  assert_same "0" "${RC}"
  assert_contains "native syntax check: crontab -n)" "$(cat "${OUT_FILE}")"

  sed -i.bak 's/schedule: "30 3 \* \* \*"/schedule: "99 3 * * *"/' "${FIXTURE}/home/.chezmoidata.yaml"

  run_cronctl check --source "${FIXTURE}"

  assert_same "2" "${RC}"
  assert_contains "FAIL  athena" "$(cat "${OUT_FILE}")"
  assert_contains "ok    apollo" "$(cat "${OUT_FILE}")"
  assert_contains "cronctl: crontab -n rejects the block for athena:" "$(cat "${ERR_FILE}")"
  assert_contains "bad minute" "$(cat "${ERR_FILE}")"
  assert_contains "cronctl check: 1 machine of 3 failed" "$(cat "${ERR_FILE}")"
}

function test_check_exits_1_when_chezmoi_cannot_render() {
  require_chezmoi || return 0
  mkdir -p "${TEST_TMP}/empty-source"

  run_cronctl check --source "${TEST_TMP}/empty-source"

  assert_same "1" "${RC}"
  assert_contains "cronctl: chezmoi execute-template failed" "$(cat "${ERR_FILE}")"
}

function test_a_missing_source_directory_is_a_usage_error() {
  run_cronctl check --source "${TEST_TMP}/nowhere"

  assert_same "2" "${RC}"
  assert_contains "--source: no such directory" "$(cat "${ERR_FILE}")"
}

#############################
#  Help and usage           #
#############################
function test_every_command_has_help() {
  local command
  for command in list render check sync; do
    run_cronctl "${command}" --help
    assert_same "0" "${RC}"
    assert_contains "usage: cronctl ${command} " "$(cat "${OUT_FILE}")"

    run_cronctl help "${command}"
    assert_same "0" "${RC}"
    assert_contains "usage: cronctl ${command} " "$(cat "${OUT_FILE}")"
  done

  run_cronctl --help
  assert_same "0" "${RC}"
  assert_contains "usage: cronctl [-h] <command>" "$(cat "${OUT_FILE}")"
}

function test_usage_errors_exit_2() {
  run_cronctl
  assert_same "2" "${RC}"
  assert_contains "usage: cronctl" "$(cat "${ERR_FILE}")"

  run_cronctl frobnicate
  assert_same "2" "${RC}"
  assert_contains "cronctl: unknown command: frobnicate" "$(cat "${ERR_FILE}")"

  run_cronctl list --bogus
  assert_same "2" "${RC}"
  assert_contains "Run 'cronctl list --help' for usage." "$(cat "${ERR_FILE}")"

  run_cronctl sync --dry-run extra
  assert_same "2" "${RC}"
}

function test_the_script_is_streamable_and_never_reads_stdin() {
  require_chezmoi || return 0

  # bash -s reads the script itself from stdin as it runs, so a child that
  # read stdin would eat the rest of the script.
  env -i HOME="${TEST_HOME}" PATH="${FAKE_BIN}:/usr/bin:/bin" TMPDIR="${TEST_TMP}" \
    CRONCTL_CHEZMOI="$(command -v chezmoi)" FAKE_CRONTAB_DIALECT=debian \
    "${BASH}" -s -- check --source "${FIXTURE}" <"${SCRIPT}" >"${OUT_FILE}" 2>"${ERR_FILE}"

  assert_same "0" "$?"
  assert_contains "cronctl check: ok (3 machines, 3 jobs; native syntax check: crontab -n)" \
    "$(cat "${OUT_FILE}")"
}
