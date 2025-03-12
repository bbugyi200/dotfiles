#!/bin/bash

BUILD_DIR=$HOME/tmp/chezmoi_build

# Log message to stdout.
#
# Arguments:
# ----------
# msg: The message to print.
# fmt_args: (optional) Arguments to format the message using printf.
function util::log() {
  local msg
  if [[ "$#" -eq 1 ]]; then
    msg="$1"
    shift
  else
    msg="$(printf "$@")"
  fi

  printf "\n>>> %s\n" "$msg"
}
