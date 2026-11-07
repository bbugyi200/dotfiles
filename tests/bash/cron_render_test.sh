#!/bin/bash

#################################################################################
# Render tests for the cron: data in home/.chezmoidata.yaml, the cron-*         #
# partials in home/.chezmoitemplates, and the per-machine managed.crontab and   #
# retire.crontab targets.                                                       #
#                                                                               #
# These use the chezmoi on PATH. athena runs chezmoi v2.13.1 and CI the latest  #
# release, so run them against both, e.g.                                       #
#   PATH="$HOME/.nix-profile/bin:$PATH" bashunit tests/bash/cron_render_test.sh #
#################################################################################

REPO_ROOT="${PWD}"
CRON_DIR="home/dot_config/cron"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  EMPTY_CONFIG="${TEST_TMP}/empty.yaml"
  OUT_FILE="${TEST_TMP}/out.txt"
  ERR_FILE="${TEST_TMP}/err.txt"
  : >"${EMPTY_CONFIG}"

  # A minimal copy of the source tree whose data each test replaces.
  FIXTURE="${TEST_TMP}/src"
  mkdir -p "${FIXTURE}/${CRON_DIR}"
  cp "${REPO_ROOT}/.chezmoiroot" "${FIXTURE}/"
  cp -R "${REPO_ROOT}/home/.chezmoitemplates" "${FIXTURE}/home/"
  cp "${REPO_ROOT}/${CRON_DIR}/managed.crontab.tmpl" \
    "${REPO_ROOT}/${CRON_DIR}/retire.crontab.tmpl" "${FIXTURE}/${CRON_DIR}/"
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

# Executes the template on stdin against the source tree rooted at $1.
function chezmoi_template() {
  chezmoi --config "${EMPTY_CONFIG}" --source "$1" execute-template
}

# Renders target $2 (managed or retire) of source tree $1 as if
# .chezmoi.hostname were $3.
function render_target() {
  sed "s/\.chezmoi\.hostname/\"$3\"/" "$1/${CRON_DIR}/$2.crontab.tmpl" \
    | chezmoi_template "$1"
}

# Renders the managed block of source tree $1 for canonical machine $2.
function render_block() {
  printf '{{ template "cron-block" (dict "machine" "%s" "cron" .cron) }}' "$2" \
    | chezmoi_template "$1"
}

function write_fixture() {
  cat >"${FIXTURE}/home/.chezmoidata.yaml"
}

# Writes fixture data whose jobs: list is $1 (items indented four spaces).
function write_jobs() {
  write_fixture <<EOF
cron:
  version: 1
  machines:
    athena: [athena]
    mac: [Kellys-MacBook-Pro]
  env:
    MAILTO: someone@example.com
  jobs:
$1
EOF
}

# Asserts that validating the fixture data aborts through fail with a message
# containing $1.
function assert_invalid() {
  local rc
  if printf '%s' '{{ template "cron-validate" (dict "cron" .cron) }}' \
    | chezmoi_template "${FIXTURE}" >"${OUT_FILE}" 2>"${ERR_FILE}"; then
    rc=0
  else
    rc=$?
  fi

  assert_not_same "0" "${rc}"
  assert_contains "error calling fail: $1" "$(cat "${ERR_FILE}")"
}

function write_golden_fixture() {
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
    apollo: [apollo]
    mac: [Kellys-MacBook-Pro, kellys-mbp]
  env:
    SHELL: /bin/bash
    MAILTO: someone@example.com
    EMPTY: ""
  jobs:
    - name: nightly
      machines: [athena]
      schedule: "30 3 * * *"
      description: Nightly maintenance
      command: . "$HOME/.config/nvm/nvm.sh"; nvm use --silent default; bob nightly
    - name: everywhere
      machines: [all]
      schedule: "@hourly"
      command: 'echo "it''s $(date +%F)" | tee -a "$HOME/x.log"'
    - name: parked
      machines: [athena, mac]
      schedule: "0 4 * * *"
      description: Parked for now
      enabled: false
      command: tman start
    - name: mac-only
      machines: [mac]
      schedule: "*/15 * * * *"
      enabled: true
      command: maybe_sync -w
  retire:
    athena:
      - "30 3 * * * bob nightly"
      - "MAILTO=old@example.com"
    mac: []
EOF
}

