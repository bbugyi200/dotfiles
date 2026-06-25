#!/bin/bash

#################################################################################
# Regression tests for the install_sase_github fatal sync gate.                 #
#################################################################################

INSTALL_SCRIPT="${PWD}/home/bin/executable_install_sase_github"

function set_up() {
  TEST_TMP="$(mktemp -d)"
  TEST_HOME="${TEST_TMP}/home"
  FAKE_BIN="${TEST_TMP}/bin"
  CALLS_FILE="${TEST_TMP}/calls.txt"
  UV_TOOL_DIR="${TEST_TMP}/uvtool"
  SASE_ORG_DIR="${TEST_HOME}/projects/github/sase-org"

  SASE_DIR="${SASE_ORG_DIR}/sase"
  SASE_CORE_DIR="${SASE_ORG_DIR}/sase-core"
  SASE_GITHUB_DIR="${SASE_ORG_DIR}/sase-github"
  SASE_TELEGRAM_DIR="${SASE_ORG_DIR}/sase-telegram"

  mkdir -p "${FAKE_BIN}" "${SASE_ORG_DIR}"

  init_clean_repo "${SASE_DIR}"
  init_clean_repo "${SASE_CORE_DIR}"
  init_clean_repo "${SASE_GITHUB_DIR}"
  init_clean_repo "${SASE_TELEGRAM_DIR}"

  # The script requires the local sase-core-rs project to exist past the gate.
  # Commit it so the sase-core worktree stays clean for the success smoke test.
  mkdir -p "${SASE_CORE_DIR}/crates/sase_core_py"
  printf '[project]\nname = "sase-core-rs"\n' \
    >"${SASE_CORE_DIR}/crates/sase_core_py/pyproject.toml"
  git -C "${SASE_CORE_DIR}" add crates/sase_core_py/pyproject.toml
  git -C "${SASE_CORE_DIR}" commit --quiet -m "add sase-core-rs project"
  git -C "${SASE_CORE_DIR}" push --quiet origin HEAD >/dev/null 2>&1

  write_fake_bins
}

function tear_down() {
  rm -rf "${TEST_TMP}"
}

# Create a clean git repo with a reachable, up-to-date upstream so that
# `git status --porcelain` is empty and `git pull --ff-only` is a no-op success.
function init_clean_repo() {
  local repo="$1"
  local remote="${repo}.git"

  git init --quiet --bare "${remote}"
  git init --quiet "${repo}"
  git -C "${repo}" config user.email "test@example.com"
  git -C "${repo}" config user.name "Test"
  git -C "${repo}" config commit.gpgsign false
  git -C "${repo}" commit --quiet --allow-empty -m "init"
  git -C "${repo}" remote add origin "${remote}"
  git -C "${repo}" push --quiet -u origin HEAD >/dev/null 2>&1
}

function push_incoming_change() {
  local repo="$1"
  shift
  local remote clone file

  remote="$(git -C "${repo}" config --get remote.origin.url)"
  clone="$(mktemp -d "${TEST_TMP}/incoming-$(basename "${repo}").XXXXXX")"
  git clone --quiet "${remote}" "${clone}"
  git -C "${clone}" config user.email "test@example.com"
  git -C "${clone}" config user.name "Test"
  git -C "${clone}" config commit.gpgsign false

  for file in "$@"; do
    mkdir -p "${clone}/$(dirname "${file}")"
    printf 'incoming %s\n' "${file}" >"${clone}/${file}"
    git -C "${clone}" add "${file}"
  done

  git -C "${clone}" commit --quiet -m "incoming change"
  git -C "${clone}" push --quiet origin HEAD >/dev/null 2>&1
}

