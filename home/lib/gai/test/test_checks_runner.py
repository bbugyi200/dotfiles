"""Tests for the checks_runner module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ace.loop.checks_runner import (
    CHECK_COMPLETE_MARKER,
    CHECK_TYPE_AUTHOR_COMMENTS,
    CHECK_TYPE_CL_SUBMITTED,
    CHECK_TYPE_REVIEWER_COMMENTS,
    _extract_cl_number,
    _get_check_output_path,
    _get_checks_directory,
    _get_pending_checks,
    _parse_check_completion,
    check_pending_checks,
    has_pending_check,
)


def test_get_checks_directory() -> None:
    """Test that _get_checks_directory returns expected path."""
    result = _get_checks_directory()
    assert result == os.path.expanduser("~/.gai/checks")


def test_get_check_output_path_format() -> None:
    """Test that _get_check_output_path generates correct filename format."""
    name = "my_feature"
    check_type = CHECK_TYPE_CL_SUBMITTED
    timestamp = "241227_120000"

    result = _get_check_output_path(name, check_type, timestamp)

    assert result.endswith(f"{name}-{check_type}-{timestamp}.txt")
    assert "/.gai/checks/" in result


def test_get_check_output_path_sanitizes_name() -> None:
    """Test that special characters in name are sanitized."""
    name = "feature/with-special.chars"
    check_type = CHECK_TYPE_REVIEWER_COMMENTS
    timestamp = "241227_120000"

    result = _get_check_output_path(name, check_type, timestamp)

    # Name should be sanitized (non-alphanumeric replaced with _)
    assert "feature/with-special.chars" not in result
    assert "feature_with_special_chars" in result


def test_extract_cl_number_valid_http() -> None:
    """Test extracting CL number from http URL."""
    result = _extract_cl_number("http://cl/123456789")
    assert result == "123456789"


def test_extract_cl_number_valid_https() -> None:
    """Test extracting CL number from https URL."""
    result = _extract_cl_number("https://cl/987654321")
    assert result == "987654321"


def test_extract_cl_number_invalid_url() -> None:
    """Test that invalid URLs return None."""
    assert _extract_cl_number("not-a-url") is None
    assert _extract_cl_number("http://example.com/123") is None
    assert _extract_cl_number("") is None


def test_extract_cl_number_none() -> None:
    """Test that None input returns None."""
    assert _extract_cl_number(None) is None


def test_parse_check_completion_not_complete() -> None:
    """Test parsing output file without completion marker."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Some output without completion marker")
        temp_path = f.name

    try:
        is_complete, exit_code, content = _parse_check_completion(temp_path)
        assert is_complete is False
        assert exit_code == -1
        assert content == ""
    finally:
        os.unlink(temp_path)


def test_parse_check_completion_complete_success() -> None:
    """Test parsing completed output with exit code 0."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Command output here\n")
        f.write(f"{CHECK_COMPLETE_MARKER}EXIT_CODE: 0\n")
        temp_path = f.name

    try:
        is_complete, exit_code, content = _parse_check_completion(temp_path)
        assert is_complete is True
        assert exit_code == 0
        assert content == "Command output here"
    finally:
        os.unlink(temp_path)


def test_parse_check_completion_complete_failure() -> None:
    """Test parsing completed output with non-zero exit code."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Error output\n")
        f.write(f"{CHECK_COMPLETE_MARKER}EXIT_CODE: 1\n")
        temp_path = f.name

    try:
        is_complete, exit_code, content = _parse_check_completion(temp_path)
        assert is_complete is True
        assert exit_code == 1
        assert content == "Error output"
    finally:
        os.unlink(temp_path)


def test_parse_check_completion_missing_file() -> None:
    """Test that missing file returns not complete."""
    is_complete, exit_code, content = _parse_check_completion("/nonexistent/path.txt")
    assert is_complete is False
    assert exit_code == -1
    assert content == ""