function test_real_data_validates() {
  require_chezmoi || return 0

  local output
  output="$(printf '%s' '{{ template "cron-validate" (dict "cron" .cron) }}' \
    | chezmoi_template "${REPO_ROOT}")"

  assert_same "0" "$?"
  assert_same "" "${output}"
}

function test_real_data_renders_every_enrolled_machine() {
  require_chezmoi || return 0

  local listing machine hosts host block failures=""
  listing="$(printf '%s' '{{ range $m, $h := .cron.machines }}{{ $m }} {{ $h | join " " }}{{ "\n" }}{{ end }}' \
    | chezmoi_template "${REPO_ROOT}")"
  assert_contains "athena athena" "${listing}"
  assert_contains "apollo apollo" "${listing}"
  assert_contains "mac Kellys-MacBook-Pro" "${listing}"

  while read -r machine hosts; do
    block="$(render_block "${REPO_ROOT}" "${machine}")" \
      || failures="${failures}${machine}: cron-block failed"$'\n'
    if [[ "$(printf '%s\n' "${block}" | head -n 1)" != "# BEGIN chezmoi-cron (machine: ${machine};"* ]]; then
      failures="${failures}${machine}: bad first line"$'\n'
    fi
    if [[ "$(printf '%s\n' "${block}" | tail -n 1)" != "# END chezmoi-cron" ]]; then
      failures="${failures}${machine}: bad last line"$'\n'
    fi
    for host in ${hosts}; do
      if [[ "$(render_target "${REPO_ROOT}" managed "${host}")" != "${block}" ]]; then
        failures="${failures}${machine}: managed.crontab for ${host} differs from cron-block"$'\n'
      fi
      if [[ "$(printf '{{ template "cron-machine" (dict "hostname" "%s" "cron" .cron) }}' "${host}" \
        | chezmoi_template "${REPO_ROOT}")" != "${machine}" ]]; then
        failures="${failures}${machine}: cron-machine does not resolve ${host}"$'\n'
      fi
    done
  done <<<"${listing}"

  if [[ -n "${failures}" ]]; then
    printf 'render failures:\n%s' "${failures}" >&2
  fi
  assert_same "" "${failures}"
}

function test_golden_blocks() {
  require_chezmoi || return 0
  write_golden_fixture

  local expected_athena expected_apollo expected_mac
  expected_athena="$(
    cat <<'EOF'
# BEGIN chezmoi-cron (machine: athena; source: cron: in home/.chezmoidata.yaml; manage with cronctl)
EMPTY=""
MAILTO=someone@example.com
SHELL=/bin/bash
# nightly: Nightly maintenance
30 3 * * * "$HOME/bin/cronrun" nightly '. "$HOME/.config/nvm/nvm.sh"; nvm use --silent default; bob nightly'
@hourly "$HOME/bin/cronrun" everywhere 'echo "it'\''s $(date +\%F)" | tee -a "$HOME/x.log"'
# parked: Parked for now
# parked (disabled): 0 4 * * * "$HOME/bin/cronrun" parked 'tman start'
# END chezmoi-cron
EOF
  )"
  expected_apollo="$(
    cat <<'EOF'
# BEGIN chezmoi-cron (machine: apollo; source: cron: in home/.chezmoidata.yaml; manage with cronctl)
EMPTY=""
MAILTO=someone@example.com
SHELL=/bin/bash
@hourly "$HOME/bin/cronrun" everywhere 'echo "it'\''s $(date +\%F)" | tee -a "$HOME/x.log"'
# END chezmoi-cron
EOF
  )"
  expected_mac="$(
    cat <<'EOF'
# BEGIN chezmoi-cron (machine: mac; source: cron: in home/.chezmoidata.yaml; manage with cronctl)
EMPTY=""
MAILTO=someone@example.com
SHELL=/bin/bash
@hourly "$HOME/bin/cronrun" everywhere 'echo "it'\''s $(date +\%F)" | tee -a "$HOME/x.log"'
# parked: Parked for now
# parked (disabled): 0 4 * * * "$HOME/bin/cronrun" parked 'tman start'
*/15 * * * * "$HOME/bin/cronrun" mac-only 'maybe_sync -w'
# END chezmoi-cron
EOF
  )"

  assert_same "${expected_athena}" "$(render_target "${FIXTURE}" managed athena)"
  assert_same "${expected_apollo}" "$(render_target "${FIXTURE}" managed apollo)"
  assert_same "${expected_mac}" "$(render_target "${FIXTURE}" managed Kellys-MacBook-Pro)"
  assert_same "${expected_mac}" "$(render_target "${FIXTURE}" managed kellys-mbp)"
  assert_same "${expected_athena}" "$(render_block "${FIXTURE}" athena)"
}

