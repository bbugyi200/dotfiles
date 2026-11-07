#!/bin/bash

#################################################################################
# Tests for cronctl's fleet commands: status, diff, apply, logs, run, and edit. #
#                                                                               #
# A fake fleet lives under $TEST_TMP/machines/<alias>/: each machine has its    #
# own HOME (a chezmoi source cloned from a local bare "origin", a chezmoi       #
# symlink off PATH, and a fake crontab table) and a hostname file. A fake ssh   #
# on PATH runs `bash -s` locally, under `env -i`, in the target's HOME; an      #
# alias with no directory, or with a "down" file, is unreachable (exit 255).    #
# The caller is athena, which never needs SSH for itself. Real chezmoi and git #
# do the work, so the real crontab and network are never touched.              #
#                                                                               #
# Test seam: the fixture's managed/retire templates read the hostname from      #
# $CRONCTL_HOSTNAME (as cronctl does), since every fake machine shares one      #
# .chezmoi.hostname. The fake ssh appends a trailer line after the streamed     #
# script; the fake git and crontab log any stdin they can read, so a routine    #
# child that read stdin (and would eat the rest of a real streamed script)      #
# fails the tests.                                                              #
#                                                                               #
# These use the chezmoi on PATH. athena runs chezmoi v2.13.1 and CI the latest  #
# release, so run them against both, e.g.                                       #
#   PATH="$HOME/.nix-profile/bin:$PATH" bashunit tests/bash/cronctl_test.sh     #
#################################################################################

# Crontab lines hold literal "$HOME" on purpose.
# shellcheck disable=SC2016

REPO_ROOT="${PWD}"
SCRIPT="${REPO_ROOT}/home/bin/executable_cronctl"

LEGACY_LINE='*/15 * * * * ~/bin/legacy_sync >> /var/tmp/legacy.log'
WATCHDOG_LINE='*/5 * * * * /usr/bin/true # sase-epic-watchdog:sase-1r2'

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  MACHINES="${TEST_TMP}/machines"
  ORIGIN="${TEST_TMP}/origin.git"
  WORK="${TEST_TMP}/work"
  SSH_LOG="${TEST_TMP}/ssh.log"
  SSH_ARGV_LOG="${TEST_TMP}/ssh.argv"
  LEAK_LOG="${TEST_TMP}/stdin-leaks.log"
  OUT_FILE="${TEST_TMP}/stdout"
  ERR_FILE="${TEST_TMP}/stderr"
  RUN_ENV=()
  : >"${SSH_LOG}"
  : >"${SSH_ARGV_LOG}"
  : >"${LEAK_LOG}"
  mkdir -p "${FAKE_BIN}" "${MACHINES}"
  if ! command -v chezmoi >/dev/null 2>&1; then
    return 0
  fi
  REAL_CHEZMOI="$(command -v chezmoi)"
  REAL_GIT="$(command -v git)"
  write_fakes
  write_origin
  add_machine athena athena .nix-profile/bin
  add_machine apollo apollo .nix-profile/bin
  add_machine mac Kellys-MacBook-Pro go/bin
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function require_chezmoi() {
  if [[ -z "${REAL_CHEZMOI:-}" ]]; then
    bashunit::skip "chezmoi is required to render the cron templates"
    return 1
  fi
}

function git_real() {
  "${REAL_GIT}" -c user.name=tester -c user.email=tester@example.com \
    -c init.defaultBranch=master "$@" </dev/null >/dev/null 2>&1
}

function write_fakes() {
  # git: logs any stdin it can read, then runs the real git.
  cat >"${FAKE_BIN}/git" <<EOF
#!/bin/bash
if IFS= read -r -t 2 leaked; then
  printf 'git %s read stdin: %s\n' "\$*" "\${leaked}" >>"${LEAK_LOG}"
fi
exec "${REAL_GIT}" "\$@"
EOF

  # crontab: the table lives in \$HOME/.crontab-table (absent: no crontab).
  cat >"${FAKE_BIN}/crontab" <<EOF
#!/bin/bash
table="\${HOME}/.crontab-table"
printf 'crontab %s\n' "\$*" >>"\${HOME}/.crontab-calls"
case "\$*" in
-h | -l)
  if IFS= read -r -t 2 leaked; then
    printf 'crontab %s read stdin: %s\n' "\$*" "\${leaked}" >>"${LEAK_LOG}"
  fi
  ;;
esac
case "\$*" in
-h)
  printf 'crontab: illegal option -- h\nusage: crontab [-u user] file\n' >&2
  exit 1
  ;;
-l)
  if [ -f "\${table}" ]; then
    cat "\${table}"
  else
    printf 'no crontab for tester\n' >&2
    exit 1
  fi
  ;;
