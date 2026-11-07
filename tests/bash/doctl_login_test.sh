#!/bin/bash

################################################################################
# Regression tests for athena's guided DigitalOcean token setup/check script.  #
################################################################################

SCRIPT="$PWD/home/bin/executable_doctl_login"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="$TEST_TMP/bin"
  TEST_HOME="$TEST_TMP/home"
  XDG_HOME="$TEST_TMP/xdg"
  EVENT_LOG="$TEST_TMP/events.log"
  STDOUT_FILE="$TEST_TMP/stdout.log"
  STDERR_FILE="$TEST_TMP/stderr.log"
  TOKEN_FILE="$XDG_HOME/saved-token"
  ACCOUNT_FILE="$TEST_TMP/account.json"
  DROPLETS_FILE="$TEST_TMP/droplets.json"
  VALID_INFO_FILE="$TEST_TMP/valid-info.json"
  EXTRA_WRITE_INFO_FILE="$TEST_TMP/extra-write-info.json"
  MISSING_INFO_FILE="$TEST_TMP/missing-info.json"
  EXTRA_READ_INFO_FILE="$TEST_TMP/extra-read-info.json"
  EXPIRING_INFO_FILE="$TEST_TMP/expiring-info.json"
  TOKEN_A="dop_v1_$(printf 'a%.0s' {1..64})"
  TOKEN_B="dop_v1_$(printf 'b%.0s' {1..64})"
  TOKEN_C="dop_v1_$(printf 'c%.0s' {1..64})"
  TOKEN_D="dop_v1_$(printf 'd%.0s' {1..64})"
  TOKEN_E="dop_v1_$(printf 'e%.0s' {1..64})"
  TOKEN_F="dop_v1_$(printf 'f%.0s' {1..64})"
  PROMPT_INPUT=""
  USE_INPUT=0
  ASSUME_TTY=0
  PATH_OVERRIDE=""
  CURL_FAIL=0
  AMBIENT_OVERRIDE=0
  STUB_CONFIG_MODE=600
  AUTH_LIST_JSON='[{"name":"default","current":true}]'
  SSH_IP="159.223.165.54"
  DROPLETS_JSON='[{"id":424242,"name":"apollo","status":"active","region":{"slug":"nyc3"},"networks":{"v4":[{"ip_address":"159.223.165.54","type":"public"}]}}]'
  RUN_RC=0

  mkdir -p "$FAKE_BIN" "$TEST_HOME" "$XDG_HOME/doctl"
  : >"$EVENT_LOG"
  printf '{"email":"fixture@example.invalid","status":"active"}\n' >"$ACCOUNT_FILE"
  printf '%s\n' "$DROPLETS_JSON" >"$DROPLETS_FILE"
  printf '{"scopes":["account:read","actions:read","droplet:read","droplet:update","image:read","regions:read","sizes:read","snapshot:read"],"expires_in_seconds":0}\n' >"$VALID_INFO_FILE"
  printf '{"scopes":["account:read","actions:read","droplet:read","droplet:update","image:read","regions:read","sizes:read","snapshot:read","droplet:delete"],"expires_in_seconds":0}\n' >"$EXTRA_WRITE_INFO_FILE"
  printf '{"scopes":["account:read","actions:read","droplet:read","droplet:update","image:read","regions:read","snapshot:read"],"expires_in_seconds":0}\n' >"$MISSING_INFO_FILE"
  printf '{"scopes":["account:read","actions:read","droplet:read","droplet:update","image:read","regions:read","sizes:read","snapshot:read","tag:read"],"expires_in_seconds":0}\n' >"$EXTRA_READ_INFO_FILE"
  printf '{"scopes":["account:read","actions:read","droplet:read","droplet:update","image:read","regions:read","sizes:read","snapshot:read"],"expires_in_seconds":86400}\n' >"$EXPIRING_INFO_FILE"

  write_doctl_stub
  write_curl_stub
  write_ssh_stub
}

function tear_down() {
  python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1])' "$TEST_TMP"
}

