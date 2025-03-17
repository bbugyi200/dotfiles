#!/bin/bash

################################################
#  Global Utility Functions for Shell Scripts  #
################################################
if [[ "${BUGYI_HAS_BEEN_SOURCED}" != true ]]; then
  readonly BUGYI_HAS_BEEN_SOURCED=true

  # ---------- Global Variables ----------
  readonly COLOR_GREEN='\033[38;5;2m'
  readonly COLOR_PURPLE='\033[38;5;5m'
  readonly COLOR_RED='\033[38;5;1m'
  readonly COLOR_RESET='\033[0m'
  readonly COLOR_YELLOW='\033[38;5;3m'
  readonly SCRIPTNAME="$(basename "$0")"

  if [[ -n "${BASH}" ]]; then
    MY_SHELL=bash
  elif [[ -n "${ZSH_NAME}" ]]; then
    MY_SHELL=zsh
  else
    MY_SHELL=unknown
  fi
  readonly MY_SHELL

  # ---------- XDG User Directories ----------
  # shellcheck disable=SC2034
  if [[ -n "${XDG_RUNTIME_DIR}" ]]; then
    XDG_RUNTIME="${XDG_RUNTIME_DIR}"
  else
    XDG_RUNTIME=/tmp
  fi
  readonly XDG_RUNTIME

  # shellcheck disable=SC2034
  if [[ -n "${XDG_CONFIG_HOME}" ]]; then
    XDG_CONFIG="${XDG_CONFIG_HOME}"
  else
    XDG_CONFIG="${HOME}"/.config
  fi
  readonly XDG_CONFIG

  # shellcheck disable=SC2034
  if [[ -n "${XDG_DATA_HOME}" ]]; then
    XDG_DATA="${XDG_DATA_HOME}"
  else
    XDG_DATA="${HOME}"/.local/share
  fi
  readonly XDG_DATA

  # shellcheck disable=SC2034
  readonly MY_XDG_RUNTIME="${XDG_RUNTIME}"/"${SCRIPTNAME}"
  # shellcheck disable=SC2034
  readonly MY_XDG_CONFIG="${XDG_CONFIG}"/"${SCRIPTNAME}"
  # shellcheck disable=SC2034
  readonly MY_XDG_DATA="${XDG_DATA}"/"${SCRIPTNAME}"
fi

#################################################################################
# Convenience function used to terminate a script early with a non-zero exit
# status.
#
# Usage
# -----
# die [-x N] MESSAGE [FMT_ARGS [...]]
#
# Positional Arguments
# --------------------
# MESSAGE
#     The error message to log before terminating the script (accepts
#     printf-style format arguments).
#
# FMT_ARGS
#     printf-style format arguments.
#
#
# Optional Arguments
# ------------------
# -x N | --exit-code N
#     Terminate the script with exit code N. Defaults to 1.
#################################################################################
function die() {
  local exit_code
  if [[ "$1" == "--exit-code" || "$1" == "-x" ]]; then
    shift

    exit_code="$1"
    shift
  elif [[ "$1" == "-x"* ]]; then
    exit_code="${1:2}"
    shift
  else
    exit_code=1
  fi

  local message
  if [[ "$#" -eq 1 ]]; then
    message="$1"
    shift
  else
    message="$(printf "$@")"
  fi

  # An exit code of 2 is used to indicate an error occurred while parsing
  # command-line arguments, so we treat this as a special case with a special
  # error message.
  if [[ "${exit_code}" -eq 2 ]]; then
    message="Failed while parsing command-line arguments. Try '${SCRIPTNAME} --help' for more information.\n\n${message}"
  fi

  log::error --up 1 "${message}"
  exit "${exit_code}"
}

