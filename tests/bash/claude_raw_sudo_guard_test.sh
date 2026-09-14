#!/bin/bash

#################################################################################
# Regression tests for the Claude raw sudo PreToolUse guard.                    #
#################################################################################

GUARD="${PWD}/home/dot_claude/hooks/executable_sase_raw_sudo_guard"
SETTINGS="${PWD}/home/dot_claude/settings.json"

function payload_for() {
  python3 -c '
import json
import sys

print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))
' "$1"
}

function run_guard_for_agent() {
  payload_for "$1" | SASE_AGENT="sase-test.1" bash "${GUARD}"
}

function run_guard_without_agent() {
  payload_for "$1" | SASE_AGENT="" bash "${GUARD}"
}

function test_denies_plain_sudo() {
  local output
  output="$(run_guard_for_agent "sudo apt-get update")"

  assert_contains '"permissionDecision":"deny"' "${output}"
  assert_contains "/sase_sudo" "${output}"
  assert_contains "sase sudo request" "${output}"
}

function test_denies_sudo_after_pipeline_and_assignment() {
  local output
  output="$(run_guard_for_agent "printf hi | FOO=bar /usr/bin/sudo tee /etc/motd")"

  assert_contains '"permissionDecision":"deny"' "${output}"
}

function test_denies_sudo_after_newline_separator() {
  local output
  output="$(run_guard_for_agent $'printf hi\nsudo true')"

  assert_contains '"permissionDecision":"deny"' "${output}"
}

function test_denies_doas_and_pkexec() {
  assert_contains '"permissionDecision":"deny"' "$(run_guard_for_agent "doas id")"
  assert_contains '"permissionDecision":"deny"' "$(run_guard_for_agent "pkexec id")"
}

function test_denies_env_and_exec_wrappers() {
  assert_contains '"permissionDecision":"deny"' \
    "$(run_guard_for_agent "env -i FOO=bar sudo true")"
  assert_contains '"permissionDecision":"deny"' \
    "$(run_guard_for_agent "exec sudo true")"
}

function test_allows_sase_sudo_front_door() {
  local output
  output="$(run_guard_for_agent "printf '{}' | sase sudo request")"

  assert_same "" "${output}"
}

function test_allows_plain_text_mentions_and_command_lookup() {
  assert_same "" "$(run_guard_for_agent "printf '%s\n' 'sudo apt-get update'")"
  assert_same "" "$(run_guard_for_agent "command -v sudo")"
}

function test_allows_when_not_running_as_sase_agent() {
  local output
  output="$(run_guard_without_agent "sudo apt-get update")"

  assert_same "" "${output}"
}

function test_claude_settings_registers_bash_guard() {
  local command matcher timeout
  command="$(python3 -c '
import json
import sys

settings = json.load(open(sys.argv[1], encoding="utf-8"))
entries = settings["hooks"]["PreToolUse"]
bash = [entry for entry in entries if entry.get("matcher") == "Bash"]
print(bash[0]["hooks"][0]["command"])
' "${SETTINGS}")"
  matcher="$(python3 -c '
import json
import sys

settings = json.load(open(sys.argv[1], encoding="utf-8"))
entries = settings["hooks"]["PreToolUse"]
bash = [entry for entry in entries if entry.get("matcher") == "Bash"]
print(bash[0]["matcher"])
' "${SETTINGS}")"
  timeout="$(python3 -c '
import json
import sys

settings = json.load(open(sys.argv[1], encoding="utf-8"))
entries = settings["hooks"]["PreToolUse"]
bash = [entry for entry in entries if entry.get("matcher") == "Bash"]
print(bash[0]["hooks"][0]["timeout"])
' "${SETTINGS}")"

  assert_same "Bash" "${matcher}"
  assert_same '"$HOME"/.claude/hooks/sase_raw_sudo_guard' "${command}"
  assert_same "5" "${timeout}"
}
