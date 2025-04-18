#!/bin/bash

source ~/lib/bugyi.sh

export USAGE_GRAMMAR=(
  "[-v]"
  "-h"
)

read -r -d '' DOC <<EOM
$(usage)

{% INSERT %}

Positional Arguments
--------------------

Optional Arguments
------------------
-h | --help
    View this help message.

-v | --verbose
    Enable verbose output. This option can be specified multiple times (e.g. -v, -vv, ...).

Examples
--------

EOM

function run() {
  parse_cli_args "$@"
}

function parse_cli_args() {
  log::debug "Command-Line Arguments: ($*)"

  eval set -- "$(getopt -o "h,v" -l "help,verbose" -- "$@")"

  VERBOSE=0
  while [[ -n "$1" ]]; do
    case $1 in
    -h | --help)
      echo "${DOC}"
      exit 0
      ;;
    -v | --verbose)
      VERBOSE=$((VERBOSE + 1))
      ;;
    --)
      shift
      break
      ;;
    esac
    shift
  done

  if [[ "${VERBOSE}" -gt 1 ]]; then
    PS4='$LINENO: '
    set -x
  fi

  readonly DOC
  readonly VERBOSE
}

if [[ "${SCRIPTNAME}" == "$(basename "${BASH_SOURCE[0]}")" ]]; then
  run "$@"
fi
