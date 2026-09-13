#!/bin/bash

#################################################################################
# Tests for the Athena rustc wrapper. Fake compilers and sccache record argv    #
# and exit status; Poseidon health is injected through test-only env vars.      #
#################################################################################

WRAPPER="${PWD}/home/bin/executable_sase-rustc-wrapper"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  FAKE_BIN="${TEST_TMP}/bin"
  COMPILER_CALLS="${TEST_TMP}/compiler_calls.txt"
  SCCACHE_CALLS="${TEST_TMP}/sccache_calls.txt"
  mkdir -p "${FAKE_BIN}" "${TEST_TMP}/poseidon/sccache"
  chmod +x "${WRAPPER}"

  cat >"${FAKE_BIN}/rustc" <<EOF
#!/bin/bash
printf '%s\n' "\$@" >"${COMPILER_CALLS}"
echo "\$@" >>"${COMPILER_CALLS}.env"
exit "\${FAKE_COMPILER_EXIT:-0}"
EOF
  chmod +x "${FAKE_BIN}/rustc"

  cat >"${FAKE_BIN}/sccache" <<EOF
#!/bin/bash
printf '%s\n' "\$@" >"${SCCACHE_CALLS}"
env | awk -F= '/^SCCACHE_|^AWS_/ {print}' | sort >"${SCCACHE_CALLS}.env"
compiler="\$1"
shift
exec "\$compiler" "\$@"
EOF
  chmod +x "${FAKE_BIN}/sccache"
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

function run_wrapper() {
  WRAPPER_RC=0
  PATH="${FAKE_BIN}:${PATH}" \
    POSEIDON_MOUNT="${TEST_TMP}/poseidon" \
    POSEIDON_SCCACHE_DIR="${TEST_TMP}/poseidon/sccache" \
    POSEIDON_SCCACHE_CONF="${TEST_TMP}/sccache.conf" \
    POSEIDON_SCCACHE_SOCK="${TEST_TMP}/poseidon/sccache/sccache.sock" \
    bash "${WRAPPER}" "${FAKE_BIN}/rustc" --crate-name demo src/lib.rs || WRAPPER_RC=$?
}

function test_runs_real_compiler_when_mount_is_missing() {
  POSEIDON_FAKE_MOUNTED=0 run_wrapper
  assert_same "0" "${WRAPPER_RC}"
  assert_file_exists "${COMPILER_CALLS}"
  assert_file_not_exists "${SCCACHE_CALLS}"
  assert_contains "--crate-name" "$(cat "${COMPILER_CALLS}")"
}

function test_runs_real_compiler_when_uuid_mismatches() {
  POSEIDON_FAKE_MOUNTED=1 POSEIDON_FAKE_UUID=deadbeef run_wrapper
  assert_same "0" "${WRAPPER_RC}"
  assert_file_not_exists "${SCCACHE_CALLS}"
}

function test_runs_real_compiler_when_volume_is_a_symlink() {
  POSEIDON_FAKE_SYMLINK=1 POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb run_wrapper
  assert_same "0" "${WRAPPER_RC}"
  assert_file_not_exists "${SCCACHE_CALLS}"
}

function test_runs_real_compiler_at_80_percent() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=50000000000 \
    POSEIDON_FAKE_USED_PCT=80 \
    run_wrapper
  assert_same "0" "${WRAPPER_RC}"
  assert_file_not_exists "${SCCACHE_CALLS}"
}

function test_runs_real_compiler_below_32g_floor() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=30000000000 \
    POSEIDON_FAKE_USED_PCT=10 \
    run_wrapper
  assert_same "0" "${WRAPPER_RC}"
  assert_file_not_exists "${SCCACHE_CALLS}"
}

function test_uses_sccache_when_poseidon_is_healthy() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    run_wrapper
  assert_same "0" "${WRAPPER_RC}"
  assert_file_exists "${SCCACHE_CALLS}"
  assert_contains "--crate-name" "$(cat "${COMPILER_CALLS}")"
}

function test_propagates_compiler_failure() {
  FAKE_COMPILER_EXIT=3 \
    POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    run_wrapper
  assert_same "3" "${WRAPPER_RC}"
}

function test_normalizes_sccache_env_and_drops_remote_backend() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    SCCACHE_BUCKET=other SCCACHE_DIR=/tmp/wrong AWS_SECRET_ACCESS_KEY=secret \
    run_wrapper
  assert_file_exists "${SCCACHE_CALLS}.env"
  assert_contains "SCCACHE_DIR=${TEST_TMP}/poseidon/sccache" "$(cat "${SCCACHE_CALLS}.env")"
  assert_not_contains "SCCACHE_BUCKET=other" "$(cat "${SCCACHE_CALLS}.env")"
  assert_not_contains "AWS_SECRET_ACCESS_KEY" "$(cat "${SCCACHE_CALLS}.env")"
}

function test_falls_back_when_sccache_is_missing() {
  rm -f "${FAKE_BIN}/sccache"
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    run_wrapper
  assert_same "0" "${WRAPPER_RC}"
  assert_file_exists "${COMPILER_CALLS}"
  assert_file_not_exists "${SCCACHE_CALLS}"
}
