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

function make_external_pyvision_repo() {
  local remote_url="$1"
  local repo_dir
  repo_dir="$(mktemp -d)"
  git -C "${repo_dir}" init -q
  git -C "${repo_dir}" remote add origin "${remote_url}"
  mkdir -p "${repo_dir}/consumer" "${repo_dir}/tests"
  printf "" >"${repo_dir}/consumer/__init__.py"
  printf "%s" "${repo_dir}"
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

function test_pyvision_allows_private_imports_from_tracked_tests() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  cat >"${repo_dir}/src/pkg/widgets.py" <<'EOF'
def build_widget():
    return _helper()


def _helper():
    return "widget"
EOF
  cat >"${repo_dir}/tests/test_widgets.py" <<'EOF'
from pkg.widgets import _helper, build_widget


def test_private_helper_usage():
    assert _helper() == build_widget()
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 0 "${status}"
  assert_contains "All public/private classes/functions are used properly!" "${output}"
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

function test_pyvision_uri_pragma_passes_when_external_repo_imports_symbol() {
  local repo_dir external_repo remote_url
  repo_dir="$(make_pyvision_repo)"
  remote_url="https://github.com/example/pyvision-consumer.git"
  external_repo="$(make_external_pyvision_repo "${remote_url}")"
  cat >"${repo_dir}/src/pkg/widgets.py" <<EOF
# pyvision: ${remote_url}
class WidgetFactory:
    pass
EOF
  cat >"${external_repo}/consumer/widgets.py" <<'EOF'
from pkg.widgets import WidgetFactory


def build_widget():
    return WidgetFactory()
EOF
  track_repo_files "${repo_dir}"
  track_repo_files "${external_repo}"

  local output
  output="$(
    PYVISION_EXTERNAL_REPO_PATHS="${external_repo}" run_pyvision "${repo_dir}" 2>&1
  )"
  local status=$?

  rm -rf "${repo_dir}" "${external_repo}"
  assert_same 0 "${status}"
  assert_contains "No public functions or classes found!" "${output}"
}

function test_pyvision_uri_pragma_fails_when_external_repo_lacks_symbol() {
  local repo_dir external_repo remote_url
  repo_dir="$(make_pyvision_repo)"
  remote_url="https://github.com/example/pyvision-empty-consumer.git"
  external_repo="$(make_external_pyvision_repo "${remote_url}")"
  cat >"${repo_dir}/src/pkg/widgets.py" <<EOF
# pyvision: ${remote_url}
class WidgetFactory:
    pass
EOF
  cat >"${external_repo}/consumer/widgets.py" <<'EOF'
def build_widget():
    return "widget"
EOF
  track_repo_files "${repo_dir}"
  track_repo_files "${external_repo}"

  local output
  output="$(
    PYVISION_EXTERNAL_REPO_PATHS="${external_repo}" run_pyvision "${repo_dir}" 2>&1
  )"
  local status=$?

  rm -rf "${repo_dir}" "${external_repo}"
  assert_same 1 "${status}"
  assert_contains "external repository '${remote_url}' does not reference symbol 'WidgetFactory'" "${output}"
}

function test_pyvision_uri_pragma_fails_when_external_repo_cannot_resolve() {
  local repo_dir missing_repo
  repo_dir="$(make_pyvision_repo)"
  missing_repo="${repo_dir}/missing-consumer"
  cat >"${repo_dir}/src/pkg/widgets.py" <<EOF
# pyvision: file://${missing_repo}
class WidgetFactory:
    pass
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 1 "${status}"
  assert_contains "could not resolve external repository 'file://${missing_repo}'" "${output}"
}

function test_pyvision_uri_pragma_ignores_external_test_only_usage() {
  local repo_dir external_repo remote_url
  repo_dir="$(make_pyvision_repo)"
  remote_url="https://github.com/example/pyvision-test-only-consumer.git"
  external_repo="$(make_external_pyvision_repo "${remote_url}")"
  cat >"${repo_dir}/src/pkg/widgets.py" <<EOF
# pyvision: ${remote_url}
class WidgetFactory:
    pass
EOF
  cat >"${external_repo}/tests/test_widgets.py" <<'EOF'
from pkg.widgets import WidgetFactory


def test_widget_factory():
    assert WidgetFactory()
EOF
  track_repo_files "${repo_dir}"
  track_repo_files "${external_repo}"

  local output
  output="$(
    PYVISION_EXTERNAL_REPO_PATHS="${external_repo}" run_pyvision "${repo_dir}" 2>&1
  )"
  local status=$?

  rm -rf "${repo_dir}" "${external_repo}"
  assert_same 1 "${status}"
  assert_contains "external repository '${remote_url}' does not reference symbol 'WidgetFactory'" "${output}"
}

function test_pyvision_external_api_root_proves_return_record_surface() {
  local repo_dir external_repo remote_url
  repo_dir="$(make_pyvision_repo)"
  remote_url="https://github.com/example/pyvision-api-surface-consumer.git"
  external_repo="$(make_external_pyvision_repo "${remote_url}")"
  cat >"${repo_dir}/src/pkg/items.py" <<EOF
from dataclasses import dataclass


@dataclass
class ItemEntry:
    name: str


@dataclass
class ItemListing:
    entries: list[ItemEntry]


# pyvision: ${remote_url}
def list_items() -> ItemListing:
    return ItemListing([ItemEntry("one")])
EOF
  cat >"${external_repo}/consumer/items.py" <<'EOF'
from pkg.items import list_items


def render_items():
    return [entry.name for entry in list_items().entries]
EOF
  track_repo_files "${repo_dir}"
  track_repo_files "${external_repo}"

  local output
  output="$(
    PYVISION_EXTERNAL_REPO_PATHS="${external_repo}" run_pyvision "${repo_dir}" 2>&1
  )"
  local status=$?

  rm -rf "${repo_dir}" "${external_repo}"
  assert_same 0 "${status}"
  assert_contains "All public/private classes/functions are used properly!" "${output}"
}

function test_pyvision_unused_public_class_dependency_still_fails() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  cat >"${repo_dir}/src/pkg/items.py" <<'EOF'
from dataclasses import dataclass


@dataclass
class StaleRecord:
    name: str


@dataclass
class UnusedWrapper:
    record: StaleRecord
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 1 "${status}"
  assert_contains "StaleRecord" "${output}"
  assert_contains "UnusedWrapper" "${output}"
}