function write_doctl_stub() {
  cat >"$FAKE_BIN/doctl" <<'STUB'
#!/bin/bash
printf 'doctl' >>"$EVENT_LOG"
for arg in "$@"; do printf ' <%s>' "$arg" >>"$EVENT_LOG"; done
printf '\n' >>"$EVENT_LOG"
if [[ -n "$DIGITALOCEAN_ACCESS_TOKEN" ]]; then
  printf 'ambient-env=present\n' >>"$EVENT_LOG"
fi
while (($# > 0)); do
  case "$1" in
  --context) shift 2 ;;
  --*) shift ;;
  *) break ;;
  esac
done
case "$1" in
version) printf 'doctl version 2.3.0-release\n' ;;
auth)
  shift
  case "$1" in
  token) [[ -f "$TOKEN_FILE" ]] && cat "$TOKEN_FILE" ;;
  init)
    if [[ -z "$DIGITALOCEAN_ACCESS_TOKEN" ]]; then exit 1; fi
    printf 'auth-init-env=set\n' >>"$EVENT_LOG"
    printf '%s' "$DIGITALOCEAN_ACCESS_TOKEN" >"$TOKEN_FILE"
    printf 'fixture\n' >"$XDG_CONFIG_HOME/doctl/config.yaml"
    chmod "$STUB_CONFIG_MODE" "$XDG_CONFIG_HOME/doctl/config.yaml"
    ;;
  remove) : >"$TOKEN_FILE" ;;
  list) printf '%s\n' "$AUTH_LIST_JSON" ;;
  esac
  ;;
account) cat "$ACCOUNT_FILE" ;;
compute) cat "$DROPLETS_FILE" ;;
*) printf 'unexpected doctl command\n' >&2; exit 2 ;;
esac
STUB
  chmod +x "$FAKE_BIN/doctl"
}

function write_curl_stub() {
  cat >"$FAKE_BIN/curl" <<'STUB'
#!/bin/bash
printf 'curl' >>"$EVENT_LOG"
for arg in "$@"; do printf ' <%s>' "$arg" >>"$EVENT_LOG"; done
printf '\n' >>"$EVENT_LOG"
out_file=""
http_code=200
while (($# > 0)); do
  case "$1" in
  -o) out_file="$2"; shift 2 ;;
  -w|-H|--max-time) shift 2 ;;
  *) shift ;;
  esac
done
IFS= read -r auth_header || true
case "$auth_header" in
*a) fixture="$VALID_INFO_FILE" ;;
*b) fixture="$EXTRA_WRITE_INFO_FILE" ;;
*c) fixture="$MISSING_INFO_FILE" ;;
*d) fixture="$EXTRA_READ_INFO_FILE" ;;
*e) fixture="$EXPIRING_INFO_FILE" ;;
*f) fixture=""; http_code=401 ;;
*) fixture="$VALID_INFO_FILE" ;;
esac
printf 'curl-header-present=%s\n' "$([[ -n "$auth_header" ]] && printf yes || printf no)" >>"$EVENT_LOG"
if [[ "$CURL_FAIL" == "1" ]]; then exit 7; fi
if [[ -n "$fixture" ]]; then
  cat "$fixture" >"$out_file"
else
  printf '{"error":"unauthorized"}\n' >"$out_file"
fi
printf '%s' "$http_code"
STUB
  chmod +x "$FAKE_BIN/curl"
}

function write_ssh_stub() {
  cat >"$FAKE_BIN/ssh" <<'STUB'
#!/bin/bash
printf 'ssh' >>"$EVENT_LOG"
for arg in "$@"; do printf ' <%s>' "$arg" >>"$EVENT_LOG"; done
printf '\n' >>"$EVENT_LOG"
if [[ "$1" == "-G" && "$2" == "apollo-do" ]]; then printf 'hostname %s\n' "$SSH_IP"; fi
STUB
  chmod +x "$FAKE_BIN/ssh"
}

function set_saved_token() {
  printf '%s' "$1" >"$TOKEN_FILE"
}