# Stub uv/just/cargo/sase so the post-gate install/build/health phase never
# touches the real installation. Every call is appended to CALLS_FILE.
function write_fake_bins() {
  cat >"${FAKE_BIN}/uv" <<'EOF'
#!/bin/bash
set -euo pipefail
printf 'uv %s\n' "$*" >>"${CALLS_FILE}"
if [[ "$1" == "tool" && "$2" == "dir" ]]; then
  printf '%s\n' "${UV_TOOL_DIR}"
  exit 0
fi
exit 0
EOF

  cat >"${FAKE_BIN}/python3" <<'EOF'
#!/bin/bash
set -euo pipefail
printf 'python3 %s\n' "$*" >>"${CALLS_FILE}"
if [[ "${SASE_CORE_VERSION_GUARD_FAIL:-}" == "1" ]]; then
  echo "[validate_sase_core_rs_version] sase-core checkout is behind: source version 0.1.4 does not satisfy \`sase\`'s \`sase-core-rs>=0.2.0,<0.3.0\` dependency." >&2
  exit 1
fi
exit 0
EOF

  cat >"${FAKE_BIN}/just" <<'EOF'
#!/bin/bash
set -euo pipefail
printf 'just %s\n' "$*" >>"${CALLS_FILE}"
exit 0
EOF

  cat >"${FAKE_BIN}/cargo" <<'EOF'
#!/bin/bash
set -euo pipefail
printf 'cargo %s\n' "$*" >>"${CALLS_FILE}"
exit 0
EOF

  cat >"${FAKE_BIN}/sase" <<'EOF'
#!/bin/bash
set -euo pipefail
printf 'sase %s\n' "$*" >>"${CALLS_FILE}"
exit 0
EOF

  cat >"${FAKE_BIN}/sase-xprompt-lsp" <<'EOF'
#!/bin/bash
exit 0
EOF

  chmod +x "${FAKE_BIN}/uv" "${FAKE_BIN}/just" "${FAKE_BIN}/cargo" \
    "${FAKE_BIN}/sase" "${FAKE_BIN}/sase-xprompt-lsp" "${FAKE_BIN}/python3"

  # Provide a fake uv-tool python so probe_uv_tool_health passes on success.
  mkdir -p "${UV_TOOL_DIR}/sase/bin"
  cat >"${UV_TOOL_DIR}/sase/bin/python" <<'EOF'
#!/bin/bash
exit 0
EOF
  chmod +x "${UV_TOOL_DIR}/sase/bin/python"
}

function run_install() {
  PATH="${FAKE_BIN}:${PATH}" \
    HOME="${TEST_HOME}" \
    CALLS_FILE="${CALLS_FILE}" \
    UV_TOOL_DIR="${UV_TOOL_DIR}" \
    SASE_CORE_VERSION_GUARD_FAIL="${SASE_CORE_VERSION_GUARD_FAIL:-}" \
    bash "${INSTALL_SCRIPT}" "$@" 2>&1
}

function calls_text() {
  if [[ -f "${CALLS_FILE}" ]]; then
    cat "${CALLS_FILE}"
  fi
}

function sync_summary_line() {
  local label="$1"
  local output="$2"
  printf '%s\n' "${output}" | awk -v label="${label}" '$1 == label { print; exit }'
}

function test_pull_failure_is_fatal_and_stops_before_install() {
  # Break sase-github's upstream so `git pull --ff-only` fails.
  git -C "${SASE_GITHUB_DIR}" remote set-url origin "${TEST_TMP}/missing-remote.git"

  local output rc
  if output="$(run_install)"; then rc=0; else rc=$?; fi

  assert_same "1" "${rc}"
  assert_contains "could not sync required repositories" "${output}"
  assert_contains "sase-github" "${output}"
  assert_contains "${SASE_GITHUB_DIR}" "${output}"
  assert_contains "git pull --ff-only failed" "${output}"
  assert_contains "git -C ${SASE_GITHUB_DIR} pull --ff-only" "${output}"
  assert_contains "before touching the uv-tool sase environment" "${output}"

  # The uv-tool environment must not have been modified.
  assert_not_contains "uv tool install" "$(calls_text)"
  assert_not_contains "rust-install-uv-tool" "$(calls_text)"
  assert_not_contains "cargo install" "$(calls_text)"
  assert_not_contains "axe stop" "$(calls_text)"
}

