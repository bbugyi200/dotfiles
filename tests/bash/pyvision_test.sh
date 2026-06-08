#!/bin/bash

#################################################################################
# Regression tests for the pyvision executable.                                 #
#################################################################################

PYVISION_SCRIPT="${PWD}/home/bin/executable_pyvision"

function make_pyvision_repo_at() {
  local repo_dir="$1"
  mkdir -p "${repo_dir}"
  git -C "${repo_dir}" init -q
  mkdir -p "${repo_dir}/src/pkg" "${repo_dir}/tests" "${repo_dir}/docs"
  printf "" >"${repo_dir}/src/pkg/__init__.py"
  printf "%s" "${repo_dir}"
}

function make_pyvision_repo() {
  local repo_dir
  repo_dir="$(mktemp -d)"
  make_pyvision_repo_at "${repo_dir}"
}

function track_repo_files() {
  local repo_dir="$1"
  git -C "${repo_dir}" add .
}

function make_external_pyvision_repo_at() {
  local repo_dir="$1"
  local remote_url="$2"
  mkdir -p "${repo_dir}"
  git -C "${repo_dir}" init -q
  git -C "${repo_dir}" remote add origin "${remote_url}"
  mkdir -p "${repo_dir}/consumer" "${repo_dir}/tests"
  printf "" >"${repo_dir}/consumer/__init__.py"
  printf "%s" "${repo_dir}"
}

function make_external_pyvision_repo() {
  local remote_url="$1"
  local repo_dir
  repo_dir="$(mktemp -d)"
  make_external_pyvision_repo_at "${repo_dir}" "${remote_url}"
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
  assert_same 1 "${status}"
  assert_contains "Unused public functions/classes" "${output}"
  assert_contains "NotificationStoreRecord" "${output}"
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
  assert_same 1 "${status}"
  assert_contains "Unused public functions/classes" "${output}"
  assert_contains "WidgetFactory" "${output}"
}

function test_module_alias_usage_from_non_test_file() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  cat >"${repo_dir}/src/pkg/records.py" <<'EOF'
class NotificationStoreRecord:
    pass
EOF
  cat >"${repo_dir}/app.py" <<'EOF'
from pkg import records as facade


def use_record():
    return facade.NotificationStoreRecord()
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
  assert_contains "referenced test-support path 'tests/test_widgets.py' is forbidden" "${output}"
  assert_contains "references from tests or testing utilities are not sufficient to keep a public symbol used" "${output}"
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
  cat >"${repo_dir}/app.py" <<'EOF'
from pkg.widgets import build_widget


def main():
    return build_widget()
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

function test_pyvision_fails_when_public_symbol_only_used_in_tests() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  cat >"${repo_dir}/src/pkg/widgets.py" <<'EOF'
def build_widget():
    return "widget"
EOF
  cat >"${repo_dir}/tests/test_widgets.py" <<'EOF'
from pkg.widgets import build_widget


def test_build_widget():
    assert build_widget() == "widget"
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 1 "${status}"
  assert_contains "Unused public functions/classes" "${output}"
  assert_contains "build_widget" "${output}"
}

function test_pyvision_ignores_public_symbols_defined_under_testing_dir() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  mkdir -p "${repo_dir}/src/pkg/testing"
  cat >"${repo_dir}/src/pkg/testing/helpers.py" <<'EOF'
class WidgetTestHelper:
    pass
EOF
  cat >"${repo_dir}/tests/test_widgets.py" <<'EOF'
from pkg.testing.helpers import WidgetTestHelper


def test_widget_test_helper():
    assert WidgetTestHelper()
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 0 "${status}"
  assert_contains "No public functions or classes found!" "${output}"
}

function test_pyvision_ignores_testing_dir_usage_for_public_symbols() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  mkdir -p "${repo_dir}/src/pkg/testing"
  cat >"${repo_dir}/src/pkg/widgets.py" <<'EOF'
def build_widget():
    return "widget"
EOF
  cat >"${repo_dir}/src/pkg/testing/helpers.py" <<'EOF'
from pkg.widgets import build_widget


def make_test_widget():
    return build_widget()
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 1 "${status}"
  assert_contains "Unused public functions/classes" "${output}"
  assert_contains "build_widget" "${output}"
}

function test_pyvision_allows_private_imports_from_testing_dir() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  mkdir -p "${repo_dir}/src/pkg/testing"
  cat >"${repo_dir}/src/pkg/widgets.py" <<'EOF'
def build_widget():
    return _helper()


def _helper():
    return "widget"
EOF
  cat >"${repo_dir}/app.py" <<'EOF'
from pkg.widgets import build_widget


def main():
    return build_widget()
EOF
  cat >"${repo_dir}/src/pkg/testing/helpers.py" <<'EOF'
from pkg.widgets import _helper


def make_test_widget():
    return _helper()
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 0 "${status}"
  assert_contains "All public/private classes/functions are used properly!" "${output}"
}

function test_pyvision_rejects_testing_dir_pragmas() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  mkdir -p "${repo_dir}/src/pkg/testing"
  cat >"${repo_dir}/src/pkg/widgets.py" <<'EOF'
# pyvision: src/pkg/testing/helpers.py
class WidgetFactory:
    pass
