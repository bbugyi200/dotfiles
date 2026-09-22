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
  CLIPPY_CALLS="${TEST_TMP}/clippy_calls.txt"
  mkdir -p "${FAKE_BIN}" "${TEST_TMP}/poseidon/sccache"
  chmod +x "${WRAPPER}"
  ln -s /usr/bin/dirname "${FAKE_BIN}/dirname"
  ln -s /usr/bin/pwd "${FAKE_BIN}/pwd"

  cat >"${FAKE_BIN}/rustc" <<EOF
#!/bin/bash
printf '%s\n' "\$@" >"${COMPILER_CALLS}"
echo "\$@" >>"${COMPILER_CALLS}.env"
echo "CARGO_INCREMENTAL=\${CARGO_INCREMENTAL-unset}" >"${COMPILER_CALLS}.cenv"
exit "\${FAKE_COMPILER_EXIT:-0}"
EOF
  chmod +x "${FAKE_BIN}/rustc"

  cat >"${FAKE_BIN}/clippy-driver" <<EOF
#!/bin/bash
printf '%s\n' "\$@" >"${CLIPPY_CALLS}"
echo "\$@" >>"${CLIPPY_CALLS}.env"
if [[ "\$1" == */* && -x "\$1" ]]; then
  compiler="\$1"
  shift
  exec "\$compiler" "\$@"
fi
exit "\${FAKE_COMPILER_EXIT:-0}"
EOF
  chmod +x "${FAKE_BIN}/clippy-driver"

  cat >"${FAKE_BIN}/sccache" <<EOF
#!/bin/bash
printf '%s\n' "\$@" >"${SCCACHE_CALLS}"
env | awk -F= '/^SCCACHE_|^AWS_/ {print}' | sort >"${SCCACHE_CALLS}.env"
echo "CARGO_INCREMENTAL=\${CARGO_INCREMENTAL-unset}" >>"${SCCACHE_CALLS}.env"
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
  PATH="${WRAPPER_PATH:-${FAKE_BIN}:${PATH}}" \
    POSEIDON_MOUNT="${TEST_TMP}/poseidon" \
    POSEIDON_SCCACHE_DIR="${TEST_TMP}/poseidon/sccache" \
    POSEIDON_SCCACHE_CONF="${TEST_TMP}/sccache.conf" \
    POSEIDON_SCCACHE_SOCK="${TEST_TMP}/poseidon/sccache/sccache.sock" \
    /bin/bash "${WRAPPER}" "${WRAPPER_COMPILER:-${FAKE_BIN}/rustc}" --crate-name demo src/lib.rs "$@" || WRAPPER_RC=$?
}

function run_wrapper_clippy_chain() {
  WRAPPER_RC=0
  PATH="${WRAPPER_PATH:-${FAKE_BIN}:${PATH}}" \
    POSEIDON_MOUNT="${TEST_TMP}/poseidon" \
    POSEIDON_SCCACHE_DIR="${TEST_TMP}/poseidon/sccache" \
    POSEIDON_SCCACHE_CONF="${TEST_TMP}/sccache.conf" \
    POSEIDON_SCCACHE_SOCK="${TEST_TMP}/poseidon/sccache/sccache.sock" \
    /bin/bash "${WRAPPER}" "${FAKE_BIN}/clippy-driver" "${FAKE_BIN}/rustc" --crate-name demo src/lib.rs "$@" || WRAPPER_RC=$?
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
    WRAPPER_PATH="${FAKE_BIN}" \
    run_wrapper
  assert_same "0" "${WRAPPER_RC}"
  assert_file_exists "${COMPILER_CALLS}"
  assert_file_not_exists "${SCCACHE_CALLS}"
}

function test_metadata_incremental_runs_direct_skipping_sccache() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    run_wrapper --emit=metadata "-Cincremental=${TEST_TMP}/inc"
  assert_same "0" "${WRAPPER_RC}"
  assert_file_exists "${COMPILER_CALLS}"
  assert_file_not_exists "${SCCACHE_CALLS}"
  assert_contains "incremental" "$(cat "${COMPILER_CALLS}")"
  assert_contains "--emit=metadata" "$(cat "${COMPILER_CALLS}")"
}

function test_metadata_incremental_two_word_flag_runs_direct() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    run_wrapper --emit=metadata -C "incremental=${TEST_TMP}/inc"
  assert_same "0" "${WRAPPER_RC}"
  assert_file_exists "${COMPILER_CALLS}"
  assert_file_not_exists "${SCCACHE_CALLS}"
  assert_contains "incremental" "$(cat "${COMPILER_CALLS}")"
}

function test_codegen_incremental_strips_flag_before_sccache() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    run_wrapper --emit=link "-Cincremental=${TEST_TMP}/inc"
  assert_same "0" "${WRAPPER_RC}"
  assert_file_exists "${SCCACHE_CALLS}"
  assert_file_exists "${COMPILER_CALLS}"
  assert_not_contains "incremental" "$(cat "${SCCACHE_CALLS}")"
  assert_not_contains "incremental" "$(cat "${COMPILER_CALLS}")"
  assert_contains "--emit=link" "$(cat "${COMPILER_CALLS}")"
}

function test_codegen_incremental_two_word_flag_is_stripped() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    run_wrapper --emit=link -C "incremental=${TEST_TMP}/inc"
  assert_same "0" "${WRAPPER_RC}"
  assert_file_exists "${SCCACHE_CALLS}"
  assert_not_contains "incremental" "$(cat "${SCCACHE_CALLS}")"
  assert_not_contains "incremental" "$(cat "${COMPILER_CALLS}")"
}

function test_metadata_without_incremental_still_uses_sccache() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    run_wrapper --emit=metadata
  assert_same "0" "${WRAPPER_RC}"
  assert_file_exists "${SCCACHE_CALLS}"
  assert_contains "--emit=metadata" "$(cat "${COMPILER_CALLS}")"
}

function test_clippy_driver_metadata_incremental_runs_direct() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    WRAPPER_COMPILER="${FAKE_BIN}/clippy-driver" \
    run_wrapper --emit=metadata "-Cincremental=${TEST_TMP}/inc"
  assert_same "0" "${WRAPPER_RC}"
  assert_file_not_exists "${SCCACHE_CALLS}"
  assert_file_exists "${CLIPPY_CALLS}.env"
  assert_contains "incremental" "$(cat "${CLIPPY_CALLS}")"
}

function test_sccache_path_forces_cargo_incremental_off() {
  # Real sccache refuses even `rustc -vV` probes when CARGO_INCREMENTAL=1
  # is exported, so the cache leg must force it off.
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    CARGO_INCREMENTAL=1 \
    run_wrapper
  assert_same "0" "${WRAPPER_RC}"
  assert_file_exists "${SCCACHE_CALLS}"
  assert_contains "CARGO_INCREMENTAL=0" "$(cat "${SCCACHE_CALLS}.env")"
}

function test_codegen_incremental_env_is_off_before_sccache() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    CARGO_INCREMENTAL=1 \
    run_wrapper --emit=link "-Cincremental=${TEST_TMP}/inc"
  assert_same "0" "${WRAPPER_RC}"
  assert_file_exists "${SCCACHE_CALLS}"
  assert_not_contains "incremental" "$(cat "${SCCACHE_CALLS}")"
  assert_contains "CARGO_INCREMENTAL=0" "$(cat "${SCCACHE_CALLS}.env")"
}

function test_metadata_direct_preserves_cargo_incremental_env() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    CARGO_INCREMENTAL=1 \
    run_wrapper --emit=metadata "-Cincremental=${TEST_TMP}/inc"
  assert_same "0" "${WRAPPER_RC}"
  assert_file_not_exists "${SCCACHE_CALLS}"
  assert_contains "CARGO_INCREMENTAL=1" "$(cat "${COMPILER_CALLS}.cenv")"
}

function test_clippy_driver_chain_metadata_incremental_runs_direct() {
  POSEIDON_FAKE_MOUNTED=1 \
    POSEIDON_FAKE_UUID=e0d96fde-be60-4f3b-bed7-3e9700060fdb \
    POSEIDON_FAKE_AVAIL=200000000000 \
    POSEIDON_FAKE_USED_PCT=1 \
    run_wrapper_clippy_chain --emit=metadata "-Cincremental=${TEST_TMP}/inc"
  assert_same "0" "${WRAPPER_RC}"
  assert_file_not_exists "${SCCACHE_CALLS}"
  assert_file_exists "${CLIPPY_CALLS}"
  assert_contains "incremental" "$(cat "${CLIPPY_CALLS}")"
  assert_file_exists "${COMPILER_CALLS}"
  assert_contains "incremental" "$(cat "${COMPILER_CALLS}")"
}
