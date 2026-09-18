#!/bin/bash

#################################################################################
# Regression tests for the LuaRocks chezmoi installer.                          #
#################################################################################

INSTALL_SCRIPT="${PWD}/home/.chezmoiscripts/run_onchange_install_luarocks.tmpl"
REQUIRED_ROCKS=(busted nlua llscheck luacheck luacov)

function set_up() {
  test_tmp="$(mktemp -d)"
  test_home="${test_tmp}/home"
  fake_bin="${test_tmp}/bin"
  sys_bin="${test_tmp}/sysbin"
  calls_file="${test_tmp}/calls.txt"
  failures_file="${test_tmp}/failures.txt"
  stdout_file="${test_tmp}/stdout.txt"
  stderr_file="${test_tmp}/stderr.txt"

  mkdir -p "${fake_bin}" "${sys_bin}" "${test_home}/.local/share/chezmoi/lib" \
    "${test_home}/.luarocks"
  touch "${calls_file}" "${failures_file}"
  write_chezmoi_utils
  write_host_stubs
}

function tear_down() {
  rm -rf "${test_tmp}"
}

function write_chezmoi_utils() {
  # Use the real helpers so the test tracks the installer's actual contract.
  cp "${PWD}/lib/chezmoi_utils.sh" \
    "${test_home}/.local/share/chezmoi/lib/chezmoi_utils.sh"
  cat >>"${test_home}/.local/share/chezmoi/lib/chezmoi_utils.sh" <<'EOF'

# Test override: model an interactive apply unless FAKE_HAS_TTY=0.
function chez::has_tty() {
  [[ "${FAKE_HAS_TTY:-1}" == 1 ]]
}
EOF
}

function write_host_stubs() {
  cat >"${fake_bin}/sudo" <<'EOF'
#!/bin/bash
printf 'sudo %s\n' "$*" >>"${CALLS_FILE}"
exit 1
EOF
  chmod +x "${fake_bin}/sudo"

  local tool
  for tool in bash mkdir rm; do
    ln -s "$(command -v "${tool}")" "${sys_bin}/${tool}"
  done
}

function write_lua51_stub() {
  cat >"${fake_bin}/lua5.1" <<'EOF'
#!/bin/bash
printf '5.1\n'
EOF
  chmod +x "${fake_bin}/lua5.1"
}

function write_brew_stub() {
  local brew_rc="${1:-0}"
  cat >"${fake_bin}/brew" <<EOF
#!/bin/bash
printf 'brew %s\n' "\$*" >>"\${CALLS_FILE}"
if [[ "\$1" != "install" || "\$2" != "luajit" ]]; then
  printf 'unexpected brew arguments: %s\n' "\$*" >&2
  exit 64
fi
exit ${brew_rc}
EOF
  chmod +x "${fake_bin}/brew"
}

function write_luarocks_stub() {
  cat >"${fake_bin}/luarocks" <<'EOF'
#!/bin/bash
printf 'luarocks %s\n' "$*" >>"${CALLS_FILE}"

if [[ "$1" != "--lua-version=5.1" || "$2" != "install" || "$3" != "--local" ]]; then
  printf 'unexpected luarocks arguments: %s\n' "$*" >&2
  exit 64
fi

rock="$4"
printf 'install:%s\n' "$rock" >>"${CALLS_FILE}"

status=0
while IFS=: read -r name code; do
  if [[ "$name" == "$rock" ]]; then
    status="$code"
    break
  fi
done <"${FAKE_LUAROCKS_FAILURES}"

if [[ "$status" -ne 0 ]]; then
  printf 'fake failure for %s\n' "$rock" >&2
  exit "$status"
fi

mkdir -p "${HOME}/.luarocks/rocks/${rock}"
printf 'installed\n' >"${HOME}/.luarocks/rocks/${rock}/marker"
exit 0
EOF
  chmod +x "${fake_bin}/luarocks"
}

function write_bootstrap_failure_stubs() {
  cat >"${fake_bin}/wget" <<'EOF'
#!/bin/bash
printf 'wget %s\n' "$*" >>"${CALLS_FILE}"
printf 'fake bootstrap download failure\n' >&2
exit 53
EOF
  chmod +x "${fake_bin}/wget"
}

function fail_rock() {
  printf '%s:%s\n' "$1" "$2" >>"${failures_file}"
}

function clear_failures() {
  : >"${failures_file}"
}

function run_installer() {
  PATH="${fake_bin}:${sys_bin}" \
    HOME="${test_home}" \
    CALLS_FILE="${calls_file}" \
    FAKE_LUAROCKS_FAILURES="${failures_file}" \
    FAKE_HAS_TTY="${FAKE_HAS_TTY:-1}" \
    bash "${INSTALL_SCRIPT}" >"${stdout_file}" 2>"${stderr_file}"
}

function stdout_text() {
  cat "${stdout_file}"
}

function stderr_text() {
  cat "${stderr_file}"
}

function calls_text() {
  cat "${calls_file}"
}

function install_attempts() {
  grep '^install:' "${calls_file}" || true
}

function required_attempts() {
  printf 'install:%s\n' "${REQUIRED_ROCKS[@]}"
}