function test_dirty_worktree_is_fatal() {
  # Introduce an uncommitted change in sase-core.
  printf 'dirty\n' >"${SASE_CORE_DIR}/uncommitted.txt"

  local output rc
  if output="$(run_install)"; then rc=0; else rc=$?; fi

  assert_same "1" "${rc}"
  assert_contains "sase-core" "${output}"
  assert_contains "dirty worktree" "${output}"

  # The installer must stop before axe maintenance / uv-tool work.
  assert_not_contains "uv tool install" "$(calls_text)"
  assert_not_contains "rust-install-uv-tool" "$(calls_text)"
  assert_not_contains "axe stop" "$(calls_text)"
}

function test_aggregated_failures_report_every_repo() {
  # Two repos fail for two different reasons in a single run.
  printf 'dirty\n' >"${SASE_CORE_DIR}/uncommitted.txt"
  git -C "${SASE_GITHUB_DIR}" remote set-url origin "${TEST_TMP}/missing-remote.git"

  local output rc
  if output="$(run_install)"; then rc=0; else rc=$?; fi

  assert_same "1" "${rc}"
  assert_contains "sase-core" "${output}"
  assert_contains "dirty worktree" "${output}"
  assert_contains "sase-github" "${output}"
  assert_contains "git pull --ff-only failed" "${output}"
}

function test_clean_repos_pass_the_gate_and_reach_install() {
  local output rc
  if output="$(run_install --install)"; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_contains ">>> Repo sync complete." "${output}"
  assert_contains "up to date" "$(sync_summary_line "sase" "${output}")"
  assert_contains "up to date" "$(sync_summary_line "sase-core" "${output}")"
  assert_contains "up to date" "$(sync_summary_line "sase-github" "${output}")"
  assert_contains "up to date" "$(sync_summary_line "sase-telegram" "${output}")"
  assert_not_contains "could not sync required repositories" "${output}"

  # The fake install/build commands were reached past the gate.
  assert_contains "uv tool install" "$(calls_text)"
  assert_contains "--reinstall-package sase-core-rs" "$(calls_text)"
  assert_contains "rust-install-uv-tool" "$(calls_text)"
}

function test_sase_core_rs_version_skew_is_fatal_before_axe_maintenance() {
  local output rc
  if output="$(SASE_CORE_VERSION_GUARD_FAIL=1 run_install --install)"; then rc=0; else rc=$?; fi

  assert_same "1" "${rc}"
  assert_contains "sase-core checkout is behind" "${output}"
  assert_contains "source version 0.1.4" "${output}"

  assert_contains "python3 ${SASE_DIR}/tools/validate_sase_core_rs_version" "$(calls_text)"
  assert_not_contains "uv tool install" "$(calls_text)"
  assert_not_contains "rust-install-uv-tool" "$(calls_text)"
  assert_not_contains "cargo install" "$(calls_text)"
  assert_not_contains "axe stop" "$(calls_text)"
  assert_not_contains "maintenance remains active" "${output}"
}

function test_files_changed_count_is_reported_for_fast_forward_pull() {
  push_incoming_change "${SASE_CORE_DIR}" one.txt two.txt nested/three.txt

  local output rc
  if output="$(run_install --install)"; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_contains ">>> Repo sync complete." "${output}"
  assert_contains "3 files changed" "$(sync_summary_line "sase-core" "${output}")"
  assert_contains "up to date" "$(sync_summary_line "sase" "${output}")"
  assert_contains "up to date" "$(sync_summary_line "sase-github" "${output}")"
  assert_contains "up to date" "$(sync_summary_line "sase-telegram" "${output}")"
}

function test_files_changed_count_uses_singular_wording() {
  push_incoming_change "${SASE_TELEGRAM_DIR}" single.txt

  local output rc
  if output="$(run_install --install)"; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_contains "1 file changed" "$(sync_summary_line "sase-telegram" "${output}")"
  assert_not_contains "1 files changed" "$(sync_summary_line "sase-telegram" "${output}")"
}