EOF
  cat >"${repo_dir}/src/pkg/testing/helpers.py" <<'EOF'
from pkg.widgets import WidgetFactory


def make_test_widget():
    return WidgetFactory()
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 1 "${status}"
  assert_contains "referenced test-support path 'src/pkg/testing/helpers.py' is forbidden" "${output}"
  assert_contains "references from tests or testing utilities are not sufficient to keep a public symbol used" "${output}"
}

function test_pyvision_passes_when_symbol_used_in_both_tests_and_non_tests() {
  local repo_dir
  repo_dir="$(make_pyvision_repo)"
  cat >"${repo_dir}/src/pkg/widgets.py" <<'EOF'
def build_widget():
    return "widget"
EOF
  cat >"${repo_dir}/app.py" <<'EOF'
from pkg.widgets import build_widget


def main():
    return build_widget()
EOF
  cat >"${repo_dir}/tests/test_widgets.py" <<'EOF'
from pkg.widgets import build_widget


def test_build_widget():
    assert build_widget() == "widget"
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 0 "${status}"
  assert_contains "All public/private classes/functions are used properly!" "${output}"
}

function test_pyvision_pragma_not_stale_when_only_test_imports_exist() {
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
  cat >"${repo_dir}/tests/test_widgets.py" <<'EOF'
from pkg.widgets import WidgetFactory


def test_widget_factory():
    WidgetFactory()
EOF
  track_repo_files "${repo_dir}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${repo_dir}"
  assert_same 0 "${status}"
  assert_contains "No public functions or classes found!" "${output}"
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

function test_pyvision_uri_pragma_prefers_canonical_sibling_checkout() {
  local parent_dir repo_dir stale_repo canonical_repo remote_url
  parent_dir="$(mktemp -d)"
  repo_dir="$(make_pyvision_repo_at "${parent_dir}/producer")"
  remote_url="https://github.com/example/pyvision-canonical-consumer.git"
  stale_repo="$(
    make_external_pyvision_repo_at \
      "${parent_dir}/pyvision-canonical-consumer_10" \
      "${remote_url}"
  )"
  canonical_repo="$(
    make_external_pyvision_repo_at \
      "${parent_dir}/pyvision-canonical-consumer" \
      "${remote_url}"
  )"
  cat >"${repo_dir}/src/pkg/widgets.py" <<EOF
# pyvision: ${remote_url}
class WidgetFactory:
    pass
EOF
  cat >"${stale_repo}/consumer/widgets.py" <<'EOF'
def build_widget():
    return "widget"
EOF
  cat >"${canonical_repo}/consumer/widgets.py" <<'EOF'
from pkg.widgets import WidgetFactory


def build_widget():
    return WidgetFactory()
EOF
  track_repo_files "${repo_dir}"
  track_repo_files "${stale_repo}"
  track_repo_files "${canonical_repo}"

  local output
  output="$(run_pyvision "${repo_dir}" 2>&1)"
  local status=$?

  rm -rf "${parent_dir}"
  assert_same 0 "${status}"
  assert_contains "No public functions or classes found!" "${output}"
}

function test_pyvision_uri_pragma_checks_later_matching_checkout() {
  local parent_dir repo_dir stale_repo canonical_repo remote_url
  parent_dir="$(mktemp -d)"
  repo_dir="$(make_pyvision_repo_at "${parent_dir}/producer")"
  remote_url="https://github.com/example/pyvision-later-consumer.git"
  stale_repo="$(make_external_pyvision_repo "${remote_url}")"
  canonical_repo="$(
    make_external_pyvision_repo_at \
      "${parent_dir}/pyvision-later-consumer" \
      "${remote_url}"
  )"
  cat >"${repo_dir}/src/pkg/widgets.py" <<EOF
# pyvision: ${remote_url}
class WidgetFactory:
    pass
EOF
  cat >"${stale_repo}/consumer/widgets.py" <<'EOF'
def build_widget():
    return "widget"
EOF
  cat >"${canonical_repo}/consumer/widgets.py" <<'EOF'
from pkg.widgets import WidgetFactory


def build_widget():
    return WidgetFactory()
EOF
  track_repo_files "${repo_dir}"
  track_repo_files "${stale_repo}"
  track_repo_files "${canonical_repo}"

  local output
  output="$(
    PYVISION_EXTERNAL_REPO_PATHS="${stale_repo}" run_pyvision "${repo_dir}" 2>&1
  )"
  local status=$?

  rm -rf "${parent_dir}" "${stale_repo}"
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

function test_pyvision_uri_pragma_ignores_external_testing_dir_usage() {
  local repo_dir external_repo remote_url
  repo_dir="$(make_pyvision_repo)"
  remote_url="https://github.com/example/pyvision-testing-only-consumer.git"
  external_repo="$(make_external_pyvision_repo "${remote_url}")"
  mkdir -p "${external_repo}/consumer/testing"
  cat >"${repo_dir}/src/pkg/widgets.py" <<EOF
# pyvision: ${remote_url}
class WidgetFactory:
    pass
EOF
  cat >"${external_repo}/consumer/testing/helpers.py" <<'EOF'
from pkg.widgets import WidgetFactory


def make_widget():
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