function test_block_ends_with_exactly_one_newline() {
  require_chezmoi || return 0
  write_golden_fixture

  render_target "${FIXTURE}" managed athena >"${OUT_FILE}"

  assert_same "# END chezmoi-cron" "$(tail -n 1 "${OUT_FILE}")"
  assert_same "0a" "$(tail -c 1 "${OUT_FILE}" | od -An -tx1 | tr -d ' ')"
  assert_same "10" "$(wc -l <"${OUT_FILE}" | tr -d ' ')"
}

function test_golden_retire_lines() {
  require_chezmoi || return 0
  write_golden_fixture

  render_target "${FIXTURE}" retire athena >"${OUT_FILE}"

  assert_same "$(printf '%s\n' "30 3 * * * bob nightly" "MAILTO=old@example.com")" \
    "$(cat "${OUT_FILE}")"
  assert_same "2" "$(wc -l <"${OUT_FILE}" | tr -d ' ')"
  # An empty list and a missing entry both render nothing.
  assert_same "0" "$(render_target "${FIXTURE}" retire Kellys-MacBook-Pro | wc -c | tr -d ' ')"
  assert_same "0" "$(render_target "${FIXTURE}" retire apollo | wc -c | tr -d ' ')"
}

function test_unknown_hostname_renders_nothing() {
  require_chezmoi || return 0
  write_golden_fixture

  assert_same "0" "$(render_target "${FIXTURE}" managed some-other-host | wc -c | tr -d ' ')"
  assert_same "0" "$(render_target "${FIXTURE}" retire some-other-host | wc -c | tr -d ' ')"
  assert_same "0" "$(printf '%s' '{{ template "cron-machine" (dict "hostname" "some-other-host" "cron" .cron) }}' \
    | chezmoi_template "${FIXTURE}" | wc -c | tr -d ' ')"
}

function test_enrolled_machine_without_jobs_renders_markers_only() {
  require_chezmoi || return 0
  write_jobs "    []"

  local expected
  expected="$(
    cat <<'EOF'
# BEGIN chezmoi-cron (machine: athena; source: cron: in home/.chezmoidata.yaml; manage with cronctl)
MAILTO=someone@example.com
# END chezmoi-cron
EOF
  )"

  assert_same "${expected}" "$(render_target "${FIXTURE}" managed athena)"
  assert_same "0" "$(render_target "${FIXTURE}" retire athena | wc -c | tr -d ' ')"
}

function test_minimal_data_renders_markers_only() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
EOF

  assert_same "$(printf '%s\n' \
    "# BEGIN chezmoi-cron (machine: athena; source: cron: in home/.chezmoidata.yaml; manage with cronctl)" \
    "# END chezmoi-cron")" "$(render_target "${FIXTURE}" managed athena)"
}

function test_quoting_round_trips_through_sh() {
  require_chezmoi || return 0
  # A command with ', %, $(date +%F), a pipe, and $HOME.
  local command
  command='printf '"'"'%s\n'"'"' "it'"'"'s $(date +%F)" | tee -a "$HOME/out.log"'
  write_jobs "$(
    cat <<'EOF'
    - name: quoting
      machines: [athena]
      schedule: "@daily"
      command: 'printf ''%s\n'' "it''s $(date +%F)" | tee -a "$HOME/out.log"'
EOF
  )"

  local line
  line="$(render_target "${FIXTURE}" managed athena | grep -F 'cronrun" quoting ')"
  assert_same "@daily \"\$HOME/bin/cronrun\" quoting 'printf '\\''\\%s\\n'\\'' \"it'\\''s \$(date +\\%F)\" | tee -a \"\$HOME/out.log\"'" \
    "${line}"

  # Simulate cron: drop the schedule, unescape \% to %, and hand the rest to
  # /bin/sh with a fake cronrun that records its arguments.
  local fake_home="${TEST_TMP}/home"
  mkdir -p "${fake_home}/bin"
  cat >"${fake_home}/bin/cronrun" <<'EOF'
