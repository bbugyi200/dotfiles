#!/bin/bash

#################################################################################
# Tests for poseidon-cache-watch. Filesystem samples and notify stubs keep the  #
# real disk, SMART collector, and SASE inbox untouched.                         #
#################################################################################

WATCH="${PWD}/home/bin/executable_poseidon-cache-watch"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  STATE_DIR="${TEST_TMP}/state"
  NOTIFY_LOG="${TEST_TMP}/notify.log"
  mkdir -p "${TEST_TMP}/poseidon/cargo-target" "${TEST_TMP}/poseidon/sccache" \
    "${STATE_DIR}" "${TEST_TMP}/bin"
  chmod 0755 "${TEST_TMP}/poseidon/cargo-target"
  cat >"${TEST_TMP}/sccache.conf" <<'EOF'
[cache.disk]
dir = "DIR_PLACEHOLDER"
size = 42949672960
EOF
  sed -i "s|DIR_PLACEHOLDER|${TEST_TMP}/poseidon/sccache|" "${TEST_TMP}/sccache.conf"
  cat >"${TEST_TMP}/bin/notify" <<EOF
#!/bin/bash
cat >>"${NOTIFY_LOG}"
printf '\nKEY=%s\n' "\${POSEIDON_NOTIFY_KEY}" >>"${NOTIFY_LOG}"
exit "\${POSEIDON_NOTIFY_EXIT:-0}"
EOF
  chmod +x "${TEST_TMP}/bin/notify" "${WATCH}"
  chmod 0555 "${TEST_TMP}/poseidon/cargo-target"
  now="$(date +%s)"
  cat >"${TEST_TMP}/smart.prom" <<EOF
smartmon_reallocated_sector_ct_raw_value{disk="/dev/sdc",type="sat"} 41
smartmon_runtime_bad_block_raw_value{disk="/dev/sdc",type="sat"} 41
smartmon_device_smart_healthy{disk="/dev/sdc",type="sat"} 1
smartmon_smartctl_run{disk="/dev/sdc",type="sat"} ${now}
EOF
}

function tear_down() {
  chmod -R u+w "${TEST_TMP}" 2>/dev/null || true
  rm -rf "${TEST_TMP}"
}

function run_watch() {
  PATH="${TEST_TMP}/bin:${PATH}" \
    POSEIDON_WATCH_STATE_DIR="${STATE_DIR}" \
    POSEIDON_NOTIFY_CMD="${TEST_TMP}/bin/notify" \
    POSEIDON_MOUNT="${TEST_TMP}/poseidon" \
    POSEIDON_OLD_TARGET="${TEST_TMP}/poseidon/cargo-target" \
    POSEIDON_SCCACHE_DIR="${TEST_TMP}/poseidon/sccache" \
    POSEIDON_SCCACHE_CONF="${TEST_TMP}/sccache.conf" \
    POSEIDON_SCCACHE_SOCK="${TEST_TMP}/poseidon/sccache/sccache.sock" \
    POSEIDON_SMART_PROM="${TEST_TMP}/smart.prom" \
    POSEIDON_SMART_DISK="/dev/sdc" \
    POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_ROOT_AVAIL="${POSEIDON_FAKE_ROOT_AVAIL:-200000000000}" \
    bash "${WATCH}" "$@"
}

function notify_log() {
  if [[ -f "${NOTIFY_LOG}" ]]; then
    cat "${NOTIFY_LOG}"
  fi
}

function test_healthy_poseidon_is_quiet() {
  chmod 0555 "${TEST_TMP}/poseidon/cargo-target"
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 run_watch
  assert_same "0" "$?"
  if [[ -f "${NOTIFY_LOG}" ]]; then
    assert_empty "$(cat "${NOTIFY_LOG}")"
  fi
}

function test_warns_at_75_percent_once() {
  chmod 0555 "${TEST_TMP}/poseidon/cargo-target"
  POSEIDON_FAKE_AVAIL=60000000000 POSEIDON_FAKE_USED_PCT=75 run_watch
  assert_contains "75%" "$(cat "${NOTIFY_LOG}")"
  : >"${NOTIFY_LOG}"
  POSEIDON_FAKE_AVAIL=60000000000 POSEIDON_FAKE_USED_PCT=75 run_watch
  if [[ -s "${NOTIFY_LOG}" ]]; then
    assert_not_contains "75%" "$(cat "${NOTIFY_LOG}")"
  fi
}

function test_retries_notification_when_delivery_fails() {
  chmod 0555 "${TEST_TMP}/poseidon/cargo-target"
  POSEIDON_NOTIFY_EXIT=1 \
    POSEIDON_FAKE_AVAIL=60000000000 POSEIDON_FAKE_USED_PCT=75 run_watch || true
  : >"${NOTIFY_LOG}"
  POSEIDON_NOTIFY_EXIT=0 \
    POSEIDON_FAKE_AVAIL=60000000000 POSEIDON_FAKE_USED_PCT=75 run_watch
  assert_contains "75%" "$(cat "${NOTIFY_LOG}")"
}