-) cat >"\${table}" ;;
*)
  printf 'fake crontab: unexpected %s\n' "\$*" >&2
  exit 64
  ;;
esac
EOF

  # ssh [-o opt]... <alias> <command>: the remote login shell runs <command>
  # with sshd's environment only. A trailer after the streamed script
  # catches any child that reads stdin. The whole argv goes to SSH_ARGV_LOG,
  # and the alias and command alone to SSH_LOG.
  cat >"${FAKE_BIN}/ssh" <<EOF
#!/bin/bash
printf '%s\n' "\$*" >>"${SSH_ARGV_LOG}"
while [ "\$#" -gt 0 ]; do
  case "\$1" in
  -o) shift 2 ;;
  -*) shift ;;
  *) break ;;
  esac
done
alias="\$1"
shift
printf '%s %s\n' "\${alias}" "\$*" >>"${SSH_LOG}"
root="${MACHINES}/\${alias}"
if [ ! -d "\${root}/home" ] || [ -e "\${root}/down" ]; then
  cat >/dev/null
  printf 'ssh: connect to host %s port 22: Operation timed out\n' "\${alias}" >&2
  exit 255
fi
{
  cat
  printf '\n# trailer: a routine child that reads stdin eats this line\n'
} | env -i HOME="\${root}/home" PATH="${FAKE_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
  TMPDIR="${TEST_TMP}" LOGNAME=tester USER=tester CRONCTL_LOCK_IMPL=mkdir \
  CRONCTL_HOSTNAME="\$(cat "\${root}/hostname")" /bin/bash -c "\$*"
EOF

  # An editor for cronctl edit: applies \$FAKE_EDIT (a sed script).
  cat >"${FAKE_BIN}/fake-editor" <<'EOF'
#!/bin/bash
sed -i.bak "${FAKE_EDIT}" "$1"
rm -f "$1.bak"
EOF
  chmod +x "${FAKE_BIN}/git" "${FAKE_BIN}/crontab" "${FAKE_BIN}/ssh" "${FAKE_BIN}/fake-editor"
}

function write_data() {
  cat >"${WORK}/home/.chezmoidata.yaml" <<'EOF'
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
      command: echo nightly
    - name: hourly
      machines: [all]
      schedule: "@hourly"
      command: echo hourly
    - name: sweep
      machines: [mac]
      schedule: "*/15 * * * *"
      command: echo "it's $(date +%Y) MAILTO=$MAILTO SHELL=$SHELL"; exit 3
    - name: parked
      machines: [mac]
      schedule: "0 4 * * *"
      enabled: false
      command: tman start
  retire:
    mac:
      - "*/15 * * * * ~/bin/legacy_sync >> /var/tmp/legacy.log"
EOF
}

# origin.git holds two commits: BASE_REV, a source that predates cron, and
# CRON_REV, which adds the cron data, partials, targets, and scripts.
function write_origin() {
  git_real init --bare "${ORIGIN}"
  git_real -C "${ORIGIN}" symbolic-ref HEAD refs/heads/master
  git_real clone "${ORIGIN}" "${WORK}"
  mkdir -p "${WORK}/home"
  cp "${REPO_ROOT}/.chezmoiroot" "${WORK}/"
  printf 'placeholder\n' >"${WORK}/home/dot_placeholder"
  git_real -C "${WORK}" add -A
  git_real -C "${WORK}" commit -m base
  BASE_REV="$("${REAL_GIT}" -C "${WORK}" rev-parse HEAD)"

  cp -R "${REPO_ROOT}/home/.chezmoitemplates" "${WORK}/home/"
  mkdir -p "${WORK}/home/dot_config/cron" "${WORK}/home/bin"
  local target
  for target in managed retire; do
    sed 's/\.chezmoi\.hostname/(env "CRONCTL_HOSTNAME" | default .chezmoi.hostname)/' \
      "${REPO_ROOT}/home/dot_config/cron/${target}.crontab.tmpl" \
      >"${WORK}/home/dot_config/cron/${target}.crontab.tmpl"
  done
  cp "${SCRIPT}" "${WORK}/home/bin/executable_cronctl"
  cp "${REPO_ROOT}/home/bin/executable_cronrun" "${WORK}/home/bin/executable_cronrun"
  write_data
  git_real -C "${WORK}" add -A
  git_real -C "${WORK}" commit -m cron
  git_real -C "${WORK}" push origin master
  CRON_REV="$("${REAL_GIT}" -C "${WORK}" rev-parse HEAD)"
}

