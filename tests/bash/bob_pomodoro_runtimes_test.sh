#!/bin/bash

#################################################################################
# Regression tests for Bob Pomodoro runtime annotations.                        #
#################################################################################

SCRIPT="${PWD}/home/bin/executable_bob_pomodoro_runtimes"

function write_fake_ob() {
  local fake_bin="$1"

  mkdir -p "${fake_bin}"
  cat >"${fake_bin}/ob" <<'EOF'
#!/bin/bash
set -euo pipefail

if [[ "$#" -ne 3 || "$1" != "sync" || "$2" != "--path" ]]; then
  printf 'unexpected ob invocation: %s\n' "$*" >&2
  exit 64
fi

if [[ -n "${OB_CALLS_FILE:-}" ]]; then
  printf '%s\n' "$*" >>"${OB_CALLS_FILE}"
fi

if [[ -n "${OB_SYNC_REPLACE_NOTE:-}" ]]; then
  cat "${OB_SYNC_REPLACE_WITH}" >"${OB_SYNC_REPLACE_NOTE}"
fi

if [[ -n "${OB_SYNC_OUTPUT:-}" ]]; then
  printf '%s\n' "${OB_SYNC_OUTPUT}" >&2
fi

exit "${OB_SYNC_STATUS:-0}"
EOF
  chmod +x "${fake_bin}/ob"
}

function run_script_with_fake_ob() {
  local fake_bin="$1"
  shift

  PATH="${fake_bin}:${PATH}" "${SCRIPT}" "$@"
}

function make_note() {
  local path="$1"
  shift

  mkdir -p "$(dirname "${path}")"
  printf "%s\n" "$@" >"${path}"
}

function test_runtime_annotations_are_idempotent() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  local fake_bin="${temp_dir}/bin"
  local note="${temp_dir}/2026/20260531_day.md"
  write_fake_ob "${fake_bin}"

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

  run_script_with_fake_ob "${fake_bin}" "${note}"

  local updated
  updated="$(cat "${note}")"
  assert_contains "## Pomodoros [runtime:: 2h10m]" "${updated}"
  assert_contains "- [x] (0800-0825) #task first [completion:: 2026-05-31] [runtime:: 25m]" "${updated}"
  assert_contains "- [X] (08:30-09:45) #task second [p:: 5] [runtime:: 1h15m]" "${updated}"
  assert_contains "  - [x] (2345-0015) #task midnight [[20260531_day]] [runtime:: 30m]" "${updated}"
  assert_contains "- [ ] (1000-1025) #task open" "${updated}"
  assert_contains "- [x] (1200-1300) #task outside" "${updated}"

  run_script_with_fake_ob "${fake_bin}" --check "${note}" >/dev/null 2>&1
  assert_same 0 "$?"

  rm -rf "${temp_dir}"
}

function test_default_note_uses_bob_dir_and_date_override() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  local fake_bin="${temp_dir}/bin"
  local note="${temp_dir}/2026/20260531_day.md"
  write_fake_ob "${fake_bin}"

  make_note \
    "${note}" \
    "# Test" \
    "" \
    "## Pomodoros" \
    "" \
    "- [x] (10:00-10:00) #task zero" \
    "- [x] #task untimed [runtime:: stale]"

  BOB_DIR="${temp_dir}" BOB_NOW="2026-05-31 12:00" \
    run_script_with_fake_ob "${fake_bin}" >/dev/null

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
  local fake_bin="${temp_dir}/bin"
  local note="${temp_dir}/note.md"
  write_fake_ob "${fake_bin}"

  make_note \
    "${note}" \
    "# Test" \
    "" \
    "## Pomodoros [runtime:: stale]" \
    "" \
    "- [ ] (0800-0825) #task open" \
    "- [x] #task untimed [runtime:: stale]"

  run_script_with_fake_ob "${fake_bin}" "${note}" >/dev/null

  local updated
  updated="$(cat "${note}")"
  assert_contains "## Pomodoros [runtime:: 0m]" "${updated}"
  assert_contains "- [ ] (0800-0825) #task open" "${updated}"
  assert_contains "- [x] #task untimed" "${updated}"
  assert_same "" "$(printf "%s\n" "${updated}" | grep 'untimed .*runtime::' || true)"

  rm -rf "${temp_dir}"
}

function test_sync_runs_before_runtime_calculation() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  local fake_bin="${temp_dir}/bin"
  local note="${temp_dir}/2026/20260531_day.md"
  local synced_note="${temp_dir}/synced_note.md"
  local calls_file="${temp_dir}/ob.calls"
  write_fake_ob "${fake_bin}"

  make_note \
    "${note}" \
    "# Test" \
    "" \
    "## Pomodoros" \
    "" \
    "- [x] (0800-0825) #task stale-before-sync"

  make_note \
    "${synced_note}" \
    "# Test" \
    "" \
    "## Pomodoros" \
    "" \
    "- [x] (0900-0925) #task synced-one" \
    "- [x] (10:00-10:50) #task synced-two"

  BOB_DIR="${temp_dir}" OB_CALLS_FILE="${calls_file}" \
    OB_SYNC_REPLACE_NOTE="${note}" OB_SYNC_REPLACE_WITH="${synced_note}" \
    run_script_with_fake_ob "${fake_bin}" "${note}" >/dev/null

  assert_same "sync --path ${temp_dir}" "$(cat "${calls_file}")"

  local updated
  updated="$(cat "${note}")"
  assert_contains "## Pomodoros [runtime:: 1h15m]" "${updated}"
  assert_contains "- [x] (0900-0925) #task synced-one [runtime:: 25m]" "${updated}"
  assert_contains "- [x] (10:00-10:50) #task synced-two [runtime:: 50m]" "${updated}"

  rm -rf "${temp_dir}"
}

function test_failing_sync_aborts_and_leaves_note_unchanged() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  local fake_bin="${temp_dir}/bin"
  local note="${temp_dir}/note.md"
  write_fake_ob "${fake_bin}"

  make_note \
    "${note}" \
    "# Test" \
    "" \
    "## Pomodoros" \
    "" \
    "- [x] (0800-0825) #task should-not-change"

  local original
  original="$(cat "${note}")"

  local output
  local status
  if output="$(OB_SYNC_STATUS=3 OB_SYNC_OUTPUT="sync exploded" \
    run_script_with_fake_ob "${fake_bin}" "${note}" 2>&1)"; then
    status=0
  else
    status=$?
  fi

  assert_same 2 "${status}"
  assert_contains "sync exploded" "${output}"
  assert_contains "bob_pomodoro_runtimes: ob sync failed with exit code 3" "${output}"
  assert_same "${original}" "$(cat "${note}")"

  rm -rf "${temp_dir}"
}

function test_already_running_sync_message_allows_runtime_calculation() {
  local temp_dir
  temp_dir="$(mktemp -d)"
  local fake_bin="${temp_dir}/bin"
  local note="${temp_dir}/note.md"
  write_fake_ob "${fake_bin}"

  make_note \
    "${note}" \
    "# Test" \
    "" \
    "## Pomodoros" \
    "" \
    "- [x] (0800-0825) #task allowed"

  OB_SYNC_STATUS=1 \
    OB_SYNC_OUTPUT="Another sync instance is already running for this vault." \
    run_script_with_fake_ob "${fake_bin}" "${note}" >/dev/null
  assert_same 0 "$?"

  local updated
  updated="$(cat "${note}")"
  assert_contains "## Pomodoros [runtime:: 25m]" "${updated}"
  assert_contains "- [x] (0800-0825) #task allowed [runtime:: 25m]" "${updated}"

  rm -rf "${temp_dir}"
}