function run_doctl_login() {
  local run_path="$FAKE_BIN:$PATH"
  if [[ -n "$PATH_OVERRIDE" ]]; then run_path="$PATH_OVERRIDE"; fi
  if (
    unset DIGITALOCEAN_ACCESS_TOKEN
    export PATH="$run_path" HOME="$TEST_HOME" XDG_CONFIG_HOME="$XDG_HOME"
    export EVENT_LOG TOKEN_FILE ACCOUNT_FILE DROPLETS_FILE
    export VALID_INFO_FILE EXTRA_WRITE_INFO_FILE MISSING_INFO_FILE EXTRA_READ_INFO_FILE EXPIRING_INFO_FILE
    export STUB_CONFIG_MODE AUTH_LIST_JSON SSH_IP CURL_FAIL DOCTL_LOGIN_ASSUME_TTY="$ASSUME_TTY"
    if [[ "$AMBIENT_OVERRIDE" == "1" ]]; then
      export DIGITALOCEAN_ACCESS_TOKEN="$TOKEN_F"
    fi
    if [[ "$USE_INPUT" == "1" ]]; then
      printf '%s\n' "$PROMPT_INPUT" | bash "$SCRIPT" "$@"
    else
      bash "$SCRIPT" "$@"
    fi
  ) >"$STDOUT_FILE" 2>"$STDERR_FILE"; then
    RUN_RC=0
  else
    RUN_RC=$?
  fi
}

function assert_no_fake_tokens() {
  local output
  output="$(cat "$STDOUT_FILE" "$STDERR_FILE" "$EVENT_LOG")"
  assert_not_contains "$TOKEN_A" "$output"
  assert_not_contains "$TOKEN_B" "$output"
  assert_not_contains "$TOKEN_C" "$output"
  assert_not_contains "$TOKEN_D" "$output"
  assert_not_contains "$TOKEN_E" "$output"
  assert_not_contains "$TOKEN_F" "$output"
}

function test_help_and_usage_errors() {
  run_doctl_login -h
  assert_equals "0" "$RUN_RC"
  assert_equals "" "$(cat "$STDOUT_FILE")"
  local options
  options="$(grep '^  -[hlry],' "$STDERR_FILE")"
  assert_contains "-h, --help" "$options"
  assert_contains "-l, --logout" "$options"
  assert_contains "-r, --replace" "$options"
  assert_contains "-y, --yes" "$options"
  assert_contains "a rerun is a" "$(cat "$STDERR_FILE")"
  assert_contains "DOCTL_LOGIN_ASSUME_TTY=1" "$(cat "$STDERR_FILE")"
  assert_contains "Exit status:" "$(cat "$STDERR_FILE")"
  assert_contains "snapshot:read" "$(cat "$STDERR_FILE")"
  run_doctl_login --unknown
  assert_equals "2" "$RUN_RC"
  run_doctl_login unexpected
  assert_equals "2" "$RUN_RC"
  run_doctl_login -l -r
  assert_equals "2" "$RUN_RC"
  run_doctl_login -y
  assert_equals "2" "$RUN_RC"
}

function test_already_connected_without_terminal_is_read_only() {
  set_saved_token "$TOKEN_A"
  run_doctl_login
  assert_equals "0" "$RUN_RC"
  assert_contains "already connected" "$(cat "$STDERR_FILE")"
  assert_contains "id 424242" "$(cat "$STDERR_FILE")"
  assert_equals "" "$(cat "$STDOUT_FILE")"
  assert_not_contains "auth init" "$(cat "$EVENT_LOG")"
  assert_not_contains "auth remove" "$(cat "$EVENT_LOG")"
  assert_no_fake_tokens
}

function test_fresh_setup_saves_token_without_putting_it_in_argv_or_output() {
  PROMPT_INPUT="$TOKEN_A"
  USE_INPUT=1
  ASSUME_TTY=1
  run_doctl_login
  assert_equals "0" "$RUN_RC"
  assert_equals "$TOKEN_A" "$(cat "$TOKEN_FILE")"
  assert_equals "600" "$(stat -c '%a' "$XDG_HOME/doctl/config.yaml")"
  assert_contains "auth-init-env=set" "$(cat "$EVENT_LOG")"
  assert_contains "id 424242" "$(cat "$STDERR_FILE")"
  assert_no_fake_tokens
}

function test_missing_scope_is_named_and_never_saved() {
  PROMPT_INPUT="$TOKEN_C"$'\nq'
  USE_INPUT=1
  ASSUME_TTY=1
  run_doctl_login
  assert_equals "1" "$RUN_RC"
  assert_contains "missing scopes: sizes:read" "$(cat "$STDERR_FILE")"
  assert_not_contains "auth-init-env=set" "$(cat "$EVENT_LOG")"
  assert_no_fake_tokens
}

