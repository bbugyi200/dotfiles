#!/bin/bash

#################################################################################
# Static regression tests for portable shared tmux configuration.               #
#################################################################################

TMUX_CONF="${PWD}/home/dot_config/tmux/tmux.conf"

function tmux_conf_contents() {
  cat "${TMUX_CONF}"
}

function test_extended_keys_format_is_quiet_on_older_tmux() {
  local contents
  contents="$(tmux_conf_contents)"

  assert_contains 'set -sq extended-keys-format csi-u' "${contents}"
  assert_not_contains 'set -s extended-keys-format' "${contents}"
}
