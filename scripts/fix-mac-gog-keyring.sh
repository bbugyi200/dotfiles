#!/bin/bash
# fix-mac-gog-keyring.sh - Move the Mac's gog tokens to the encrypted file keyring.
#
# Temporary migration helper. Run locally on the Mac in a GUI terminal
# (not over SSH): ~/.local/share/chezmoi/scripts/fix-mac-gog-keyring.sh
#
# With --check, run a read-only preflight and inventory. That mode is safe
# over SSH and changes nothing.

set -euo pipefail
umask 077

SCRIPT_NAME="fix-mac-gog-keyring.sh"
GOG_CONFIG_DIR="$HOME/.config/gogcli"

WORKDIR=""
PREV_BACKEND="auto"
CLIENT_LIST=""

cleanup() {
  if [ -n "$WORKDIR" ] && [ -d "$WORKDIR" ]; then
    for f in "$WORKDIR"/*; do
      if [ -e "$f" ]; then
        rm -P "$f" 2>/dev/null || rm -f "$f" 2>/dev/null || true
      fi
    done
    rm -rf "$WORKDIR" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

say() {
  printf "%s\n" "$1"
}

warn() {
  printf "warning: %s\n" "$1" >&2
}

die() {
  printf "error: %s\n" "$1" >&2
  exit "${2:-1}"
}

usage() {
  cat <<'EOF'
Usage: fix-mac-gog-keyring.sh [--check] [-h|--help]

Move the Mac's gog tokens from the macOS login keychain to the encrypted
file keyring so SSH agents can run `bob gmail draft` on the Mac.

  (no option)  Run the guided migration. Must run in a local Mac terminal,
               not over SSH, because only a local login unlocks the keychain.
  -c, --check  Read-only preflight and inventory. Safe over SSH. Changes nothing.
  -h, --help   Show this help and exit.
EOF
}

pause_enter() {
  printf "%s" "Press Enter to continue... "
  # shellcheck disable=SC2034
  read -r _dummy || true
}

ask_yes_no() {
  # $1 = prompt. Returns 0 on yes, 1 on no. Default is No.
  printf "%s [y/N] " "$1"
  read -r ans || ans=""
  case "$ans" in
    [yY]|[yY][eE][sS])
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "required command '$1' not found on PATH"
  fi
}

resolve_real_gog() {
  if [ -x "$HOME/.local/bin/gog" ]; then
    printf "%s" "$HOME/.local/bin/gog"
  elif [ -x "/opt/homebrew/bin/gog" ]; then
    printf "%s" "/opt/homebrew/bin/gog"
  else
    die "no real gog found (looked in ~/.local/bin/gog and /opt/homebrew/bin/gog)"
  fi
}

current_backend() {
  "$HOME/bin/gog" auth status --json 2>/dev/null | jq -r '.keyring.backend // empty' 2>/dev/null || true
}

list_clients() {
  # Print one client name per line, from credentials file names.
  # Uses only plain variables so it runs on bash 3.2.
  for f in "$GOG_CONFIG_DIR"/credentials-*.json; do
    if [ -f "$f" ]; then
      base=$(basename "$f")
      client=${base#credentials-}
      client=${client%.json}
      if [ -n "$client" ]; then
        printf "%s\n" "$client"
      fi
    fi
  done
  if [ -f "$GOG_CONFIG_DIR/credentials.json" ]; then
    printf "default\n"
  fi
}

cred_file_for() {
  if [ "$1" = "default" ]; then
    printf "%s" "$GOG_CONFIG_DIR/credentials.json"
  else
    printf "%s" "$GOG_CONFIG_DIR/credentials-$1.json"
  fi
}

keychain_account_for() {
  if [ "$1" = "default" ]; then
    printf "client/default/client-secret"
  else
    printf "client/%s/client-secret" "$1"
  fi
}

token_emails_keychain() {
  # $1 = client. Print one email per line from the keychain backend.
  # gog lists keys globally, so filter to this client's keys first.
  client="$1"
  out=""
  if [ "$client" = "default" ]; then
    out=$(GOG_KEYRING_BACKEND=keychain "$HOME/bin/gog" auth tokens list --json 2>/dev/null || true)
  else
    out=$(GOG_KEYRING_BACKEND=keychain "$HOME/bin/gog" --client "$client" auth tokens list --json 2>/dev/null || true)
  fi
  if [ -z "$out" ]; then
    return 0
  fi
  if [ "$client" = "default" ]; then
    printf "%s" "$out" | jq -r '.keys[]? // empty' 2>/dev/null | sed -e 's/^.*://' | sort -u || true
  else
    printf "%s" "$out" | jq -r --arg c "$client" '.keys[]? | select(contains(":"+$c+":")) // empty' 2>/dev/null | sed -e 's/^.*://' | sort -u || true
  fi
}

token_emails_file() {
  # $1 = client. Print one email per line from the file backend.
  client="$1"
  out=""
  if [ "$client" = "default" ]; then
    out=$("$HOME/bin/gog" auth tokens list --json 2>/dev/null || true)
  else
    out=$("$HOME/bin/gog" --client "$client" auth tokens list --json 2>/dev/null || true)
  fi
  if [ -z "$out" ]; then
    return 0
  fi
  if [ "$client" = "default" ]; then
    printf "%s" "$out" | jq -r '.keys[]? // empty' 2>/dev/null | sed -e 's/^.*://' | sort -u || true
  else
    printf "%s" "$out" | jq -r --arg c "$client" '.keys[]? | select(contains(":"+$c+":")) // empty' 2>/dev/null | sed -e 's/^.*://' | sort -u || true
  fi
}

has_file_bob_gmail_token() {
  out=$("$HOME/bin/gog" --client bob-gmail auth tokens list --json 2>/dev/null || true)
  if [ -z "$out" ]; then
    return 1
  fi
  if printf "%s" "$out" | jq -e '.keys[]? | select(contains("bob-gmail"))' >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

doctor_field() {
  # $1 = doctor json, $2 = check id, $3 = field (status|summary)
  printf "%s" "$1" | jq -r --arg id "$2" --arg f "$3" '.checks[] | select(.id==$id) | .[$f] // empty' 2>/dev/null || true
}

do_preflight() {
  say "Step 1: Preflight - checking this Mac can run the migration."
  say "Reason: the migration needs the real gog, the wrapper, and helpers."
  if [ "$(uname)" != "Darwin" ]; then
    die "this script must run on macOS (Darwin); uname says $(uname)"
  fi
  real_gog=$(resolve_real_gog)
  say "Real gog: $real_gog"
  if ! "$real_gog" auth tokens export --help >/dev/null 2>&1; then
    die "'$real_gog auth tokens export --help' failed; install gogcli 0.47.1 or newer"
  fi
  require_cmd "$HOME/bin/gog"
  # Also require the bare names the script calls.
  require_cmd pass
  require_cmd jq
  require_cmd bob
  require_cmd security
  # Require a non-empty keyring password without echoing it.
  if ! pass show gogcli/keyring-password 2>/dev/null | sed -n '1p' | grep -q '[^[:space:]]'; then
    die "pass show gogcli/keyring-password is empty or unreadable"
  fi
  say "pass keyring password: present (not shown)"
  which_gog=$(command -v gog 2>/dev/null || true)
  if [ "$which_gog" != "$HOME/bin/gog" ]; then
    warn "command -v gog resolves to '${which_gog:-not found}', expected $HOME/bin/gog"
    warn "Ledger Tools and Bob Mail reach the wrapper because GUI apps put ~/bin first on PATH."
  else
    say "command -v gog: $HOME/bin/gog"
  fi
  export BOB_GMAIL_GOG="$HOME/bin/gog"
  export BOB_GCAL_GOG="$HOME/bin/gog"
  backend=$(current_backend)
  if [ -z "$backend" ]; then
    backend="unknown"
  fi
  say "Current gog keyring backend: $backend"
}

do_inventory() {
  # Read-only inventory of what would migrate. Prints CLIENT_LIST global.
  say "Step 3: Inventory - listing keychain clients that would migrate."
  say "Reason: only migrate what the keychain actually holds."
  CLIENT_LIST=$(list_clients | sort -u)
  if [ -z "$CLIENT_LIST" ]; then
    say "No gog clients found in $GOG_CONFIG_DIR. Nothing to migrate."
    return 1
  fi
  say "Clients from config file names:"
  for c in $CLIENT_LIST; do
    say "  - $c ($(cred_file_for "$c"))"
  done
  say ""
  say "Token emails per client (keychain backend):"
  found_tokens=""
  for c in $CLIENT_LIST; do
    emails=$(token_emails_keychain "$c" || true)
    if [ -z "$emails" ]; then
      say "  - $c: no readable keychain tokens (locked over SSH, or none)"
    else
      say "  - $c:"
      for e in $emails; do
        say "      $e"
        found_tokens="yes"
      done
    fi
  done
  say ""
  say "Clients whose credentials file lacks client_secret (need keychain export):"
  for c in $CLIENT_LIST; do
    cf=$(cred_file_for "$c")
    secret=""
    if [ -f "$cf" ]; then
      secret=$(jq -r '.installed.client_secret // .client_secret // empty' "$cf" 2>/dev/null || true)
    fi
    if [ -z "$secret" ]; then
      say "  - $c: secret must come from the keychain"
    else
      say "  - $c: credentials file already has a secret"
    fi
  done
  if [ -z "$found_tokens" ]; then
    say ""
    say "Nothing to migrate: no keychain tokens readable. Exiting 0."
    return 1
  fi
  say ""
  say "Migration list: clients:$CLIENT_LIST"
  return 0
}

do_check() {
  say "=== $SCRIPT_NAME --check (read-only; changes nothing) ==="
  do_preflight
  say ""
  if [ -n "${SSH_CONNECTION:-}" ] || [ -n "${SSH_TTY:-}" ]; then
    say "SSH lock: SSH_CONNECTION or SSH_TTY is set, so the login keychain is locked."
    say "Expected: 'security find-generic-password -w' exits 36 and gog reports"
    say "the token could not be found in the keyring. Run the migration locally."
  else
    say "SSH lock: no SSH_CONNECTION/SSH_TTY; running in a local session."
  fi
  say ""
  # Best-effort read-only keychain probe; never triggers a dialog write.
  if security show-keychain-info >/dev/null 2>&1; then
    say "security show-keychain-info: readable (local session)"
  else
    say "security show-keychain-info: not readable (expected over SSH: User interaction is not allowed)"
  fi
  say ""
  if do_inventory; then
    say ""
    say "Expected keychain shape: six gogcli items (2 client-secrets, 2 tokens,"
    say "2 token-sub index entries) for bob-gmail and bob-gcal."
    say "--check complete: backend, inventory, and SSH lock reported; nothing changed."
  else
    say "--check complete: nothing to migrate; nothing changed."
  fi
}

do_export() {
  say "Step 4: Export - copying tokens and client secrets to a temp directory."
  say "Reason: copy everything first so a failure aborts before anything changes."
  WORKDIR=$(mktemp -d "${TMPDIR:-/tmp}/fix-mac-gog-keyring.XXXXXX")
  # shellcheck disable=SC2064
  say "Work directory: $WORKDIR (removed on exit)"
  n=0
  for c in $CLIENT_LIST; do
    emails=$(token_emails_keychain "$c" || true)
    if [ -z "$emails" ]; then
      die "no keychain token emails readable for client $c; aborting before any change"
    fi
    for email in $emails; do
      n=$((n + 1))
      out="$WORKDIR/token-$c-$n.json"
      say "Exporting token $c / $email (scopes only will be shown)..."
      if [ "$c" = "default" ]; then
        GOG_KEYRING_BACKEND=keychain "$HOME/bin/gog" auth tokens export "$email" --out "$out" --overwrite
      else
        GOG_KEYRING_BACKEND=keychain "$HOME/bin/gog" --client "$c" auth tokens export "$email" --out "$out" --overwrite
      fi
      chmod 600 "$out"
      if ! jq -e '.refresh_token | type=="string" and length>0' "$out" >/dev/null 2>&1; then
        die "exported token $out has an empty refresh_token; aborting before any change"
      fi
      scopes=$(jq -r '.scopes | if type=="array" then join(",") else tostring end' "$out" 2>/dev/null || true)
      say "  exported $email scopes: ${scopes:-unknown}"
    done
  done
  for c in $CLIENT_LIST; do
    cf=$(cred_file_for "$c")
    client_id=""
    if [ -f "$cf" ]; then
      client_id=$(jq -r '.installed.client_id // .client_id // empty' "$cf" 2>/dev/null || true)
    fi
    if [ -z "$client_id" ]; then
      die "cannot find client_id in $cf; aborting before any change"
    fi
    acct=$(keychain_account_for "$c")
    say ""
    say "Next, macOS will show a keychain dialog for $acct."
    say "Enter your login keychain password, then click Allow."
    pause_enter
    out="$WORKDIR/client-$c.json"
    # The secret flows from security straight into jq; it never lands in argv.
    if [ "$c" = "default" ]; then
      if security find-generic-password -s gogcli -a "$acct" -w 2>/dev/null | jq -n --rawfile s /dev/stdin --arg id "$client_id" '{installed:{client_id:$id, client_secret:$s}}' > "$out"; then
        :
      else
        security find-generic-password -s gogcli -a "client/client-secret" -w | jq -n --rawfile s /dev/stdin --arg id "$client_id" '{installed:{client_id:$id, client_secret:$s}}' > "$out"
      fi
    else
      security find-generic-password -s gogcli -a "$acct" -w | jq -n --rawfile s /dev/stdin --arg id "$client_id" '{installed:{client_id:$id, client_secret:$s}}' > "$out"
    fi
    chmod 600 "$out"
    if ! jq -e '.installed.client_secret | type=="string" and length>0' "$out" >/dev/null 2>&1; then
      die "exported client secret for $c is empty; aborting before any change"
    fi
    say "  saved $out (secret hidden)"
  done
  say ""
  say "Export complete. Nothing has been switched yet."
}

do_switch_import() {
  say "Step 5: Switch and import - moving tokens into the file keyring."
  say "Reason: the file keyring decrypts over SSH; the login keychain does not."
  PREV_BACKEND=$(current_backend)
  if [ -z "$PREV_BACKEND" ]; then
    PREV_BACKEND="auto"
  fi
  say "Previous backend: $PREV_BACKEND"
  say "This will run: ~/bin/gog auth keyring file"
  if ! ask_yes_no "Switch the gog keyring backend to file?"; then
    die "declined to switch backend; work directory will be cleaned up"
  fi
  if ! "$HOME/bin/gog" auth keyring file; then
    die "failed to switch backend to file"
  fi
  restore_and_fail() {
    printf "error: %s\n" "$1" >&2
    printf "Restoring previous backend: %s\n" "$PREV_BACKEND" >&2
    "$HOME/bin/gog" auth keyring "$PREV_BACKEND" 2>/dev/null || true
    say "Keychain items were left untouched, so rollback loses nothing."
    exit 1
  }
  for c in $CLIENT_LIST; do
    cf="$WORKDIR/client-$c.json"
    if [ ! -f "$cf" ]; then
      restore_and_fail "missing exported client file for $c"
    fi
    say "Storing credentials for $c..."
    if [ "$c" = "default" ]; then
      "$HOME/bin/gog" auth credentials set "$cf" || restore_and_fail "credentials set failed for $c"
    else
      "$HOME/bin/gog" --client "$c" auth credentials set "$cf" || restore_and_fail "credentials set failed for $c"
    fi
  done
  for f in "$WORKDIR"/token-*.json; do
    if [ -f "$f" ]; then
      say "Importing $(basename "$f")..."
      "$HOME/bin/gog" auth tokens import "$f" || restore_and_fail "token import failed for $f"
    fi
  done
  say "Switch and import complete."
}

do_verify() {
  say "Step 6: Verify - checking Gmail, Gcal, and a fresh login shell."
  say "Reason: prove SSH agents can now decrypt the file keyring."
  gmail_json=$(bob gmail doctor -f json 2>/dev/null || true)
  if [ -z "$gmail_json" ]; then
    die "bob gmail doctor produced no JSON"
  fi
  gmail_token=$(doctor_field "$gmail_json" "token" "status")
  gmail_scopes=$(doctor_field "$gmail_json" "scopes" "summary")
  say "bob gmail doctor: token=$gmail_token scopes=$gmail_scopes"
  if [ "$gmail_token" != "ok" ]; then
    die "bob gmail doctor token check is '$gmail_token', expected 'ok'"
  fi
  if [ "$gmail_scopes" = "readonly" ]; then
    say "Gmail scopes are readonly; compose is needed for drafts."
    if ask_yes_no "Run 'bob gmail login -s compose' now (opens a browser)?"; then
      bob gmail login -s compose
      gmail_json=$(bob gmail doctor -f json 2>/dev/null || true)
      gmail_token=$(doctor_field "$gmail_json" "token" "status")
      gmail_scopes=$(doctor_field "$gmail_json" "scopes" "summary")
      say "After login: token=$gmail_token scopes=$gmail_scopes"
      if [ "$gmail_token" != "ok" ]; then
        die "gmail token still '$gmail_token' after login"
      fi
    else
      warn "skipped compose consent; drafts need readonly+compose"
    fi
  fi
  gcal_json=$(bob gcal doctor -f json 2>/dev/null || true)
  if [ -z "$gcal_json" ]; then
    warn "bob gcal doctor produced no JSON"
  else
    gcal_token=$(doctor_field "$gcal_json" "token" "status")
    say "bob gcal doctor: token=$gcal_token"
    if [ "$gcal_token" != "ok" ]; then
      warn "bob gcal doctor token is '$gcal_token' (warning only)"
    fi
  fi
  cur_user="${USER:-}"
  if [ -z "$cur_user" ]; then
    cur_user=$(id -un 2>/dev/null || printf "unknown")
  fi
  cur_logname="${LOGNAME:-$cur_user}"
  say "Checking a fresh login shell (mimics the SSH recipe)..."
  login_json=$(env -i HOME="$HOME" USER="$cur_user" LOGNAME="$cur_logname" /bin/zsh -lc 'bob gmail doctor -f json' 2>/dev/null || true)
  if [ -z "$login_json" ]; then
    die "fresh login shell produced no bob gmail doctor JSON; check that zsh resolves ~/bin/gog"
  fi
  login_token=$(doctor_field "$login_json" "token" "status")
  say "Fresh login shell: gmail token=$login_token"
  if [ "$login_token" != "ok" ]; then
    die "fresh login shell gmail token is '$login_token', expected 'ok'"
  fi
  say ""
  say "The six keychain items are now unused (2 client-secrets, 2 tokens,"
  say "2 token-sub index entries for bob-gmail and bob-gcal)."
  say "They stay as an instant rollback path. To roll back, run:"
  say "  ~/bin/gog auth keyring auto"
}

do_finish() {
  say "Step 7: Finish."
  say "Summary: the Mac's gog now uses the encrypted file keyring."
  say "Reminders:"
  say "  - After a Mac reboot, pass may need the GPG passphrase once in a local"
  say "    terminal before SSH agents can decrypt."
  say "  - Next, answer the SASE gate so it can verify from apollo."
}

do_migrate() {
  if [ -n "${SSH_CONNECTION:-}" ] || [ -n "${SSH_TTY:-}" ]; then
    die "refusing to migrate over SSH (SSH_CONNECTION or SSH_TTY is set). The login keychain is locked to SSH sessions; run this script in a local Mac terminal." 2
  fi
  say "=== $SCRIPT_NAME: guided Mac gog file-keyring migration ==="
  say ""
  do_preflight
  say ""
  backend_now=$(current_backend)
  if [ "$backend_now" = "file" ] && has_file_bob_gmail_token; then
    say "Step 2: Fast path - backend is already file with a bob-gmail token. Skipping to verify."
    say ""
    do_verify
    say ""
    do_finish
    return 0
  fi
  say "Step 2: Fast path - migration is still needed (backend=$backend_now)."
  say ""
  if ! do_inventory; then
    return 0
  fi
  say ""
  do_export
  say ""
  do_switch_import
  say ""
  do_verify
  say ""
  do_finish
}

MODE="migrate"
for arg in ${1+"$@"}; do
  case "$arg" in
    -h|--help)
      usage
      exit 0
      ;;
    -c|--check)
      MODE="check"
      ;;
    --)
      ;;
    -*)
      printf "error: unknown option %s\n" "$arg" >&2
      usage >&2
      exit 2
      ;;
    *)
      printf "error: unexpected argument %s\n" "$arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ "$MODE" = "check" ]; then
  do_check
else
  do_migrate
fi

