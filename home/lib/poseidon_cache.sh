# Shared Poseidon Cargo-cache helpers for Athena. Sourced by the rustc wrapper
# and the pressure watcher. Override paths through the environment in tests.

POSEIDON_MOUNT="${POSEIDON_MOUNT:-/mnt/poseidon}"
POSEIDON_UUID="${POSEIDON_UUID:-e0d96fde-be60-4f3b-bed7-3e9700060fdb}"
POSEIDON_OLD_TARGET="${POSEIDON_OLD_TARGET:-${POSEIDON_MOUNT}/cargo-target}"
POSEIDON_SCCACHE_DIR="${POSEIDON_SCCACHE_DIR:-${POSEIDON_MOUNT}/sccache}"
POSEIDON_SCCACHE_SIZE="${POSEIDON_SCCACHE_SIZE:-42949672960}"
POSEIDON_SCCACHE_SOCK="${POSEIDON_SCCACHE_SOCK:-${POSEIDON_SCCACHE_DIR}/sccache.sock}"
POSEIDON_SCCACHE_CONF="${POSEIDON_SCCACHE_CONF:-${HOME}/.config/sccache/config}"
POSEIDON_MIN_AVAIL_BYTES="${POSEIDON_MIN_AVAIL_BYTES:-34359738368}"
POSEIDON_RECOVERY_AVAIL_BYTES="${POSEIDON_RECOVERY_AVAIL_BYTES:-51539607552}"
POSEIDON_WARN_USED_PCT="${POSEIDON_WARN_USED_PCT:-75}"
POSEIDON_BYPASS_USED_PCT="${POSEIDON_BYPASS_USED_PCT:-80}"
POSEIDON_CRITICAL_USED_PCT="${POSEIDON_CRITICAL_USED_PCT:-90}"
POSEIDON_RECOVERY_USED_PCT="${POSEIDON_RECOVERY_USED_PCT:-70}"
POSEIDON_SCRATCH_SOFT_BYTES="${POSEIDON_SCRATCH_SOFT_BYTES:-17179869184}"
POSEIDON_SMART_PROM="${POSEIDON_SMART_PROM:-/var/lib/prometheus/node-exporter/smartmon.prom}"
POSEIDON_SMART_STALE_SECONDS="${POSEIDON_SMART_STALE_SECONDS:-2700}"
POSEIDON_SMART_DISK="${POSEIDON_SMART_DISK:-}"
POSEIDON_SMART_BASELINE_REALLOC="${POSEIDON_SMART_BASELINE_REALLOC:-41}"
POSEIDON_SMART_BASELINE_RUNTIME="${POSEIDON_SMART_BASELINE_RUNTIME:-41}"
POSEIDON_SMART_BASELINE_UNCORRECTABLE="${POSEIDON_SMART_BASELINE_UNCORRECTABLE:-0}"
DF_BIN="${POSEIDON_DF_BIN:-/usr/bin/df}"
FINDMNT_BIN="${POSEIDON_FINDMNT_BIN:-/usr/bin/findmnt}"
STAT_BIN="${POSEIDON_STAT_BIN:-/usr/bin/stat}"
DU_BIN="${POSEIDON_DU_BIN:-/usr/bin/du}"

poseidon_now() {
  if [[ -n "${POSEIDON_FAKE_NOW-}" ]]; then
    printf '%s\n' "$POSEIDON_FAKE_NOW"
    return
  fi
  date +%s
}

poseidon_is_symlink() {
  if [[ -n "${POSEIDON_FAKE_SYMLINK-}" ]]; then
    [[ "$POSEIDON_FAKE_SYMLINK" == "1" ]]
    return
  fi
  [[ -L "$POSEIDON_MOUNT" ]]
}

poseidon_mounted_uuid() {
  if [[ -n "${POSEIDON_FAKE_UUID-}" ]]; then
    printf '%s\n' "$POSEIDON_FAKE_UUID"
    return 0
  fi
  if [[ "${POSEIDON_FAKE_MOUNTED-}" == "0" ]]; then
    return 1
  fi
  "$FINDMNT_BIN" -M "$POSEIDON_MOUNT" -n -o UUID 2>/dev/null
}