#!/bin/sh
printf '%s' "$1" >"$HOME/job.txt"
printf '%s' "$2" >"$HOME/command.txt"
EOF
  chmod +x "${fake_home}/bin/cronrun"
  local cron_command
  cron_command="$(printf '%s\n' "${line#@daily }" | sed 's/\\%/%/g')"
  HOME="${fake_home}" /bin/sh -c "${cron_command}"

  assert_same "quoting" "$(cat "${fake_home}/job.txt")"
  assert_same "${command}" "$(cat "${fake_home}/command.txt")"

  # The recovered command runs as written under bash.
  HOME="${fake_home}" bash -c "$(cat "${fake_home}/command.txt")" >/dev/null
  assert_same "it's $(date +%F)" "$(cat "${fake_home}/out.log")"
}

function test_invalid_data_aborts_target_render() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 2
  machines:
    athena: [athena]
EOF

  local host rc
  for host in athena some-other-host; do
    if render_target "${FIXTURE}" managed "${host}" >"${OUT_FILE}" 2>"${ERR_FILE}"; then
      rc=0
    else
      rc=$?
    fi
    assert_not_same "0" "${rc}"
    assert_contains "cron.version: must be 1" "$(cat "${ERR_FILE}")"
  done
}

function test_block_for_unknown_machine_fails() {
  require_chezmoi || return 0
  write_golden_fixture

  local rc
  if render_block "${FIXTURE}" nope >"${OUT_FILE}" 2>"${ERR_FILE}"; then rc=0; else rc=$?; fi

  assert_not_same "0" "${rc}"
  assert_contains 'cron: unknown machine "nope" (enrolled: apollo, athena, mac)' "$(cat "${ERR_FILE}")"
}

function test_rejects_unsupported_version() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 2
  machines:
    athena: [athena]
EOF
  assert_invalid "cron.version: must be 1, got 2"
}

function test_rejects_missing_version() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  machines:
    athena: [athena]
EOF
  assert_invalid "cron.version: must be 1"
}

function test_rejects_unknown_top_level_key() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
  job: []
EOF
  assert_invalid 'cron: unknown key "job"'
}

function test_rejects_empty_machines() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines: {}
EOF
  assert_invalid "cron.machines: must enroll at least one machine"
}

function test_rejects_invalid_machine_name() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    Athena: [athena]
EOF
  assert_invalid 'cron.machines: invalid machine name "Athena"'
}

function test_rejects_machine_named_all() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    all: [athena]
EOF
  assert_invalid 'cron.machines: "all" is reserved'
}

function test_rejects_hostname_claimed_by_two_machines() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
    apollo: [apollo, athena]
EOF
  assert_invalid 'cron.machines: hostname "athena" is claimed by both apollo and athena'
}

function test_rejects_invalid_job_name() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: Bad_Name
      machines: [athena]
      schedule: "0 * * * *"
      command: echo ok
EOF
  )"
  assert_invalid 'cron.jobs[0]: invalid job name "Bad_Name"'
}

function test_rejects_duplicate_job_name() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: twice
      machines: [athena]
      schedule: "0 * * * *"
      command: echo one
    - name: twice
      machines: [mac]
      schedule: "0 * * * *"
      command: echo two
EOF
  )"
  assert_invalid 'cron.jobs[1]: duplicate job name "twice"'
}

function test_rejects_unknown_job_key() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: typo
      machine: [athena]
      schedule: "0 * * * *"
      command: echo ok
EOF
  )"
  assert_invalid 'cron.jobs[0] (typo): unknown key "machine"'
}

function test_rejects_empty_job_machines() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: nowhere
      machines: []
      schedule: "0 * * * *"
      command: echo ok
EOF
  )"
  assert_invalid "cron.jobs[0] (nowhere): machines must not be empty"
}

function test_rejects_unknown_job_machine() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: elsewhere
      machines: [zeus]
      schedule: "0 * * * *"
      command: echo ok
EOF
  )"
  assert_invalid 'cron.jobs[0] (elsewhere): unknown machine "zeus" (enrolled: athena, mac)'
}

function test_rejects_all_mixed_with_machines() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: mixed
      machines: [all, athena]
      schedule: "0 * * * *"
      command: echo ok
EOF
  )"
  assert_invalid "cron.jobs[0] (mixed): machines may list all only on its own"
}

