#!/bin/bash

#################################################################################
# Regression tests for chezmoi-managed SASE shell completions.                  #
#################################################################################

REPO_ROOT="${PWD}"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  TEST_HOME="${TEST_TMP}/home"
  SOURCE_ROOT="${TEST_TMP}/source"
  HOOK_TEMPLATE="${SOURCE_ROOT}/.chezmoiscripts/run_onchange_after_zcompile_sase_completion.tmpl"

  mkdir -p \
    "${TEST_HOME}" \
    "${SOURCE_ROOT}/.chezmoiscripts" \
    "${SOURCE_ROOT}/dot_config/fish/completions" \
    "${SOURCE_ROOT}/dot_local/share/bash-completion/completions" \
    "${SOURCE_ROOT}/dot_sase/completion/stamp" \
    "${SOURCE_ROOT}/dot_zfunc"

  cp "${REPO_ROOT}/home/dot_config/fish/completions/sase.fish" \
    "${SOURCE_ROOT}/dot_config/fish/completions/sase.fish"
  cp "${REPO_ROOT}/home/dot_local/share/bash-completion/completions/sase" \
    "${SOURCE_ROOT}/dot_local/share/bash-completion/completions/sase"
  cp "${REPO_ROOT}/home/dot_sase/completion/stamp/"*.json \
    "${SOURCE_ROOT}/dot_sase/completion/stamp/"
  cp "${REPO_ROOT}/home/dot_zfunc/_sase" \
    "${SOURCE_ROOT}/dot_zfunc/_sase"
  cp "${REPO_ROOT}/home/.chezmoiscripts/run_onchange_after_zcompile_sase_completion.tmpl" \
    "${HOOK_TEMPLATE}"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function require_chezmoi() {
  if ! command -v chezmoi >/dev/null 2>&1; then
    bashunit::skip "chezmoi is required for completion source rendering"
    return 1
  fi
}

function require_zsh() {
  if ! command -v zsh >/dev/null 2>&1; then
    bashunit::skip "zsh is required for zcompile verification"
    return 1
  fi
}

function apply_completion_fixture() {
  chezmoi --source "${SOURCE_ROOT}" --destination "${TEST_HOME}" \
    apply --include files,dirs --force
}

function render_hook() {
  chezmoi --source "${SOURCE_ROOT}" --destination "${TEST_HOME}" \
    execute-template <"${HOOK_TEMPLATE}" >"${TEST_TMP}/zcompile-hook.sh"
}

function test_apply_writes_completion_targets_and_metadata() {
  require_chezmoi || return 0

  apply_completion_fixture

  assert_file_exists "${TEST_HOME}/.zfunc/_sase"
  assert_file_exists "${TEST_HOME}/.local/share/bash-completion/completions/sase"
  assert_file_exists "${TEST_HOME}/.config/fish/completions/sase.fish"
  assert_file_exists "${TEST_HOME}/.sase/completion/stamp/bash.json"
  assert_file_exists "${TEST_HOME}/.sase/completion/stamp/fish.json"
  assert_file_exists "${TEST_HOME}/.sase/completion/stamp/zsh.json"
  assert_contains '"owner": "chezmoi"' \
    "$(cat "${TEST_HOME}/.sase/completion/stamp/zsh.json")"
  assert_contains '"shell": "zsh"' \
    "$(cat "${TEST_HOME}/.sase/completion/stamp/zsh.json")"
}

function test_apply_is_repeatable() {
  require_chezmoi || return 0

  apply_completion_fixture
  first_hash="$(sha256sum "${TEST_HOME}/.zfunc/_sase")"

  apply_completion_fixture
  second_hash="$(sha256sum "${TEST_HOME}/.zfunc/_sase")"

  assert_same "${first_hash}" "${second_hash}"
}

function test_hook_zcompiles_only_when_needed() {
  require_chezmoi || return 0
  require_zsh || return 0

  apply_completion_fixture
  render_hook

  first_output="$(HOME="${TEST_HOME}" bash "${TEST_TMP}/zcompile-hook.sh")"
  first_mtime="$(stat -c %Y "${TEST_HOME}/.zfunc/_sase.zwc")"
  second_output="$(HOME="${TEST_HOME}" bash "${TEST_TMP}/zcompile-hook.sh")"
  second_mtime="$(stat -c %Y "${TEST_HOME}/.zfunc/_sase.zwc")"

  sleep 1
  touch "${TEST_HOME}/.zfunc/_sase"
  third_output="$(HOME="${TEST_HOME}" bash "${TEST_TMP}/zcompile-hook.sh")"
  third_mtime="$(stat -c %Y "${TEST_HOME}/.zfunc/_sase.zwc")"

  assert_file_exists "${TEST_HOME}/.zfunc/_sase.zwc"
  assert_contains "bytecode refreshed" "${first_output}"
  assert_contains "bytecode is current" "${second_output}"
  assert_contains "bytecode refreshed" "${third_output}"
  assert_same "${first_mtime}" "${second_mtime}"
  assert_same "newer" "$(
    if [[ "${third_mtime}" -gt "${second_mtime}" ]]; then
      printf 'newer'
    else
      printf 'stale'
    fi
  )"
}

function test_zfunc_precedes_oh_my_zsh_compinit() {
  fpath_line="$(
    grep -n -F 'fpath=("${HOME}/.zfunc" $fpath)' \
      "${REPO_ROOT}/home/dot_zshrc" | cut -d: -f1
  )"
  oh_my_zsh_line="$(
    grep -n -F 'source $ZSH/oh-my-zsh.sh' \
      "${REPO_ROOT}/home/dot_zshrc" | cut -d: -f1
  )"
  explicit_compinit_line="$(
    grep -n -F 'autoload -U +X compinit && compinit -u' \
      "${REPO_ROOT}/home/dot_zshrc" | cut -d: -f1
  )"

  assert_same "" "$(grep -F 'fpath+=~/.zfunc' "${REPO_ROOT}/home/dot_zshrc" || true)"
  assert_same "before" "$(
    if [[ "${fpath_line}" -lt "${oh_my_zsh_line}" ]]; then
      printf 'before'
    else
      printf 'after'
    fi
  )"
  assert_same "before" "$(
    if [[ "${fpath_line}" -lt "${explicit_compinit_line}" ]]; then
      printf 'before'
    else
      printf 'after'
    fi
  )"
}