# add_machine <alias> <hostname> <dir under HOME holding its chezmoi>
function add_machine() {
  local home="${MACHINES}/$1/home"
  mkdir -p "${home}/.local/share" "${home}/$3"
  printf '%s\n' "$2" >"${MACHINES}/$1/hostname"
  ln -s "${REAL_CHEZMOI}" "${home}/$3/chezmoi"
  git_real clone "${ORIGIN}" "${home}/.local/share/chezmoi"
}

function home_of() {
  printf '%s/%s/home' "${MACHINES}" "$1"
}

function table_of() {
  printf '%s/.crontab-table' "$(home_of "$1")"
}

function write_table() {
  printf '%s\n' "${@:2}" >"$(table_of "$1")"
}

# Pushes a new commit to origin from the authoring checkout.
function push_change() {
  sed -i.bak "$1" "${WORK}/home/.chezmoidata.yaml"
  rm -f "${WORK}/home/.chezmoidata.yaml.bak"
  git_real -C "${WORK}" commit -am change
  git_real -C "${WORK}" push origin master
}

# Runs cronctl on athena (the caller); sets RC, OUT_FILE, and ERR_FILE.
function run_cronctl() {
  env -i \
    HOME="$(home_of athena)" \
    PATH="${FAKE_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    TMPDIR="${TEST_TMP}" \
    LOGNAME=tester USER=tester \
    CRONCTL_HOSTNAME=athena \
    CRONCTL_LOCK_IMPL=mkdir \
    ${RUN_ENV[@]+"${RUN_ENV[@]}"} \
    "${BASH}" "${SCRIPT}" "$@" </dev/null >"${OUT_FILE}" 2>"${ERR_FILE}"
  RC=$?
}

function apply_all() {
  run_cronctl apply --all
  assert_same "0" "${RC}"
}

function assert_no_stdin_leaks() {
  assert_empty "$(cat "${LEAK_LOG}")"
}

#############################
#  apply                    #
#############################
function test_apply_converges_a_target_with_no_prior_cronctl() {
  require_chezmoi || return 0
  local mac_home
  mac_home="$(home_of mac)"
  # Like the real Mac: its source predates cron, and nothing is deployed.
  git_real -C "${mac_home}/.local/share/chezmoi" reset --hard "${BASE_REV}"
  write_table mac "# legacy" "${LEGACY_LINE}" "${WATCHDOG_LINE}"

  run_cronctl apply mac

  assert_same "0" "${RC}"
  assert_contains "cronctl apply: ${CRON_REV} (origin's HEAD) to mac" "$(cat "${OUT_FILE}")"
  assert_matches "mac +in_sync +${CRON_REV:0:12} +cronctl sync: mac: inserted the managed block at the top \(6 lines\); removed 1 retire line" \
    "$(cat "${OUT_FILE}")"
  assert_contains "cronctl apply: 1 in_sync" "$(cat "${OUT_FILE}")"
  # The sweep line nests the renderer's '\'' quoting inside the test's own.
  # shellcheck disable=SC1003
  assert_same "$(printf '%s\n' \
    '# BEGIN chezmoi-cron (machine: mac; source: cron: in home/.chezmoidata.yaml; manage with cronctl)' \
    'MAILTO=someone@example.com' \
    '@hourly "$HOME/bin/cronrun" hourly '\''echo hourly'\''' \
    '*/15 * * * * "$HOME/bin/cronrun" sweep '\''echo "it'\''\'\'''\''s $(date +\%Y) MAILTO=$MAILTO SHELL=$SHELL"; exit 3'\''' \
    '# parked (disabled): 0 4 * * * "$HOME/bin/cronrun" parked '\''tman start'\''' \
    '# END chezmoi-cron' '# legacy' "${WATCHDOG_LINE}")" "$(cat "$(table_of mac)")"
  assert_file_exists "${mac_home}/bin/cronctl"
  assert_file_exists "${mac_home}/bin/cronrun"
  assert_same "${CRON_REV}" "$("${REAL_GIT}" -C "${mac_home}/.local/share/chezmoi" rev-parse HEAD)"
  # A targeted apply leaves every other dotfile for the next full update.
  assert_file_not_exists "${mac_home}/.placeholder"
  assert_same "mac bash -s -- __apply ${CRON_REV} mac" "$(cat "${SSH_LOG}")"
  # Keepalives make a link that dies mid-session exit 255 (pending).
  assert_same "-o BatchMode=yes -o ConnectTimeout=8 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 mac bash -s -- __apply ${CRON_REV} mac" \
    "$(cat "${SSH_ARGV_LOG}")"
  assert_no_stdin_leaks
}

