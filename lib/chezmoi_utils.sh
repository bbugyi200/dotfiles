#!/bin/bash

readonly COLOR_PURPLE='\033[38;5;5m'
readonly COLOR_RESET='\033[0m'

# Prints the root build directory to stdout.
function chez::build_dir_root() {
  echo "$HOME"/tmp/chezmoi_build
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
