"""Tests for fix tests workflow operations."""

from work.changespec import ChangeSpec
from work.workflows.fix_tests import _extract_failing_test_targets


def test_extract_failing_test_targets_with_failed_markers() -> None:
    """Test extracting test targets that have (FAILED) markers."""
    changespec = ChangeSpec(
        name="test-cs",
        description="Test changespec",
        parent=None,
        cl="12345",
        status="Failing Tests",
        test_targets=[
            "//foo/bar:test1 (FAILED)",
            "//foo/bar:test2",
            "//baz/qux:test3 (FAILED)",
        ],
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
    )

    result = _extract_failing_test_targets(changespec)

    # Should only return the failed targets, with markers removed
    assert result == ["//foo/bar:test1", "//baz/qux:test3"]


def test_extract_failing_test_targets_no_failed_markers() -> None:
    """Test extracting when no test targets have (FAILED) markers."""
    changespec = ChangeSpec(
        name="test-cs",
        description="Test changespec",
        parent=None,
        cl="12345",
        status="Failing Tests",
        test_targets=[
            "//foo/bar:test1",
            "//foo/bar:test2",
            "//baz/qux:test3",
        ],
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
    )

    result = _extract_failing_test_targets(changespec)

    # Should return empty list when no targets have FAILED markers
    assert result == []


def test_extract_failing_test_targets_all_failed() -> None:
    """Test extracting when all test targets have (FAILED) markers."""
    changespec = ChangeSpec(
        name="test-cs",
        description="Test changespec",
        parent=None,
        cl="12345",
        status="Failing Tests",
        test_targets=[
            "//foo/bar:test1 (FAILED)",
            "//foo/bar:test2 (FAILED)",
            "//baz/qux:test3 (FAILED)",
        ],
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
    )

    result = _extract_failing_test_targets(changespec)

    # Should return all targets with markers removed
    assert result == ["//foo/bar:test1", "//foo/bar:test2", "//baz/qux:test3"]


def test_extract_failing_test_targets_none() -> None:
    """Test extracting when test_targets is None."""
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
    )

    result = _extract_failing_test_targets(changespec)

    # Should return empty list when test_targets is None
    assert result == []


def test_extract_failing_test_targets_empty_list() -> None:
    """Test extracting when test_targets is an empty list."""
    changespec = ChangeSpec(
        name="test-cs",
        description="Test changespec",
        parent=None,
        cl="12345",
        status="Failing Tests",
        test_targets=[],
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
    )

    result = _extract_failing_test_targets(changespec)

    # Should return empty list when test_targets is empty
    assert result == []