function test_rejects_schedule_with_four_fields() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: short
      machines: [athena]
      schedule: "0 * * *"
      command: echo ok
EOF
  )"
  assert_invalid 'cron.jobs[0] (short): invalid schedule "0 * * *"'
}

function test_rejects_unknown_schedule_keyword() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: sometimes
      machines: [athena]
      schedule: "@sometimes"
      command: echo ok
EOF
  )"
  assert_invalid 'cron.jobs[0] (sometimes): invalid schedule "@sometimes"'
}

function test_rejects_schedule_with_shell_characters() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: sneaky
      machines: [athena]
      schedule: "0 * * * ; rm"
      command: echo ok
EOF
  )"
  assert_invalid 'cron.jobs[0] (sneaky): invalid schedule'
}

function test_rejects_missing_command() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: idle
      machines: [athena]
      schedule: "0 * * * *"
EOF
  )"
  assert_invalid "cron.jobs[0] (idle): command is required and must be a string"
}

function test_rejects_empty_command() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: blank
      machines: [athena]
      schedule: "0 * * * *"
      command: "   "
EOF
  )"
  assert_invalid "cron.jobs[0] (blank): command must not be empty"
}

function test_rejects_multi_line_command() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: twolines
      machines: [athena]
      schedule: "0 * * * *"
      command: |
        echo one
        echo two
EOF
  )"
  assert_invalid "cron.jobs[0] (twolines): command must be a single line"
}

function test_rejects_backslash_percent_in_command() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: escaped
      machines: [athena]
      schedule: "0 * * * *"
      command: 'date +\%F'
EOF
  )"
  assert_invalid "cron.jobs[0] (escaped): command must not contain a backslash before %"
}

function test_rejects_multi_line_description() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: chatty
      machines: [athena]
      schedule: "0 * * * *"
      description: "one\ntwo"
      command: echo ok
EOF
  )"
  assert_invalid "cron.jobs[0] (chatty): description must be a single line"
}

function test_rejects_multi_line_env_value() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
  env:
    MAILTO: "one\ntwo"
EOF
  assert_invalid "cron.env.MAILTO: value must be a single line"
}

function test_rejects_invalid_env_key() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
  env:
    mailto: someone@example.com
EOF
  assert_invalid 'cron.env: invalid variable name "mailto"'
}

function test_rejects_non_boolean_enabled() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: maybe
      machines: [athena]
      schedule: "0 * * * *"
      enabled: "no"
      command: echo ok
EOF
  )"
  assert_invalid "cron.jobs[0] (maybe): enabled must be true or false"
}

function test_rejects_retire_for_unknown_machine() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
  retire:
    zeus: ["0 * * * * old"]
EOF
  assert_invalid 'cron.retire: unknown machine "zeus" (enrolled: athena)'
}

function test_rejects_blank_retire_line() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
  retire:
    athena: ["  "]
EOF
  assert_invalid "cron.retire.athena[0]: must not be blank"
}

function test_rejects_home_path_in_command() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: pinned
      machines: [athena]
      schedule: "0 * * * *"
      command: /home/bryan/bin/thing
EOF
  )"
  assert_invalid "cron.jobs[0] (pinned): command must not hard-code /home/, /Users/, or /run/user/"
}

function test_rejects_run_user_path_in_command() {
  require_chezmoi || return 0
  write_jobs "$(
    cat <<'EOF'
    - name: busy
      machines: [athena]
      schedule: "0 * * * *"
      command: DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus notify
EOF
  )"
  assert_invalid "cron.jobs[0] (busy): command must not hard-code /home/, /Users/, or /run/user/"
}

function test_rejects_users_path_in_env_value() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
  env:
    BOB_VAULT: /Users/bbugyi/bob
EOF
  assert_invalid "cron.env.BOB_VAULT: value must not hard-code /home/, /Users/, or /run/user/"
}

function test_retire_lines_are_exempt_from_path_rule() {
  require_chezmoi || return 0
  write_fixture <<'EOF'
cron:
  version: 1
  machines:
    athena: [athena]
  retire:
    athena:
      - "HOME=/home/bryan"
      - "XDG_RUNTIME_DIR=/run/user/1000"
EOF

  assert_same "$(printf '%s\n' "HOME=/home/bryan" "XDG_RUNTIME_DIR=/run/user/1000")" \
    "$(render_target "${FIXTURE}" retire athena)"
}
