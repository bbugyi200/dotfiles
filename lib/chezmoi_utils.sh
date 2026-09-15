#!/bin/bash

readonly COLOR_PURPLE='\033[38;5;5m'
readonly COLOR_RESET='\033[0m'

# Prints the root build directory to stdout.
function chez::build_dir_root() {
  echo "$HOME"/tmp/chezmoi_build
}

# Returns true when stdin has a TTY.
function chez::has_tty() {
  [[ -t 0 ]]
}

# Returns true when sudo can run without prompting, or can prompt on a TTY.
function chez::can_sudo() {
  sudo -n true &>/dev/null || chez::has_tty
}

# Log message to stdout.
#
# Arguments:
# ----------
# msg: The message to print.
# fmt_args: (optional) Arguments to format the message using printf.
function chez::log() {
  local msg
  if [[ "$#" -eq 1 ]]; then
    msg="$1"
    shift
  else
    msg="$(printf "$@")"
  fi

  printf "\n${COLOR_PURPLE}>>> %s${COLOR_RESET}\n" "$msg"
}

# Exit from an install script, soft-failing non-interactive chezmoi applies.
function chez::exit_install() {
  local rc="$1"
  if [[ "$rc" -eq 0 ]]; then
    exit 0
  fi

  if chez::has_tty; then
    exit "$rc"
  fi

  chez::log "WARNING: install failed or was skipped during a non-interactive chezmoi apply. It will retry on the next scheduled re-run. To force an earlier interactive retry, run: chezmoi state delete-bucket --bucket=scriptState && chezmoi apply"
  exit 0
}
