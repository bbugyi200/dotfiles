#!/bin/bash

#################################################################################
# Regression tests for the pyvendor executable.                                 #
#################################################################################

PYVENDOR_SCRIPT="${PWD}/home/bin/executable_pyvendor"

function make_pyvendor_home() {
  local test_home="$1"
  mkdir -p "${test_home}/lib" "${test_home}/.local/share/chezmoi/home/bin"
  cp "${PWD}/home/lib/bugyi.sh" "${test_home}/lib/bugyi.sh"
}

function make_script() {
  local script_path="$1"
  mkdir -p "$(dirname "${script_path}")"
  printf '#!/bin/bash\nprintf "hello from %s\\n" "$(basename "$0")"\n' >"${script_path}"
  chmod +x "${script_path}"
}

function file_exists_text() {
  local file_path="$1"
  if [[ -f "${file_path}" ]]; then
    printf "yes"
  else
    printf "no"
  fi
}

function run_pyvendor_with_home() {
  local test_home="$1"
  shift
  HOME="${test_home}" DISABLE_LOG_COLOR=true bash "${PYVENDOR_SCRIPT}" "$@"
}

function test_chezmoi_executable_prefix_is_stripped_when_vendored() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  local test_home="${tmp_dir}/home"
  make_pyvendor_home "${test_home}"

  local source_script="${test_home}/.local/share/chezmoi/home/bin/executable_foo"
  make_script "${source_script}"

  local project_dir="${tmp_dir}/project"
  mkdir -p "${project_dir}"

  local date_suffix
  date_suffix="$(date +%y%m%d)"

  run_pyvendor_with_home "${test_home}" "${source_script}" "${project_dir}" >/dev/null

  assert_same "yes" "$(file_exists_text "${project_dir}/tools/foo-${date_suffix}")"
  assert_same "no" "$(file_exists_text "${project_dir}/tools/executable_foo-${date_suffix}")"

  rm -rf "${tmp_dir}"
}

function test_chezmoi_executable_prefix_cleanup_updates_old_references() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  local test_home="${tmp_dir}/home"
  make_pyvendor_home "${test_home}"

  local source_script="${test_home}/.local/share/chezmoi/home/bin/executable_foo"
  make_script "${source_script}"

  local project_dir="${tmp_dir}/project"
  mkdir -p "${project_dir}/tools"
  printf '#!/bin/bash\n' >"${project_dir}/tools/executable_foo-260101"
  printf '#!/bin/bash\n' >"${project_dir}/tools/foo-260102"
  printf 'tools/executable_foo-260101\ntools/foo-260102\n' >"${project_dir}/README.md"

  local date_suffix
  date_suffix="$(date +%y%m%d)"

  run_pyvendor_with_home "${test_home}" "${source_script}" "${project_dir}" >/dev/null

  assert_same "no" "$(file_exists_text "${project_dir}/tools/executable_foo-260101")"
  assert_same "no" "$(file_exists_text "${project_dir}/tools/foo-260102")"
  assert_same "yes" "$(file_exists_text "${project_dir}/tools/foo-${date_suffix}")"
  assert_contains "tools/foo-${date_suffix}" "$(cat "${project_dir}/README.md")"
  assert_same "" "$(grep -E 'executable_foo-260101|foo-260102' "${project_dir}/README.md" || true)"

  rm -rf "${tmp_dir}"
}

function test_non_chezmoi_and_non_prefixed_sources_keep_their_basenames() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  local test_home="${tmp_dir}/home"
  make_pyvendor_home "${test_home}"

  local date_suffix
  date_suffix="$(date +%y%m%d)"

  local non_chezmoi_source="${tmp_dir}/outside/executable_bar"
  make_script "${non_chezmoi_source}"
  local non_chezmoi_project="${tmp_dir}/non-chezmoi-project"
  mkdir -p "${non_chezmoi_project}"

  run_pyvendor_with_home "${test_home}" "${non_chezmoi_source}" "${non_chezmoi_project}" >/dev/null

  assert_same "yes" "$(file_exists_text "${non_chezmoi_project}/tools/executable_bar-${date_suffix}")"
  assert_same "no" "$(file_exists_text "${non_chezmoi_project}/tools/bar-${date_suffix}")"

  local non_prefixed_source="${test_home}/.local/share/chezmoi/home/bin/baz"
  make_script "${non_prefixed_source}"
  local non_prefixed_project="${tmp_dir}/non-prefixed-project"
  mkdir -p "${non_prefixed_project}"

  run_pyvendor_with_home "${test_home}" "${non_prefixed_source}" "${non_prefixed_project}" >/dev/null

  assert_same "yes" "$(file_exists_text "${non_prefixed_project}/tools/baz-${date_suffix}")"

  rm -rf "${tmp_dir}"
}