function test_extra_write_scope_is_refused_but_extra_read_scope_is_accepted() {
  PROMPT_INPUT="$TOKEN_B"$'\nq'
  USE_INPUT=1
  ASSUME_TTY=1
  run_doctl_login
  assert_equals "1" "$RUN_RC"
  assert_contains "extra scopes refused: droplet:delete" "$(cat "$STDERR_FILE")"
  assert_not_contains "auth-init-env=set" "$(cat "$EVENT_LOG")"
  assert_no_fake_tokens
  PROMPT_INPUT="$TOKEN_D"
  run_doctl_login
  assert_equals "0" "$RUN_RC"
  assert_contains "also has read-only scopes: tag:read" "$(cat "$STDERR_FILE")"
  assert_equals "$TOKEN_D" "$(cat "$TOKEN_FILE")"
  assert_no_fake_tokens
}

function test_expiring_token_warns_but_is_saved() {
  PROMPT_INPUT="$TOKEN_E"
  USE_INPUT=1
  ASSUME_TTY=1
  run_doctl_login
  assert_equals "0" "$RUN_RC"
  assert_contains "expires " "$(cat "$STDERR_FILE")"
  assert_contains "No-expiry token" "$(cat "$STDERR_FILE")"
  assert_equals "$TOKEN_E" "$(cat "$TOKEN_FILE")"
  assert_no_fake_tokens
}

function test_no_token_without_terminal_never_prompts() {
  run_doctl_login
  assert_equals "1" "$RUN_RC"
  assert_contains "no token saved" "$(cat "$STDERR_FILE")"
  assert_contains "in a terminal on athena" "$(cat "$STDERR_FILE")"
  assert_not_contains "Paste the token" "$(cat "$STDERR_FILE")"
  assert_not_contains "curl <" "$(cat "$EVENT_LOG")"
  assert_no_fake_tokens
}

function test_saved_rejected_token_prompts_and_replaces_it() {
  set_saved_token "$TOKEN_F"
  PROMPT_INPUT="$TOKEN_F"$'\n'"$TOKEN_A"
  USE_INPUT=1
  ASSUME_TTY=1
  run_doctl_login
  assert_equals "0" "$RUN_RC"
  assert_contains "stopped working" "$(cat "$STDERR_FILE")"
  assert_contains "DigitalOcean rejected this token" "$(cat "$STDERR_FILE")"
  assert_equals "$TOKEN_A" "$(cat "$TOKEN_FILE")"
  assert_contains "auth-init-env=set" "$(cat "$EVENT_LOG")"
  assert_no_fake_tokens
}

function test_curl_failure_exits_without_prompting() {
  set_saved_token "$TOKEN_A"
  CURL_FAIL=1
  run_doctl_login
  assert_equals "1" "$RUN_RC"
  assert_contains "could not reach cloud.digitalocean.com" "$(cat "$STDERR_FILE")"
  assert_not_contains "Paste the token" "$(cat "$STDERR_FILE")"
  assert_no_fake_tokens
}

function test_apollo_can_be_found_by_ssh_ip_or_reported_missing() {
  set_saved_token "$TOKEN_A"
  DROPLETS_JSON='[{"id":7,"name":"different-name","status":"active","region":{"slug":"nyc3"},"networks":{"v4":[{"ip_address":"159.223.165.54","type":"public"}]}}]'
  printf '%s\n' "$DROPLETS_JSON" >"$DROPLETS_FILE"
  run_doctl_login
  assert_equals "0" "$RUN_RC"
  assert_contains "different-name · id 7" "$(cat "$STDERR_FILE")"
  assert_contains "apollo-do" "$(cat "$EVENT_LOG")"
  assert_no_fake_tokens
  DROPLETS_JSON='[{"id":8,"name":"unrelated","status":"active","region":{"slug":"nyc3"},"networks":{"v4":[{"ip_address":"10.0.0.8","type":"public"}]}}]'
  printf '%s\n' "$DROPLETS_JSON" >"$DROPLETS_FILE"
  run_doctl_login
  assert_equals "0" "$RUN_RC"
  assert_contains "no droplet named apollo or at 159.223.165.54" "$(cat "$STDERR_FILE")"
  assert_contains "found: unrelated" "$(cat "$STDERR_FILE")"
  assert_no_fake_tokens
}