function brew_and_install_calls() {
  grep -E '^(brew |install:)' "${calls_file}" || true
}

function final_summary() {
  sed -n '/LuaRocks failed to install required rocks/,$p' "${stderr_file}"
}

function count_occurrences() {
  local needle="$1"
  local text="$2"
  grep -F -c -- "$needle" <<<"${text}"
}

function write_tree_sentinel() {
  mkdir -p "${test_home}/.luarocks/lib/luarocks/rocks-5.1/existing"
  printf 'rock\n' >"${test_home}/.luarocks/lib/luarocks/rocks-5.1/existing/sentinel"
  printf 'config\n' >"${test_home}/.luarocks/config.lua"
}

function assert_tree_sentinel_survives() {
  assert_same "rock" \
    "$(cat "${test_home}/.luarocks/lib/luarocks/rocks-5.1/existing/sentinel")"
  assert_same "config" "$(cat "${test_home}/.luarocks/config.lua")"
}

function test_all_five_installs_succeed_in_order() {
  write_lua51_stub
  write_luarocks_stub

  local rc
  if run_installer; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_same "$(required_attempts)" "$(install_attempts)"
  assert_contains "INSTALLING ROCK: busted" "$(stdout_text)"
  assert_same "" "$(stderr_text)"
}

function test_busted_failure_survives_later_luacov_success() {
  write_lua51_stub
  write_luarocks_stub
  fail_rock busted 37

  local rc
  if run_installer; then rc=0; else rc=$?; fi

  assert_same "1" "${rc}"
  assert_same "$(required_attempts)" "$(install_attempts)"
  assert_contains "LuaRocks install failed for busted (exit status 37)." "$(stderr_text)"
  assert_contains "LuaRocks failed to install required rocks" "$(stderr_text)"
  assert_contains "- busted (exit status 37). Retry: luarocks --lua-version=5.1 install --local busted" \
    "$(final_summary)"
}

function test_multiple_failures_are_summarized_once_and_all_installs_are_attempted() {
  write_lua51_stub
  write_luarocks_stub
  fail_rock busted 37
  fail_rock luacov 42

  local rc summary
  if run_installer; then rc=0; else rc=$?; fi
  summary="$(final_summary)"

  assert_same "1" "${rc}"
  assert_same "$(required_attempts)" "$(install_attempts)"
  assert_contains "- busted (exit status 37)." "${summary}"
  assert_contains "- luacov (exit status 42)." "${summary}"
  assert_same "1" "$(count_occurrences "- busted (exit status 37)." "${summary}")"
  assert_same "1" "$(count_occurrences "- luacov (exit status 42)." "${summary}")"
}

function test_existing_tree_survives_failure_and_successful_retry() {
  write_lua51_stub
  write_luarocks_stub
  write_tree_sentinel
  fail_rock busted 37

  local rc
  if run_installer; then rc=0; else rc=$?; fi

  assert_same "1" "${rc}"
  assert_tree_sentinel_survives

  clear_failures
  : >"${calls_file}"
  if run_installer; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_same "$(required_attempts)" "$(install_attempts)"
  assert_tree_sentinel_survives
}

function test_bootstrap_failure_stops_before_rock_installs_and_preserves_tree() {
  write_lua51_stub
  write_bootstrap_failure_stubs
  write_tree_sentinel

  local rc
  if run_installer; then rc=0; else rc=$?; fi

  assert_same "1" "${rc}"
  assert_contains "fake bootstrap download failure" "$(stderr_text)"
  assert_same "" "$(install_attempts)"
  assert_tree_sentinel_survives
}

function test_non_interactive_failure_soft_exits_with_summary() {
  write_lua51_stub
  write_luarocks_stub
  fail_rock busted 37

  local rc
  if FAKE_HAS_TTY=0 run_installer; then rc=0; else rc=$?; fi

  assert_same "0" "${rc}"
  assert_contains "- busted (exit status 37)." "$(final_summary)"
  assert_contains "non-interactive chezmoi apply" "$(stdout_text)"
  assert_not_contains "sudo" "$(calls_text)"
}

function test_existing_luarocks_provisions_lua51_via_brew_before_rocks() {
  write_luarocks_stub
  write_brew_stub 0

  local rc expected
  if run_installer; then rc=0; else rc=$?; fi
  expected="$(printf 'brew install luajit\n%s' "$(required_attempts)")"

  assert_same "0" "${rc}"
  assert_same "${expected}" "$(brew_and_install_calls)"
  assert_contains "INSTALLING LUA 5.1" "$(stdout_text)"
  assert_same "" "$(stderr_text)"
}

function test_lua51_provision_failure_skips_rock_installs() {
  write_luarocks_stub
  write_brew_stub 1

  local rc
  if run_installer; then rc=0; else rc=$?; fi

  assert_same "1" "${rc}"
  assert_contains "brew install luajit" "$(calls_text)"
  assert_same "" "$(install_attempts)"
  assert_not_contains "LuaRocks install failed for" "$(stderr_text)"
  assert_not_contains "LuaRocks failed to install required rocks" "$(stderr_text)"
}