function test_apply_is_idempotent_and_reports_an_unchanged_table() {
  require_chezmoi || return 0
  apply_all
  local before
  before="$(cat "$(table_of mac)")"

  run_cronctl apply mac

  assert_same "0" "${RC}"
  assert_matches "mac +in_sync +${CRON_REV:0:12} +the crontab already matched" "$(cat "${OUT_FILE}")"
  assert_same "${before}" "$(cat "$(table_of mac)")"
}

function test_apply_reports_an_unreachable_target_as_pending_and_exits_3() {
  require_chezmoi || return 0
  touch "${MACHINES}/apollo/down"

  run_cronctl apply apollo mac

  assert_same "3" "${RC}"
  assert_matches "apollo +pending +- +unreachable over SSH: ssh: connect to host apollo port 22: Operation timed out" \
    "$(cat "${OUT_FILE}")"
  assert_matches "mac +in_sync" "$(cat "${OUT_FILE}")"
  assert_contains "cronctl apply: 1 in_sync, 1 pending" "$(cat "${OUT_FILE}")"
  assert_file_not_exists "$(table_of apollo)"
}

function test_apply_refuses_an_unpushed_rev() {
  require_chezmoi || return 0
  local athena_source unpushed
  athena_source="$(home_of athena)/.local/share/chezmoi"
  printf 'local only\n' >"${athena_source}/home/dot_local_only"
  git_real -C "${athena_source}" add -A
  git_real -C "${athena_source}" commit -m unpushed
  unpushed="$("${REAL_GIT}" -C "${athena_source}" rev-parse HEAD)"

  run_cronctl apply --rev "${unpushed}" mac

  assert_same "2" "${RC}"
  assert_contains "is not reachable from origin; push it first" "$(cat "${ERR_FILE}")"
  assert_empty "$(cat "${SSH_LOG}")"
  assert_file_not_exists "$(table_of mac)"

  run_cronctl apply --rev no-such-rev mac
  assert_same "2" "${RC}"
  assert_contains "no such commit in the local chezmoi source" "$(cat "${ERR_FILE}")"

  # A pushed revision is accepted, even an older one.
  run_cronctl apply --rev "${BASE_REV}" mac
  assert_same "0" "${RC}"
  assert_contains "cronctl apply: ${BASE_REV} (--rev ${BASE_REV}) to mac" "$(cat "${OUT_FILE}")"
}

function test_apply_skips_a_target_whose_identity_does_not_match() {
  require_chezmoi || return 0
  # The host answering for mac is apollo in its own data.
  printf 'apollo\n' >"${MACHINES}/mac/hostname"
  write_table mac "${LEGACY_LINE}"

  run_cronctl apply mac

  assert_same "1" "${RC}"
  assert_matches "mac +identity_mismatch +${CRON_REV:0:12} +this host \(apollo\) is apollo in its own cron: data, not mac; nothing was applied" \
    "$(cat "${OUT_FILE}")"
  assert_same "${LEGACY_LINE}" "$(cat "$(table_of mac)")"
  assert_file_not_exists "$(home_of mac)/bin/cronctl"
}

function test_the_local_target_uses_no_ssh() {
  require_chezmoi || return 0
  write_table athena "${WATCHDOG_LINE}"

  run_cronctl apply athena
  assert_same "0" "${RC}"
  assert_matches "athena +in_sync" "$(cat "${OUT_FILE}")"
  assert_contains '30 3 * * * "$HOME/bin/cronrun" nightly' "$(cat "$(table_of athena)")"

  run_cronctl status
  assert_same "0" "${RC}"
  assert_contains "athena: in_sync" "$(cat "${OUT_FILE}")"

  run_cronctl diff athena
  assert_same "0" "${RC}"

  assert_empty "$(cat "${SSH_LOG}")"
}

function test_apply_needs_targets() {
  require_chezmoi || return 0
  run_cronctl apply
  assert_same "2" "${RC}"
  assert_contains "name the machines to apply, or pass --all" "$(cat "${ERR_FILE}")"

  run_cronctl apply stranger
  assert_same "2" "${RC}"
  assert_contains "unknown machine: 'stranger' (enrolled: apollo, athena, mac)" "$(cat "${ERR_FILE}")"
  assert_empty "$(cat "${SSH_LOG}")"
}

