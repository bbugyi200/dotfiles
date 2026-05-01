#!/bin/bash

#################################################################################
# Regression tests for the pyvision executable.                                 #
#################################################################################

PYVISION_SCRIPT="${PWD}/home/bin/executable_pyvision"

function make_pyvision_repo() {
  local repo_dir
  repo_dir="$(mktemp -d)"
  git -C "${repo_dir}" init -q
  mkdir -p "${repo_dir}/src/pkg" "${repo_dir}/tests" "${repo_dir}/docs"
  printf "" >"${repo_dir}/src/pkg/__init__.py"
  printf "%s" "${repo_dir}"
}

function track_repo_files() {
  local repo_dir="$1"
  git -C "${repo_dir}" add .
}

function run_pyvision() {
  local repo_dir="$1"
  (
    cd "${repo_dir}" || exit 1
    python3 "${PYVISION_SCRIPT}" src/pkg
  )
}

function test_module_alias_usage_from_tracked_tests() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  cat >"${repo_dir}/src/pkg/records.py" <<'EOF'
class NotificationStoreRecord:
    pass
EOF
  cat >"${repo_dir}/tests/test_records.py" <<'EOF'
from pkg import records as facade


def test_record_usage():
    facade.NotificationStoreRecord()
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 0 "${status}"
  assert_contains "All public/private classes/functions are used properly!" "${output}"
}

function test_from_import_alias_usage_from_tracked_tests() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  cat >"${repo_dir}/src/pkg/widgets.py" <<'EOF'
class WidgetFactory:
    pass
EOF
  cat >"${repo_dir}/tests/test_widgets.py" <<'EOF'
from pkg.widgets import WidgetFactory as Factory


def test_widget_factory_usage():
    Factory()
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 0 "${status}"
  assert_contains "All public/private classes/functions are used properly!" "${output}"
}

function test_pyvision_rejects_test_file_pragmas() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  cat >"${repo_dir}/src/pkg/widgets.py" <<'EOF'
# pyvision: tests/test_widgets.py
class WidgetFactory:
    pass
EOF
  cat >"${repo_dir}/tests/test_widgets.py" <<'EOF'
from pkg.widgets import WidgetFactory


def test_widget_factory_usage():
    WidgetFactory()
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 1 "${status}"
  assert_contains "referenced test file 'tests/test_widgets.py' is forbidden" "${output}"
  assert_contains "Python test references are detected automatically" "${output}"
}

function test_pyvision_keeps_non_test_pragmas() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  cat >"${repo_dir}/src/pkg/widgets.py" <<'EOF'
# pyvision: docs/reference.md
class WidgetFactory:
    pass
EOF
  cat >"${repo_dir}/docs/reference.md" <<'EOF'
The WidgetFactory symbol is referenced from generated documentation.
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 0 "${status}"
  assert_contains "No public functions or classes found!" "${output}"
}
