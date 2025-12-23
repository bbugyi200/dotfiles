"""Tests for fix tests workflow operations."""

from fix_tests_workflow.agents.oneshot import _parse_test_fixer_status
from work.changespec import ChangeSpec, HookEntry
from work.workflows.fix_tests import _extract_failing_test_targets


def test_extract_failing_test_targets_with_failed_markers() -> None:
    """Test extracting test targets from hooks with FAILED status."""
    changespec = ChangeSpec(
        name="test-cs",
        description="Test changespec",
        parent=None,
        cl="12345",
        status="Failing Tests",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
        hooks=[
            HookEntry(command="bb_rabbit_test //foo/bar:test1", status="FAILED"),
            HookEntry(command="bb_rabbit_test //foo/bar:test2", status="PASSED"),
            HookEntry(command="bb_rabbit_test //baz/qux:test3", status="FAILED"),
        ],
    )

    result = _extract_failing_test_targets(changespec)

    # Should only return the failed targets
    assert result == ["//foo/bar:test1", "//baz/qux:test3"]


def test_extract_failing_test_targets_no_failed_markers() -> None:
    """Test extracting when no hooks have FAILED status."""
    changespec = ChangeSpec(
        name="test-cs",
        description="Test changespec",
        parent=None,
        cl="12345",
        status="Failing Tests",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
        hooks=[
            HookEntry(command="bb_rabbit_test //foo/bar:test1", status="PASSED"),
            HookEntry(command="bb_rabbit_test //foo/bar:test2", status="PASSED"),
            HookEntry(command="bb_rabbit_test //baz/qux:test3", status="PASSED"),
        ],
    )

    result = _extract_failing_test_targets(changespec)

    # Should return empty list when no hooks have FAILED status
    assert result == []


def test_extract_failing_test_targets_all_failed() -> None:
    """Test extracting when all test target hooks have FAILED status."""
    changespec = ChangeSpec(
        name="test-cs",
        description="Test changespec",
        parent=None,
        cl="12345",
        status="Failing Tests",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
        hooks=[
            HookEntry(command="bb_rabbit_test //foo/bar:test1", status="FAILED"),
            HookEntry(command="bb_rabbit_test //foo/bar:test2", status="FAILED"),
            HookEntry(command="bb_rabbit_test //baz/qux:test3", status="FAILED"),
        ],
    )

    result = _extract_failing_test_targets(changespec)

    # Should return all targets
    assert result == ["//foo/bar:test1", "//foo/bar:test2", "//baz/qux:test3"]


def test_extract_failing_test_targets_none() -> None:
    """Test extracting when hooks is None."""
    changespec = ChangeSpec(
        name="test-cs",
        description="Test changespec",
        parent=None,
        cl="12345",
        status="Failing Tests",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
        hooks=None,
    )

    result = _extract_failing_test_targets(changespec)

    # Should return empty list when hooks is None
    assert result == []


def test_extract_failing_test_targets_empty_list() -> None:
    """Test extracting when hooks is an empty list."""
    changespec = ChangeSpec(
        name="test-cs",
        description="Test changespec",
        parent=None,
        cl="12345",
        status="Failing Tests",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
        hooks=[],
    )

    result = _extract_failing_test_targets(changespec)

    # Should return empty list when hooks is empty
    assert result == []


def test_extract_failing_test_targets_non_test_hooks_only() -> None:
    """Test extracting when only non-test-target hooks are failing."""
    changespec = ChangeSpec(
        name="test-cs",
        description="Test changespec",
        parent=None,
        cl="12345",
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
        hooks=[
            HookEntry(command="flake8 src", status="FAILED"),
            HookEntry(command="mypy src", status="FAILED"),
        ],
    )

    result = _extract_failing_test_targets(changespec)

    # Should return empty list - only test target hooks count
    assert result == []


# Tests for _parse_test_fixer_status


def test_parse_test_fixer_status_fixed_in_status_section() -> None:
    """Test that FIXED in Status section is detected as success."""
    log = """#### Changes Made
- Modified file X

#### Test Results
- Result: passed

#### Status
- FIXED
"""
    assert _parse_test_fixer_status(log) is True


def test_parse_test_fixer_status_failed_in_details_fixed_in_status() -> None:
    """Test that 'failed' in explanatory text doesn't override FIXED status.

    This is the bug case where the word 'failed' appeared in Details
    explaining why a different test command didn't work, but the actual
    Status was FIXED.
    """
    log = """#### Test Results
- Ran tests: bb_rabbit_test //some:test
- Result: passed
- Details: The test command provided in the instructions (bidder_settings_test) failed because the package does not exist

#### Status
- FIXED
"""
    assert _parse_test_fixer_status(log) is True


def test_parse_test_fixer_status_failed_in_status_section() -> None:
    """Test that FAILED in Status section is detected as failure."""
    log = """#### Changes Made
- Modified file X

#### Test Results
- Result: failed

#### Status
- FAILED
"""
    assert _parse_test_fixer_status(log) is False


def test_parse_test_fixer_status_partially_fixed() -> None:
    """Test that PARTIALLY_FIXED in Status section is detected as failure."""
    log = """#### Status
- PARTIALLY_FIXED
"""
    assert _parse_test_fixer_status(log) is False


def test_parse_test_fixer_status_build_error() -> None:
    """Test that BUILD_ERROR in Status section is detected as failure."""
    log = """#### Status
- BUILD_ERROR
"""
    assert _parse_test_fixer_status(log) is False


def test_parse_test_fixer_status_no_status_section_fixed() -> None:
    """Test fallback to full log when no Status section exists."""
    log = """#### Changes Made
- FIXED the issue
"""
    # Falls back to entire log, finds FIXED
    assert _parse_test_fixer_status(log) is True


def test_parse_test_fixer_status_no_status_section_failed() -> None:
    """Test fallback behavior when no Status section and FAILED in log."""
    log = """#### Test Results
- Tests FAILED
"""
    # Falls back to entire log, finds FAILED
    assert _parse_test_fixer_status(log) is False


def test_parse_test_fixer_status_case_insensitive() -> None:
    """Test that status detection is case insensitive."""
    log = """#### Status
- fixed
"""
    assert _parse_test_fixer_status(log) is True


def test_parse_test_fixer_status_passed_keyword() -> None:
    """Test that PASSED keyword is detected as success."""
    log = """#### Status
- PASSED
"""
    assert _parse_test_fixer_status(log) is True


def test_parse_test_fixer_status_all_tests_pass() -> None:
    """Test that 'ALL TESTS PASS' is detected as success."""
    log = """#### Status
- ALL TESTS PASS
"""
    assert _parse_test_fixer_status(log) is True


def test_parse_test_fixer_status_h2_status_section() -> None:
    """Test that ## Status section format works."""
    log = """## Status
- FIXED
"""
    assert _parse_test_fixer_status(log) is True