#############################
#  status                   #
#############################
function test_status_classifies_each_machine() {
  require_chezmoi || return 0
  write_table mac "${LEGACY_LINE}" "${WATCHDOG_LINE}"
  apply_all
  run_cronctl status --all
  assert_same "0" "${RC}"
  assert_contains "athena: in_sync" "$(cat "${OUT_FILE}")"
  assert_contains "apollo: in_sync" "$(cat "${OUT_FILE}")"
  assert_contains "mac: in_sync" "$(cat "${OUT_FILE}")"
  assert_contains "cron.retire can be deleted" "$(cat "${OUT_FILE}")"

  # apollo loses its block, and mac gets a hand edit plus a legacy line back.
  printf '%s\n' "${WATCHDOG_LINE}" >"$(table_of apollo)"
  sed -i.bak -e 's/^MAILTO=.*/MAILTO=hand@example.com/' "$(table_of mac)"
  printf '%s\n' "${LEGACY_LINE}" >>"$(table_of mac)"

  run_cronctl status --all

  assert_same "0" "${RC}"
  local out
  out="$(cat "${OUT_FILE}")"
  assert_contains "athena: in_sync" "${out}"
  assert_contains "apollo: unmanaged" "${out}"
  assert_contains "note: the crontab has no managed block yet; run cronctl apply apollo" "${out}"
  assert_contains "mac: drifted" "${out}"
  assert_contains "note: the live block differs from the deployed managed.crontab" "${out}"
  assert_contains "note: deployed retire lines are back outside the block" "${out}"
  assert_contains "$(printf '%s\n' "  retire lines still present (1):" "    ${LEGACY_LINE}")" "${out}"
  assert_contains "$(printf '%s\n' "  unmanaged lines outside the block (1):" "    ${WATCHDOG_LINE}")" "${out}"
  assert_contains "cron.retire is still needed: mac still has 1 line" "${out}"
  assert_contains "host: Kellys-MacBook-Pro (" "${out}"
  assert_contains "source: ${CRON_REV}, at origin's HEAD" "${out}"
}

function test_status_reports_unreachable_behind_and_mismatched_machines() {
  require_chezmoi || return 0
  apply_all
  push_change 's/schedule: "@hourly"/schedule: "@daily"/'
  touch "${MACHINES}/mac/down"

  run_cronctl status --all

  assert_same "3" "${RC}"
  local out
  out="$(cat "${OUT_FILE}")"
  assert_contains "apollo: pending" "${out}"
  assert_contains "note: its chezmoi source is behind origin; run cronctl apply apollo" "${out}"
  assert_contains "mac: pending" "${out}"
  assert_contains "note: unreachable over SSH: ssh: connect to host mac port 22: Operation timed out" "${out}"
  assert_contains "cron.retire is still needed: mac could not be read (pending)" "${out}"

  # A failed or mismatched machine outranks an unreachable one.
  printf 'Kellys-MacBook-Pro\n' >"${MACHINES}/apollo/hostname"
  run_cronctl status apollo mac
  assert_same "1" "${RC}"
  assert_contains "apollo: identity_mismatch" "$(cat "${OUT_FILE}")"
  assert_contains "note: the host answering for apollo (Kellys-MacBook-Pro) is mac in its own cron: data" \
    "$(cat "${OUT_FILE}")"
}

function test_status_reports_a_source_that_predates_cron_as_pending() {
  require_chezmoi || return 0
  git_real -C "$(home_of mac)/.local/share/chezmoi" reset --hard "${BASE_REV}"
  write_table mac "${LEGACY_LINE}"

  run_cronctl status mac

  assert_same "0" "${RC}"
  assert_contains "mac: pending" "$(cat "${OUT_FILE}")"
  assert_contains "note: its chezmoi source cannot resolve the host" "$(cat "${OUT_FILE}")"
  assert_contains "source: ${BASE_REV}, behind origin" "$(cat "${OUT_FILE}")"
  assert_contains "$(printf '%s\n' "  retire lines still present (1):" "    ${LEGACY_LINE}")" \
    "$(cat "${OUT_FILE}")"
}

function test_status_shows_each_jobs_last_run() {
  require_chezmoi || return 0
  apply_all
  local state
  state="$(home_of athena)/.local/state/cron"
  printf 'job=nightly\nhost=athena\npid=42\nstart=2026-11-07T08:30:00Z\nend=2026-11-07T08:31:02Z\nexit=0\n' \
    >"${state}/nightly.status"
  printf 'job=hourly\nhost=athena\npid=77\nstart=2026-11-07T09:00:00Z\nend=\nexit=\n' \
    >"${state}/hourly.status"

  run_cronctl status athena mac

  assert_same "0" "${RC}"
  local out
  out="$(cat "${OUT_FILE}")"
  assert_contains "    nightly: last run 2026-11-07T08:30:00Z to 2026-11-07T08:31:02Z, exit 0" "${out}"
  assert_contains "    hourly: running since 2026-11-07T09:00:00Z (pid 77 on athena)" "${out}"
  assert_contains "    sweep: never run here" "${out}"
  assert_contains "    parked (disabled): never run here" "${out}"
}