function test_bypass_at_80_percent() {
  chmod 0555 "${TEST_TMP}/poseidon/cargo-target"
  POSEIDON_FAKE_AVAIL=50000000000 POSEIDON_FAKE_USED_PCT=80 run_watch
  assert_contains "bypass sccache" "$(cat "${NOTIFY_LOG}")"
}

function test_recovery_requires_hysteresis() {
  chmod 0555 "${TEST_TMP}/poseidon/cargo-target"
  POSEIDON_FAKE_AVAIL=60000000000 POSEIDON_FAKE_USED_PCT=75 run_watch
  : >"${NOTIFY_LOG}"
  POSEIDON_FAKE_AVAIL=60000000000 POSEIDON_FAKE_USED_PCT=72 run_watch
  if [[ -s "${NOTIFY_LOG}" ]]; then
    assert_not_contains "recovered" "$(cat "${NOTIFY_LOG}")"
  fi
  POSEIDON_FAKE_AVAIL=60000000000 POSEIDON_FAKE_USED_PCT=60 run_watch
  assert_contains "recovered" "$(cat "${NOTIFY_LOG}")"
}

function test_setup_notification_is_marked() {
  chmod 0555 "${TEST_TMP}/poseidon/cargo-target"
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 run_watch --setup
  assert_contains "SETUP:" "$(cat "${NOTIFY_LOG}")"
}

function test_old_target_writable_is_reported() {
  chmod 0755 "${TEST_TMP}/poseidon/cargo-target"
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 run_watch
  assert_contains "writable" "$(cat "${NOTIFY_LOG}")"
}

function test_scratch_soft_target_does_not_notify() {
  chmod 0555 "${TEST_TMP}/poseidon/cargo-target"
  cat >"${STATE_DIR}/state" <<'EOF'
delivered_scratch=stale
level_scratch=stale
scratch_last_bytes=20000000000
scratch_over_ticks=2
last_hourly_du=1
EOF
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 \
    POSEIDON_FAKE_SCRATCH_BYTES=20000000000 run_watch
  assert_not_contains "soft target" "$(notify_log)"
  assert_not_contains "KEY=scratch" "$(notify_log)"
  assert_not_contains "reaper progress" "$(notify_log)"
  : >"${NOTIFY_LOG}"
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 \
    POSEIDON_FAKE_SCRATCH_BYTES=30000000000 run_watch
  assert_not_contains "soft target" "$(notify_log)"
  assert_not_contains "KEY=scratch" "$(notify_log)"
  assert_not_contains "recovered" "$(notify_log)"
  : >"${NOTIFY_LOG}"
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 \
    POSEIDON_FAKE_SCRATCH_BYTES=25000000000 run_watch
  assert_not_contains "soft target" "$(notify_log)"
  assert_not_contains "KEY=scratch" "$(notify_log)"
  assert_not_contains "recovered" "$(notify_log)"
  assert_contains "delivered_scratch=stale" "$(cat "${STATE_DIR}/state")"
  assert_contains "level_scratch=stale" "$(cat "${STATE_DIR}/state")"
}

function test_root_low_space_alerts_once() {
  chmod 0555 "${TEST_TMP}/poseidon/cargo-target"
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 \
    POSEIDON_FAKE_ROOT_AVAIL=30000000000 run_watch
  assert_contains "below the 32 GiB floor" "$(notify_log)"
  : >"${NOTIFY_LOG}"
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 \
    POSEIDON_FAKE_ROOT_AVAIL=30000000000 run_watch
  if [[ -s "${NOTIFY_LOG}" ]]; then
    assert_not_contains "32 GiB floor" "$(notify_log)"
  fi
}

function test_root_hysteresis_does_not_recover_early() {
  chmod 0555 "${TEST_TMP}/poseidon/cargo-target"
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 \
    POSEIDON_FAKE_ROOT_AVAIL=30000000000 run_watch
  assert_contains "below the 32 GiB floor" "$(notify_log)"
  : >"${NOTIFY_LOG}"
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 \
    POSEIDON_FAKE_ROOT_AVAIL=40000000000 run_watch
  assert_not_contains "recovered" "$(notify_log)"
}

function test_root_recovers_only_after_alert() {
  chmod 0555 "${TEST_TMP}/poseidon/cargo-target"
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 \
    POSEIDON_FAKE_ROOT_AVAIL=60000000000 run_watch
  if [[ -f "${NOTIFY_LOG}" ]]; then
    assert_not_contains "recovered" "$(notify_log)"
  fi
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 \
    POSEIDON_FAKE_ROOT_AVAIL=30000000000 run_watch
  assert_contains "below the 32 GiB floor" "$(notify_log)"
  : >"${NOTIFY_LOG}"
  POSEIDON_FAKE_AVAIL=200000000000 POSEIDON_FAKE_USED_PCT=1 \
    POSEIDON_FAKE_ROOT_AVAIL=60000000000 run_watch
  assert_contains "recovered above 48 GiB" "$(notify_log)"
}
