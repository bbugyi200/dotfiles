"""Tests for ace.cl_status module."""

from unittest.mock import MagicMock, patch

from ace.cl_status import (
    SYNCABLE_STATUSES,
    _extract_cl_number,
    is_cl_submitted,
    is_parent_submitted,
)

# === Tests for _extract_cl_number ===


def test_extract_cl_number_http() -> None:
    """Test extracting CL number from HTTP URL."""
    result = _extract_cl_number("http://cl/123456789")
    assert result == "123456789"


def test_extract_cl_number_https() -> None:
    """Test extracting CL number from HTTPS URL."""
    result = _extract_cl_number("https://cl/999888777")
    assert result == "999888777"


def test_extract_cl_number_none() -> None:
    """Test that None input returns None."""
    result = _extract_cl_number(None)
    assert result is None


def test_extract_cl_number_empty_string() -> None:
    """Test that empty string returns None."""
    result = _extract_cl_number("")
    assert result is None


def test_extract_cl_number_invalid_format() -> None:
    """Test that invalid formats return None."""
    result = _extract_cl_number("not-a-url")
    assert result is None


def test_extract_cl_number_wrong_domain() -> None:
    """Test that wrong domain returns None."""
    result = _extract_cl_number("http://example.com/123456")
    assert result is None


# === Tests for is_parent_submitted ===


def test_is_parent_submitted_no_parent() -> None:
    """Test that no parent means parent is considered submitted."""
    mock_changespec = MagicMock()
    mock_changespec.parent = None

    result = is_parent_submitted(mock_changespec)

    assert result is True


@patch("ace.cl_status.find_all_changespecs")
def test_is_parent_submitted_parent_submitted(mock_find: MagicMock) -> None:
    """Test that submitted parent returns True."""
    mock_parent = MagicMock()
    mock_parent.name = "parent_cs"
    mock_parent.status = "Submitted"

    mock_find.return_value = [mock_parent]

    mock_changespec = MagicMock()
    mock_changespec.parent = "parent_cs"

    result = is_parent_submitted(mock_changespec)

    assert result is True


@patch("ace.cl_status.find_all_changespecs")
def test_is_parent_submitted_parent_not_submitted(mock_find: MagicMock) -> None:
    """Test that non-submitted parent returns False."""
    mock_parent = MagicMock()
    mock_parent.name = "parent_cs"
    mock_parent.status = "Mailed"

    mock_find.return_value = [mock_parent]

    mock_changespec = MagicMock()
    mock_changespec.parent = "parent_cs"

    result = is_parent_submitted(mock_changespec)

    assert result is False


@patch("ace.cl_status.find_all_changespecs")
def test_is_parent_submitted_parent_not_found(mock_find: MagicMock) -> None:
    """Test that missing parent returns True (assumed deleted)."""
    mock_find.return_value = []

    mock_changespec = MagicMock()
    mock_changespec.parent = "nonexistent_parent"

    result = is_parent_submitted(mock_changespec)

    assert result is True


# === Tests for is_cl_submitted ===


def test_is_cl_submitted_no_cl_url() -> None:
    """Test that missing CL URL returns False."""
    mock_changespec = MagicMock()
    mock_changespec.cl = None

    result = is_cl_submitted(mock_changespec)

    assert result is False


def test_is_cl_submitted_invalid_cl_url() -> None:
    """Test that invalid CL URL returns False."""
    mock_changespec = MagicMock()
    mock_changespec.cl = "invalid-url"

    result = is_cl_submitted(mock_changespec)

    assert result is False


@patch("subprocess.run")
@patch("ace.cl_status.get_workspace_directory_for_changespec")
def test_is_cl_submitted_true(mock_get_ws: MagicMock, mock_run: MagicMock) -> None:
    """Test that submitted CL returns True."""
    mock_get_ws.return_value = "/workspace"
    mock_run.return_value = MagicMock(returncode=0)

    mock_changespec = MagicMock()
    mock_changespec.cl = "http://cl/123456"

    result = is_cl_submitted(mock_changespec)

    assert result is True
    mock_run.assert_called_once()


@patch("subprocess.run")
@patch("ace.cl_status.get_workspace_directory_for_changespec")
def test_is_cl_submitted_false(mock_get_ws: MagicMock, mock_run: MagicMock) -> None:
    """Test that non-submitted CL returns False."""
    mock_get_ws.return_value = "/workspace"
    mock_run.return_value = MagicMock(returncode=1)

    mock_changespec = MagicMock()
    mock_changespec.cl = "http://cl/123456"

    result = is_cl_submitted(mock_changespec)

    assert result is False


@patch("subprocess.run")
@patch("ace.cl_status.get_workspace_directory_for_changespec")
def test_is_cl_submitted_command_not_found(
    mock_get_ws: MagicMock, mock_run: MagicMock
) -> None:
    """Test that command not found returns False."""
    mock_get_ws.return_value = "/workspace"
    mock_run.side_effect = FileNotFoundError()

    mock_changespec = MagicMock()
    mock_changespec.cl = "http://cl/123456"

    result = is_cl_submitted(mock_changespec)

    assert result is False


@patch("subprocess.run")
@patch("ace.cl_status.get_workspace_directory_for_changespec")
def test_is_cl_submitted_other_exception(
    mock_get_ws: MagicMock, mock_run: MagicMock
) -> None:
    """Test that other exceptions return False."""
    mock_get_ws.return_value = "/workspace"
    mock_run.side_effect = OSError("Permission denied")

    mock_changespec = MagicMock()
    mock_changespec.cl = "http://cl/123456"

    result = is_cl_submitted(mock_changespec)

    assert result is False


# === Tests for SYNCABLE_STATUSES constant ===


def test_syncable_statuses_contains_mailed() -> None:
    """Test that SYNCABLE_STATUSES contains Mailed."""
    assert "Mailed" in SYNCABLE_STATUSES