function test_status_json_is_valid_json() {
  require_chezmoi || return 0
  if ! command -v python3 >/dev/null 2>&1; then
    bashunit::skip "python3 is required to check the JSON"
    return 0
  fi
  apply_all
  printf 'job=nightly\nhost=athena\npid=42\nstart=2026-11-07T08:30:00Z\nend=2026-11-07T08:31:02Z\nexit=0\n' \
    >"$(home_of athena)/.local/state/cron/nightly.status"
  # A tab, quotes, and backslashes must survive the hand-built JSON.
  printf '%s\n' "$(printf '0 1 * * * echo "a\\\\b"\tc')" >>"$(table_of apollo)"
  touch "${MACHINES}/mac/down"

  run_cronctl status --all --json

  assert_same "3" "${RC}"
  python3 -m json.tool "${OUT_FILE}" >/dev/null
  assert_same "0" "$?"
  # bash 3.2 misparses here-docs inside $(...), so they go to files first.
  cat >"${TEST_TMP}/summary.py" <<'EOF'
import json, sys
data = json.load(open(sys.argv[1]))
print("origin", len(data["origin"]), data["retire"])
for m in data["machines"]:
    print(m["machine"], m["state"], m["reachable"], m["source"]["relation"],
          m["unmanaged_lines"], [(j["name"], j["enabled"], j["last_run"] and j["last_run"]["exit"]) for j in m["jobs"]])
EOF
  cat >"${TEST_TMP}/expected" <<'EOF'
origin 40 {'lines': 1, 'deletable': False, 'blockers': ['mac could not be read (pending)']}
apollo in_sync True current ['0 1 * * * echo "a\\\\b"\tc'] [('hourly', True, None)]
athena in_sync True current [] [('nightly', True, 0), ('hourly', True, None)]
mac pending False None [] [('hourly', True, None), ('sweep', True, None), ('parked', False, None)]
EOF
  assert_same "$(cat "${TEST_TMP}/expected")" "$(python3 "${TEST_TMP}/summary.py" "${OUT_FILE}")"
}

function test_status_lists_other_schedulers_read_only() {
  require_chezmoi || return 0
  cat >"${FAKE_BIN}/systemctl" <<'EOF'
#!/bin/bash
[ "$*" = "--user list-timers --all --no-pager --no-legend" ] || exit 64
printf 'Sat 2026-11-07 14:51:00 EST 1min 47s Sat 2026-11-07 14:49:00 EST 12s ago bob-ref-intake.timer bob-ref-intake.service\n'
EOF
  chmod +x "${FAKE_BIN}/systemctl"
  apply_all

  RUN_ENV=(CRONCTL_OS=Linux)
  run_cronctl status --all-schedulers athena

  assert_same "0" "${RC}"
  assert_contains "$(printf '%s\n' "  other schedulers (read-only):" \
    "    systemd bob-ref-intake.timer (activates bob-ref-intake.service; next, left, last, passed: Sat 2026-11-07 14:51:00 EST 1min 47s Sat 2026-11-07 14:49:00 EST 12s ago)")" \
    "$(cat "${OUT_FILE}")"
}

#############################
#  diff                     #
#############################
function test_diff_shows_the_block_outside_lines_and_retire_lines() {
  require_chezmoi || return 0
  write_table mac "# a comment" "${LEGACY_LINE}" "${WATCHDOG_LINE}"

  run_cronctl diff mac

  assert_same "0" "${RC}"
  # bash 3.2 misparses here-docs inside $(...), so the expectation goes to a file.
  cat >"${TEST_TMP}/expected" <<EOF
cronctl diff mac: the live crontab on Kellys-MacBook-Pro vs the block from the local chezmoi source
the live crontab has no managed block yet; sync would insert it at the top
--- block (live on mac)
+++ block (desired)
@@ -0,0 +1,6 @@
+# BEGIN chezmoi-cron (machine: mac; source: cron: in home/.chezmoidata.yaml; manage with cronctl)
+MAILTO=someone@example.com
+@hourly "\$HOME/bin/cronrun" hourly 'echo hourly'
+*/15 * * * * "\$HOME/bin/cronrun" sweep 'echo "it'\\''s \$(date +\\%Y) MAILTO=\$MAILTO SHELL=\$SHELL"; exit 3'
+# parked (disabled): 0 4 * * * "\$HOME/bin/cronrun" parked 'tman start'
+# END chezmoi-cron
unmanaged lines outside the block, which sync keeps (1): (plus 1 comment or blank line)
  ${WATCHDOG_LINE}
retire lines that sync would remove (1):
  ${LEGACY_LINE}
deployed ~/.config/cron/managed.crontab on mac: missing (not applied)
EOF
  assert_same "$(cat "${TEST_TMP}/expected")" "$(cat "${OUT_FILE}")"
  assert_no_stdin_leaks
}

