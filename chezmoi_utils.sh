#!/bin/bash

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

  printf "\n>>> %s\n" "$msg"
}