poseidon_df_fields() {
  # Prints: avail_bytes used_pct
  if [[ -n "${POSEIDON_FAKE_AVAIL-}" || -n "${POSEIDON_FAKE_USED_PCT-}" ]]; then
    printf '%s %s\n' "${POSEIDON_FAKE_AVAIL:-0}" "${POSEIDON_FAKE_USED_PCT:-0}"
    return 0
  fi
  "$DF_BIN" -B1 -P "$POSEIDON_MOUNT" 2>/dev/null | awk 'NR==2 {gsub("%","",$5); print $4, $5}'
}

root_df_avail() {
  if [[ -n "${POSEIDON_FAKE_ROOT_AVAIL-}" ]]; then
    printf '%s\n' "$POSEIDON_FAKE_ROOT_AVAIL"
    return 0
  fi
  "$DF_BIN" -B1 -P / 2>/dev/null | awk 'NR==2 {print $4}'
}

poseidon_mount_ok() {
  local uuid
  if poseidon_is_symlink; then
    return 1
  fi
  if [[ ! -d "$POSEIDON_MOUNT" ]]; then
    return 1
  fi
  uuid="$(poseidon_mounted_uuid || true)"
  [[ -n "$uuid" && "$uuid" == "$POSEIDON_UUID" ]]
}

poseidon_volume_same_fs() {
  local path="$1"
  local mount_dev path_dev
  if [[ -n "${POSEIDON_FAKE_FOREIGN_FS-}" && -e "$path" ]]; then
    [[ "$POSEIDON_FAKE_FOREIGN_FS" != "1" ]]
    return
  fi
  if [[ ! -e "$path" ]]; then
    return 0
  fi
  mount_dev="$("$STAT_BIN" -c '%d' "$POSEIDON_MOUNT" 2>/dev/null || true)"
  path_dev="$("$STAT_BIN" -c '%d' "$path" 2>/dev/null || true)"
  [[ -n "$mount_dev" && "$mount_dev" == "$path_dev" ]]
}

poseidon_should_cache() {
  local avail used_pct
  if ! poseidon_mount_ok; then
    return 1
  fi
  if ! poseidon_volume_same_fs "$POSEIDON_SCCACHE_DIR"; then
    return 1
  fi
  read -r avail used_pct <<<"$(poseidon_df_fields)"
  if [[ -z "$avail" || -z "$used_pct" ]]; then
    return 1
  fi
  if ((used_pct >= POSEIDON_BYPASS_USED_PCT)); then
    return 1
  fi
  if ((avail < POSEIDON_MIN_AVAIL_BYTES)); then
    return 1
  fi
  return 0
}

normalize_sccache_env() {
  export SCCACHE_CONF="$POSEIDON_SCCACHE_CONF"
  export SCCACHE_DIR="$POSEIDON_SCCACHE_DIR"
  export SCCACHE_CACHE_SIZE="$POSEIDON_SCCACHE_SIZE"
  export SCCACHE_SERVER_UDS="$POSEIDON_SCCACHE_SOCK"
  unset SCCACHE_SERVER_PORT \
    SCCACHE_BUCKET SCCACHE_REGION SCCACHE_ENDPOINT SCCACHE_S3_KEY_PREFIX \
    AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE \
    SCCACHE_REDIS SCCACHE_MEMCACHED \
    SCCACHE_GCS_BUCKET SCCACHE_GCS_RW_MODE SCCACHE_GCS_KEY_PATH \
    SCCACHE_AZURE_CONNECTION_STRING SCCACHE_AZURE_BLOB_CONTAINER \
    SCCACHE_GHA_ENABLED \
    SCCACHE_WEBDAV_ENDPOINT SCCACHE_WEBDAV_USERNAME SCCACHE_WEBDAV_PASSWORD \
    SCCACHE_WEBDAV_TOKEN \
    SCCACHE_OSS_BUCKET SCCACHE_COS_BUCKET
}