def test_parse_check_completion_malformed_marker() -> None:
    """Test parsing output with malformed completion marker."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Output\n")
        f.write(f"{CHECK_COMPLETE_MARKER}MALFORMED\n")
        temp_path = f.name

    try:
        is_complete, exit_code, content = _parse_check_completion(temp_path)
        assert is_complete is True
        assert exit_code == 1  # Default to 1 on parse error
    finally:
        os.unlink(temp_path)


def test_get_pending_checks_no_directory() -> None:
    """Test that missing checks directory returns empty list."""
    mock_changespec = MagicMock()
    mock_changespec.name = "test_feature"

    with patch(
        "ace.loop.checks_runner._get_checks_directory",
        return_value="/nonexistent/path",
    ):
        result = _get_pending_checks(mock_changespec)
        assert result == []


def test_get_pending_checks_with_matching_files() -> None:
    """Test finding pending checks in the checks directory."""
    mock_changespec = MagicMock()
    mock_changespec.name = "my_feature"

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create check output files
        Path(temp_dir, "my_feature-cl_submitted-241227_120000.txt").touch()
        Path(temp_dir, "my_feature-reviewer_comments-241227_120001.txt").touch()
        Path(temp_dir, "other_feature-cl_submitted-241227_120002.txt").touch()

        with patch(
            "ace.loop.checks_runner._get_checks_directory", return_value=temp_dir
        ):
            result = _get_pending_checks(mock_changespec)

        # Should find 2 files matching my_feature
        assert len(result) == 2
        check_types = {check.check_type for check in result}
        assert CHECK_TYPE_CL_SUBMITTED in check_types
        assert CHECK_TYPE_REVIEWER_COMMENTS in check_types


def test_has_pending_check_true() -> None:
    """Test has_pending_check returns True when check exists."""
    mock_changespec = MagicMock()
    mock_changespec.name = "my_feature"

    with tempfile.TemporaryDirectory() as temp_dir:
        Path(temp_dir, "my_feature-cl_submitted-241227_120000.txt").touch()

        with patch(
            "ace.loop.checks_runner._get_checks_directory", return_value=temp_dir
        ):
            result = has_pending_check(mock_changespec, CHECK_TYPE_CL_SUBMITTED)
            assert result is True


def test_has_pending_check_false() -> None:
    """Test has_pending_check returns False when no check exists."""
    mock_changespec = MagicMock()
    mock_changespec.name = "my_feature"

    with tempfile.TemporaryDirectory() as temp_dir:
        # No files in directory
        with patch(
            "ace.loop.checks_runner._get_checks_directory", return_value=temp_dir
        ):
            result = has_pending_check(mock_changespec, CHECK_TYPE_CL_SUBMITTED)
            assert result is False


def test_has_pending_check_different_type() -> None:
    """Test has_pending_check returns False for different check type."""
    mock_changespec = MagicMock()
    mock_changespec.name = "my_feature"

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a cl_submitted check, but look for reviewer_comments
        Path(temp_dir, "my_feature-cl_submitted-241227_120000.txt").touch()

        with patch(
            "ace.loop.checks_runner._get_checks_directory", return_value=temp_dir
        ):
            result = has_pending_check(mock_changespec, CHECK_TYPE_REVIEWER_COMMENTS)
            assert result is False


def test_check_pending_checks_processes_completed() -> None:
    """Test that completed checks are processed and cleaned up."""
    mock_changespec = MagicMock()
    mock_changespec.name = "my_feature"
    mock_changespec.file_path = "/path/to/project.gp"
    mock_changespec.cl = "http://cl/123456"
    mock_changespec.status = "Mailed"
    mock_changespec.comments = None
    mock_log = MagicMock()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a completed check file
        check_file = Path(temp_dir, "my_feature-cl_submitted-241227_120000.txt")
        check_file.write_text(f"Output\n{CHECK_COMPLETE_MARKER}EXIT_CODE: 1\n")

        with patch(
            "ace.loop.checks_runner._get_checks_directory", return_value=temp_dir
        ):
            with patch("ace.loop.checks_runner.update_last_checked"):
                with patch("ace.loop.checks_runner.is_parent_submitted") as mock_parent:
                    mock_parent.return_value = True
                    check_pending_checks(mock_changespec, mock_log)

        # The check file should be cleaned up
        assert not check_file.exists()


def test_check_pending_checks_incomplete_not_processed() -> None:
    """Test that incomplete checks are not processed."""
    mock_changespec = MagicMock()
    mock_changespec.name = "my_feature"
    mock_log = MagicMock()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create an incomplete check file (no completion marker)
        check_file = Path(temp_dir, "my_feature-cl_submitted-241227_120000.txt")
        check_file.write_text("Still running...\n")

        with patch(
            "ace.loop.checks_runner._get_checks_directory", return_value=temp_dir
        ):
            result = check_pending_checks(mock_changespec, mock_log)

        # The check file should still exist
        assert check_file.exists()
        # No updates should be returned
        assert result == []


def test_check_type_constants() -> None:
    """Test that check type constants have expected values."""
    assert CHECK_TYPE_CL_SUBMITTED == "cl_submitted"
    assert CHECK_TYPE_REVIEWER_COMMENTS == "reviewer_comments"
    assert CHECK_TYPE_AUTHOR_COMMENTS == "author_comments"


def test_check_complete_marker() -> None:
    """Test that completion marker has expected value."""
    assert CHECK_COMPLETE_MARKER == "===CHECK_COMPLETE=== "