function test_diff_previews_a_checkout_against_the_live_block() {
  require_chezmoi || return 0
  apply_all
  sed -i.bak 's/schedule: "30 3 \* \* \*"/schedule: "45 4 * * *"/' "${WORK}/home/.chezmoidata.yaml"

  run_cronctl diff athena --source "${WORK}"

  assert_same "0" "${RC}"
  assert_contains "the block from ${WORK}" "$(cat "${OUT_FILE}")"
  assert_contains "$(printf '%s\n' \
    '-30 3 * * * "$HOME/bin/cronrun" nightly '\''echo nightly'\''' \
    '+45 4 * * * "$HOME/bin/cronrun" nightly '\''echo nightly'\''')" "$(cat "${OUT_FILE}")"
  assert_contains "deployed ~/.config/cron/managed.crontab on athena: differs from the desired block (not applied there yet)" \
    "$(cat "${OUT_FILE}")"

  run_cronctl diff athena
  assert_contains "block: no changes" "$(cat "${OUT_FILE}")"
  assert_contains "managed.crontab on athena: matches the desired block" "$(cat "${OUT_FILE}")"
}

function test_diff_of_an_unreachable_machine_exits_3() {
  require_chezmoi || return 0
  touch "${MACHINES}/apollo/down"

  run_cronctl diff apollo

  assert_same "3" "${RC}"
  assert_contains "cronctl: apollo is unreachable over SSH (pending)" "$(cat "${ERR_FILE}")"
}

#############################
#  logs                     #
#############################
function test_logs_tails_the_right_file() {
  require_chezmoi || return 0
  local mac_state athena_state
  mac_state="$(home_of mac)/.local/state/cron"
  athena_state="$(home_of athena)/.local/state/cron"
  mkdir -p "${mac_state}" "${athena_state}"
  printf 'old 1\nold 2\n' >"${mac_state}/sweep.log.1"
  printf 'new 1\nnew 2\n' >"${mac_state}/sweep.log"
  printf 'athena nightly\n' >"${athena_state}/nightly.log"
  printf 'athena sweep\n' >"${athena_state}/sweep.log"

  run_cronctl logs sweep --machine mac -n 3
  assert_same "0" "${RC}"
  assert_same "$(printf '%s\n' "old 2" "new 1" "new 2")" "$(cat "${OUT_FILE}")"
  assert_contains "${mac_state}/sweep.log on Kellys-MacBook-Pro" "$(cat "${ERR_FILE}")"

  # The local machine needs no --machine and no SSH.
  : >"${SSH_LOG}"
  run_cronctl logs nightly
  assert_same "0" "${RC}"
  assert_same "athena nightly" "$(cat "${OUT_FILE}")"
  assert_empty "$(cat "${SSH_LOG}")"

  # sweep runs on mac only, so athena's stray sweep.log is not a default.
  run_cronctl logs sweep
  assert_same "2" "${RC}"
  assert_contains "sweep runs on mac, not on this host (athena); pass --machine M" "$(cat "${ERR_FILE}")"

  run_cronctl logs nightly --machine apollo
  assert_same "1" "${RC}"
  assert_contains "cronctl: no log for nightly on apollo" "$(cat "${ERR_FILE}")"

  touch "${MACHINES}/mac/down"
  run_cronctl logs sweep --machine mac
  assert_same "3" "${RC}"
  assert_no_stdin_leaks
}

#############################
#  run                      #
#############################
function test_run_executes_the_job_through_cronrun_as_cron_would() {
  require_chezmoi || return 0
  apply_all
  local mac_state
  mac_state="$(home_of mac)/.local/state/cron"

  run_cronctl run sweep --machine mac

  assert_same "3" "${RC}"
  assert_contains "cronctl run: running sweep on mac now, as cron would (real side effects)" \
    "$(cat "${ERR_FILE}")"
  assert_contains "cronrun: sweep failed (exit 3)" "$(cat "${ERR_FILE}")"
  assert_contains "cronctl run: sweep on mac exited 3; see cronctl logs sweep --machine mac" \
    "$(cat "${ERR_FILE}")"
  # The command arrived intact, with cron.env and cron's /bin/sh SHELL.
  assert_contains "it's $(date +%Y) MAILTO=someone@example.com SHELL=/bin/sh" \
    "$(cat "${mac_state}/sweep.log")"
  assert_contains "exit=3" "$(cat "${mac_state}/sweep.status")"

  run_cronctl run hourly
  assert_same "0" "${RC}"
  assert_contains "hourly" "$(cat "$(home_of athena)/.local/state/cron/hourly.log")"
  assert_no_stdin_leaks
}

