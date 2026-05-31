#!/bin/bash

#################################################################################
# Regression tests for Bob Pomodoro runtime annotations.                        #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_bob_pomodoro_runtimes"

function make_note() {
  local path="$1"
  shift

  mkdir -p "$(dirname "${path}")"
  printf "%s\n" "$@" >"${path}"
}

function test_runtime_annotations_are_idempotent() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  local note="${temp_dir}/2026/20260531_day.md"

  make_note \
    "${note}" \
    "# Test" \
    "" \
    "## Pomodoros [runtime:: stale]" \
    "" \
    "- [x] (0800-0825) #task first [completion:: 2026-05-31] [runtime:: old]" \
    "- [X] (08:30-09:45) #task second [p:: 5]" \
    "- [ ] (1000-1025) #task open" \
    "- [-] (1100-1125) #task cancelled" \
    "  - [x] (2345-0015) #task midnight [[20260531_day]] [runtime:: bad]" \
    "" \
    "## Later" \
    "- [x] (1200-1300) #task outside"

  "${SCRIPT}" "${note}"

  local updated
  updated="$(cat "${note}")"
  assert_contains "## Pomodoros [runtime:: 2h10m]" "${updated}"
  assert_contains "- [x] (0800-0825) #task first [completion:: 2026-05-31] [runtime:: 25m]" "${updated}"
  assert_contains "- [X] (08:30-09:45) #task second [p:: 5] [runtime:: 1h15m]" "${updated}"
  assert_contains "  - [x] (2345-0015) #task midnight [[20260531_day]] [runtime:: 30m]" "${updated}"
  assert_contains "- [ ] (1000-1025) #task open" "${updated}"
  assert_contains "- [x] (1200-1300) #task outside" "${updated}"

  "${SCRIPT}" --check "${note}" >/dev/null 2>&1
  assert_same 0 "$?"

  rm -rf "${temp_dir}"
}

function test_default_note_uses_bob_dir_and_date_override() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  local note="${temp_dir}/2026/20260531_day.md"

  make_note \
    "${note}" \
    "# Test" \
    "" \
    "## Pomodoros" \
    "" \
    "- [x] (10:00-10:00) #task zero" \
    "- [x] #task untimed [runtime:: stale]"

  BOB_DIR="${temp_dir}" BOB_NOW="2026-05-31 12:00" "${SCRIPT}" >/dev/null

  local updated
  updated="$(cat "${note}")"
  assert_contains "## Pomodoros [runtime:: 0m]" "${updated}"
  assert_contains "- [x] (10:00-10:00) #task zero [runtime:: 0m]" "${updated}"
  assert_contains "- [x] #task untimed" "${updated}"
  assert_same "" "$(printf "%s\n" "${updated}" | grep 'untimed .*runtime::' || true)"

  rm -rf "${temp_dir}"
}

function test_no_completed_timed_tasks_sets_zero_header_only() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  local note="${temp_dir}/note.md"

  make_note \
    "${note}" \
    "# Test" \
    "" \
    "## Pomodoros [runtime:: stale]" \
    "" \
    "- [ ] (0800-0825) #task open" \
    "- [x] #task untimed [runtime:: stale]"

  "${SCRIPT}" "${note}" >/dev/null

  local updated
  updated="$(cat "${note}")"
  assert_contains "## Pomodoros [runtime:: 0m]" "${updated}"
  assert_contains "- [ ] (0800-0825) #task open" "${updated}"
  assert_contains "- [x] #task untimed" "${updated}"
  assert_same "" "$(printf "%s\n" "${updated}" | grep 'untimed .*runtime::' || true)"

  rm -rf "${temp_dir}"
}