function test_replace_prompts_even_when_connected_and_requires_terminal() {
  set_saved_token "$TOKEN_A"
  run_doctl_login -r
  assert_equals "1" "$RUN_RC"
  assert_contains "-r needs a terminal" "$(cat "$STDERR_FILE")"
  PROMPT_INPUT="$TOKEN_A"
  USE_INPUT=1
  ASSUME_TTY=1
  run_doctl_login -r
  assert_equals "0" "$RUN_RC"
  assert_contains "old token works until you revoke it" "$(cat "$STDERR_FILE")"
  assert_contains "auth-init-env=set" "$(cat "$EVENT_LOG")"
  assert_no_fake_tokens
}

function test_logout_yes_removes_token_and_prints_revoke_url() {
  run_doctl_login -l
  assert_equals "0" "$RUN_RC"
  assert_contains "nothing to remove" "$(cat "$STDERR_FILE")"

  set_saved_token "$TOKEN_A"
  run_doctl_login -l -y
  assert_equals "0" "$RUN_RC"
  assert_equals "" "$(cat "$TOKEN_FILE")"
  assert_contains "https://cloud.digitalocean.com/account/api/tokens" "$(cat "$STDERR_FILE")"
  assert_contains "<auth> <remove>" "$(cat "$EVENT_LOG")"
  assert_no_fake_tokens
}

function test_warns_when_plain_doctl_context_is_not_default() {
  set_saved_token "$TOKEN_A"
  AUTH_LIST_JSON='[{"name":"default","current":false},{"name":"backup","current":true}]'
  run_doctl_login
  assert_equals "0" "$RUN_RC"
  assert_contains "plain doctl commands use context backup" "$(cat "$STDERR_FILE")"
  assert_contains "doctl auth switch --context default" "$(cat "$STDERR_FILE")"
  assert_no_fake_tokens
}

function test_ambient_token_override_is_unset_and_reported() {
  set_saved_token "$TOKEN_A"
  AMBIENT_OVERRIDE=1
  run_doctl_login
  assert_equals "0" "$RUN_RC"
  assert_contains "DIGITALOCEAN_ACCESS_TOKEN overrides the saved token" "$(cat "$STDERR_FILE")"
  assert_not_contains "ambient-env=present" "$(cat "$EVENT_LOG")"
  assert_no_fake_tokens
}

function test_logout_without_terminal_confirmation_removes_nothing() {
  set_saved_token "$TOKEN_A"
  run_doctl_login -l
  assert_equals "1" "$RUN_RC"
  assert_equals "$TOKEN_A" "$(cat "$TOKEN_FILE")"
  assert_contains "Pass -y" "$(cat "$STDERR_FILE")"
  assert_not_contains "auth remove" "$(cat "$EVENT_LOG")"
  assert_no_fake_tokens
}

function test_missing_binary_and_config_permissions() {
  PATH_OVERRIDE="/usr/bin:/bin"
  run_doctl_login
  assert_equals "1" "$RUN_RC"
  assert_contains "doctl not found" "$(cat "$STDERR_FILE")"
  assert_contains "chezmoi apply" "$(cat "$STDERR_FILE")"
  PATH_OVERRIDE=""
  PROMPT_INPUT="$TOKEN_A"
  USE_INPUT=1
  ASSUME_TTY=1
  STUB_CONFIG_MODE=644
  run_doctl_login
  assert_equals "0" "$RUN_RC"
  assert_equals "600" "$(stat -c '%a' "$XDG_HOME/doctl/config.yaml")"
  assert_contains "Tightened doctl config permissions to 600" "$(cat "$STDERR_FILE")"
  assert_no_fake_tokens
}

function render_ignore() {
  local host="$1"
  sed "s/\\.chezmoi\\.hostname/\"$host\"/g" home/.chezmoiignore |
    chezmoi execute-template
}

function test_host_isolation_ignores_script_except_on_athena() {
  assert_contains "bin/doctl_login" "$(render_ignore apollo)"
  assert_contains "bin/doctl_login" "$(render_ignore Kellys-MacBook-Pro)"
  assert_not_contains "bin/doctl_login" "$(render_ignore athena)"
}