function test_run_refuses_disabled_jobs_and_other_machines() {
  require_chezmoi || return 0
  run_cronctl run parked --machine mac
  assert_same "2" "${RC}"
  assert_contains "parked is disabled in the cron: data" "$(cat "${ERR_FILE}")"

  run_cronctl run nightly --machine mac
  assert_same "2" "${RC}"
  assert_contains "nightly does not run on mac (its machines: athena)" "$(cat "${ERR_FILE}")"

  run_cronctl run nosuch
  assert_same "2" "${RC}"
  assert_contains "unknown job: nosuch" "$(cat "${ERR_FILE}")"
  assert_empty "$(cat "${SSH_LOG}")"
}

#############################
#  edit                     #
#############################
function test_edit_checks_and_diffs_this_machine() {
  require_chezmoi || return 0
  apply_all
  : >"${SSH_LOG}"
  local data
  data="$(home_of athena)/.local/share/chezmoi/home/.chezmoidata.yaml"

  RUN_ENV=(EDITOR=fake-editor FAKE_EDIT='s/schedule: "30 3 \* \* \*"/schedule: "45 4 * * *"/')
  run_cronctl edit

  assert_same "0" "${RC}"
  assert_contains 'schedule: "45 4 * * *"' "$(cat "${data}")"
  local out
  out="$(cat "${OUT_FILE}")"
  assert_contains "cronctl check: ok (3 machines, 4 jobs;" "${out}"
  assert_contains "cronctl diff athena: the live crontab on athena" "${out}"
  assert_contains '+45 4 * * * "$HOME/bin/cronrun" nightly' "${out}"
  assert_contains "Nothing is installed yet. Next: commit and push the change" "${out}"
  assert_contains '`cronctl apply <machine>...`' "${out}"
  assert_empty "$(cat "${SSH_LOG}")"

  RUN_ENV=(EDITOR=fake-editor FAKE_EDIT='s/schedule: "45 4 \* \* \*"/schedule: "45 4 * *"/')
  run_cronctl edit
  assert_same "2" "${RC}"
  assert_contains "invalid schedule" "$(cat "${ERR_FILE}")"
  assert_contains "cronctl edit: fix ${data} before committing it" "$(cat "${ERR_FILE}")"
}

#############################
#  Streaming and help       #
#############################
# Proves the stdin guard is live: the same streamed routine, with the
# </dev/null taken off cronctl's git calls, lets git eat the trailer.
function test_a_child_reading_stdin_would_be_caught() {
  require_chezmoi || return 0
  local leaky="${TEST_TMP}/leaky-cronctl"
  sed 's|git -- "\$@" </dev/null|git -- "$@"|' "${SCRIPT}" >"${leaky}"
  if cmp -s "${SCRIPT}" "${leaky}"; then
    bashunit::fail "the sed no longer finds cronctl_git's </dev/null"
    return 0
  fi
  run_cronctl status mac
  assert_same "0" "${RC}"
  assert_no_stdin_leaks

  env -i HOME="$(home_of athena)" PATH="${FAKE_BIN}:/usr/bin:/bin:/usr/sbin:/sbin" \
    TMPDIR="${TEST_TMP}" CRONCTL_HOSTNAME=athena \
    "${BASH}" "${leaky}" status mac </dev/null >"${OUT_FILE}" 2>"${ERR_FILE}"

  assert_contains "read stdin: # trailer" "$(cat "${LEAK_LOG}")"
}

function test_every_fleet_command_has_help() {
  local command
  for command in status diff apply logs run edit; do
    run_cronctl "${command}" --help
    assert_same "0" "${RC}"
    assert_contains "usage: cronctl ${command} " "$(cat "${OUT_FILE}")"

    run_cronctl help "${command}"
    assert_same "0" "${RC}"
    assert_contains "usage: cronctl ${command} " "$(cat "${OUT_FILE}")"
  done
  run_cronctl run --help
  assert_contains "WARNING: this runs the job for real" "$(cat "${OUT_FILE}")"
  run_cronctl --help
  assert_contains "3 when at least one target" "$(cat "${OUT_FILE}")"
}

function test_fleet_usage_errors_exit_2() {
  require_chezmoi || return 0
  run_cronctl status --all athena
  assert_same "2" "${RC}"
  assert_contains "pass --all or machine names, not both" "$(cat "${ERR_FILE}")"

  run_cronctl status stranger
  assert_same "2" "${RC}"

  run_cronctl diff
  assert_same "2" "${RC}"
  assert_contains "missing <machine>" "$(cat "${ERR_FILE}")"

  run_cronctl logs nightly -n 0
  assert_same "2" "${RC}"

  run_cronctl edit extra
  assert_same "2" "${RC}"
  assert_empty "$(cat "${SSH_LOG}")"
}
