#!/bin/bash

#################################################################################
# Regression tests for Codex hook configuration.                                #
#################################################################################

CODEX_CONFIG="${PWD}/home/dot_codex/config.toml"
CODEX_HOOKS="${PWD}/home/dot_codex/hooks.json"

function features_table() {
  awk '
    /^\[features\]$/ { in_features = 1; next }
    /^\[/ && in_features { exit }
    in_features { print }
  ' "${CODEX_CONFIG}"
}

function test_codex_hooks_feature_is_enabled() {
  local features
  features="$(features_table)"

  assert_contains "[features]" "$(cat "${CODEX_CONFIG}")"
  assert_contains "hooks = true" "${features}"
  assert_same "" "$(printf "%s\n" "${features}" | grep -E '^codex_hooks[[:space:]]*=' || true)"
}

function test_codex_stop_hooks_include_sase_commands() {
  local hooks_json
  hooks_json="$(cat "${CODEX_HOOKS}")"

  assert_contains "sase_commit_stop_hook" "${hooks_json}"
  assert_contains "sase_sibling_commit_stop_hook" "${hooks_json}"
}