#################################################################################
# The following helper functions are used to provide some primitive logging
# capability from bash scripts.
#
# Usage
# -----
# log::debug [-u N] MESSAGE [FMT_ARGS [...]]  # log debug message
# log::error [-u N] MESSAGE [FMT_ARGS [...]]  # log error message
# log::info [-u N] MESSAGE [FMT_ARGS [...]]  # log info message
# log::warn [-u N] MESSAGE [FMT_ARGS [...]]  # log warning message
#
# Positional Arguments
# --------------------
# MESSAGE
#     The message to log (accepts printf-style format arguments).
#
# FMT_ARGS
#     printf-style format arguments.
#
# Optional Arguments
# ------------------
# -u N | --up N
#     Use this option to specify that we go forward in the stack N times before
#     crawling for metadata to be used to decorate our log message (e.g. line
#     number, script name, function name).
#################################################################################
function log::debug() { if [[ "${DEBUG}" = true || "${VERBOSE}" -gt 0 ]]; then _log "debug" "${COLOR_PURPLE}" "$@"; fi; }
function log::error() { _log "error" "${COLOR_RED}" "$@"; }
function log::info() { _log "info" "${COLOR_GREEN}" "$@"; }
function log::warn() { _log "warning" "${COLOR_YELLOW}" "$@"; }
function _log() {
  local level="$1"
  shift

  local color="$1"
  shift

  if [[ "${DISABLE_LOG_COLOR}" == true ]]; then
    color="${COLOR_RESET}"
  fi

  local up
  if [[ "$1" == "--up" || "$1" == "-u" ]]; then
    shift

    up=$(($1 + 1))
    shift
  elif [[ "$1" == "-u"* ]]; then
    up=$((${1:2} + 1))
    shift
  else
    up=1
  fi

  local message
  if [[ "$#" -eq 1 ]]; then
    message="$1"
    shift
  else
    message="$(printf "$@")"
  fi

  if [[ "${MY_SHELL}" == "bash" ]]; then
    # shellcheck disable=SC2207
    local caller_info=($(caller "${up}"))

    local this_lineno="${caller_info[0]}"
    local this_funcname="${caller_info[1]}"
    local this_filename="${caller_info[2]}"

    # This happens when called from global scope.
    if [[ "${this_funcname}" == "main" ]]; then
      this_funcname="<main>"
    fi
  fi

  local pretty_level="${color}$(echo "${level}" | tr '[:lower:]' '[:upper:]')${COLOR_RESET}"
  local scriptname="$(basename "${this_filename:-"${MY_SHELL}"}")"
  local date_string="$(date +"%Y-%m-%d %H:%M:%S")"
  if [[ -n "${this_funcname}" ]]; then
    local log_msg="$(printf "%s | PID:%s | %s | %s:%d | %s | %s" \
      "${date_string}" \
      "$$" \
      "${scriptname}" \
      "${this_funcname}" \
      "${this_lineno}" \
      "${pretty_level}" \
      "${message}")"
  else
    local log_msg="$(printf "%s | %s | %s | %s" \
      "${date_string}" \
      "${scriptname}" \
      "${pretty_level}" \
      "${message}")"
  fi

  echo -e "${log_msg}" |
    # Print to STDERR...
    tee /dev/stderr |
    # Get rid of first two log message sections...
    perl -nE 'print s/^[^|]+\|[ ]*[^|]+\|[ ]*(.*)/\1/gr' |
    # And then log to syslog...
    logger -t "${scriptname}"
}

#################################################################################
# Printf function that uses pythonic format specifiers.
#
# Usage
# -----
# pyprintf MESSAGE [FMT_ARGS [...]]
#
# Positional Arguments
# --------------------
# MESSAGE
#     The message to print to stdout [accepts pythonic .format() method styled
#     format arguments].
#
# FMT_ARGS
#     Format arguments.
#
# Examples
# --------
# pyprintf "{0} {1} {0}" "foo" "bar"  =>  "foo bar foo"
#################################################################################
function pyprintf() {
  local pycmd="import sys; args = ['\\n'.join(a.split(r'\\n')) for a in sys.argv[1:]]; print(args[0].format(*args[1:]), end='')"
  python3 -c "${pycmd}" "$@"
}

#################################################################################
# Encodes a URL string.
#
# Usage
# -----
# urlencode STRING [EXCLUDED_CHARS]
#
# Positional Arguments
# --------------------
# STRING
#     The string to encode.
#
# EXCLUDED_CHARS
#     A string containing characters that should not be encoded.
#
# Examples
# --------
# urlencode "foo bar"  =>  "foo%20bar"
# urlencode "/path/to/foo bar" "/"  =>  "/path/to/foo%20bar"
#################################################################################
function urlencode() {
  local string="$1"
  shift

  local excluded_chars="$1"
  shift

  local pycmd="from urllib.parse import quote; import sys; print(quote(sys.argv[1], sys.argv[2]))"
  python3 -c "${pycmd}" "${string}" "${excluded_chars}"
}

#################################################################################
# Prints the usage information for the script to the standard output.
#
# The usage format is determined by the USAGE_GRAMMAR array and the SCRIPTNAME
# variable. Each entry in USAGE_GRAMMAR represents a different usage pattern
# that will be printed.
#################################################################################
function usage() {
  printf "usage: "

  local hspace=false
  for P in "${USAGE_GRAMMAR[@]}"; do
    if [[ "${hspace}" = true ]]; then
      printf "       "
    else
      hspace=true
    fi

    printf "${SCRIPTNAME} %s\n" "${P}"
  done
}
