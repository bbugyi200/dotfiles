#!/bin/bash

#################################################################################
# Static regression tests for portable shared zsh startup paths.                #
#################################################################################

ZSHRC="${PWD}/home/dot_zshrc"

function zshrc_contents() {
  cat "${ZSHRC}"
}

function test_shared_zshrc_has_no_linux_home_references() {
  assert_not_contains "/home/bryan" "$(zshrc_contents)"
}

function test_pyenv_bin_path_is_home_relative_and_directory_guarded() {
  local contents
  contents="$(zshrc_contents)"

  assert_contains 'if [[ -d "${HOME}/.pyenv/bin" ]]; then' "${contents}"
  assert_contains 'export PATH="$(insert_path "${PATH}" "${HOME}/.pyenv/bin")"' "${contents}"
  assert_not_contains 'export PATH="/home/bryan/.pyenv/bin:$PATH"' "${contents}"
}

function test_broot_launcher_is_xdg_relative_and_optional() {
  local contents
  contents="$(zshrc_contents)"

  assert_contains "if cmd_exists broot; then" "${contents}"
  assert_contains 'source_if_exists "${XDG_CONFIG_HOME:-${HOME}/.config}/broot/launcher/bash/br"' "${contents}"
  assert_not_contains "source /home/bryan/.config/broot/launcher/bash/br" "${contents}"
}
