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

function test_clipboard_uses_native_tmux_osc52_bindings() {
  local contents
  contents="$(tmux_conf_contents)"

  assert_contains 'set -s set-clipboard on' "${contents}"
  assert_contains "set -as terminal-features ',tmux-256color:clipboard'" "${contents}"
  assert_contains "set -as terminal-features ',screen*:clipboard'" "${contents}"
  assert_contains 'bind -T copy-mode-vi '"'"'y'"'"' send-keys -X copy-selection' "${contents}"
  assert_contains 'bind -T copy-mode-vi '"'"'Y'"'"' send-keys -X copy-selection' "${contents}"
  assert_contains 'bind y run "tmux capture-pane -p | tmux load-buffer -w -"' "${contents}"
}

function test_clipboard_bindings_do_not_use_x11_or_legacy_helpers() {
  local contents line
  contents="$(tmux_conf_contents)"

  assert_not_contains 'tm-copy' "${contents}"
  assert_not_contains 'xclip' "${contents}"
  assert_not_contains 'xsel' "${contents}"
  assert_not_contains 'yank >' "${contents}"

  while IFS= read -r line; do
    case "${line}" in
    bind\ * | bind-key\ *)
      assert_not_contains '| xc' "${line}"
      assert_not_contains ' xc' "${line}"
      ;;
    esac
  done <<<"${contents}"
}
