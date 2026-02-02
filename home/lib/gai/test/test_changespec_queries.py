"""Tests for commit_workflow.changespec_queries module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from commit_workflow.changespec_queries import (
    changespec_exists,
    get_blocking_exact_match_changespec,
    project_file_exists,
)

# === Tests for project_file_exists ===


@patch("commit_workflow.changespec_queries.get_project_file_path")
def test_project_file_exists_true(mock_get_path: MagicMock) -> None:
    """Test project_file_exists returns True when file exists."""
    with tempfile.NamedTemporaryFile(suffix=".gp", delete=False) as f:
        mock_get_path.return_value = f.name
        result = project_file_exists("test_project")
        assert result is True
        Path(f.name).unlink()


@patch("commit_workflow.changespec_queries.get_project_file_path")
def test_project_file_exists_false(mock_get_path: MagicMock) -> None:
    """Test project_file_exists returns False when file doesn't exist."""
    mock_get_path.return_value = "/nonexistent/path.gp"
    result = project_file_exists("test_project")
    assert result is False


# === Tests for changespec_exists ===


@patch("commit_workflow.changespec_queries.get_project_file_path")
def test_changespec_exists_file_not_found(mock_get_path: MagicMock) -> None:
    """Test changespec_exists returns False when file doesn't exist."""
    mock_get_path.return_value = "/nonexistent/path.gp"
    result = changespec_exists("test_project", "test_cl")
    assert result is False


def test_changespec_exists_found() -> None:
    """Test changespec_exists returns True when CL name is found."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("# Project File\n\nNAME: existing_cl\nSTATUS: WIP\n")
        f.flush()

        with patch(
            "commit_workflow.changespec_queries.get_project_file_path"
        ) as mock_get_path:
            mock_get_path.return_value = f.name
            result = changespec_exists("test_project", "existing_cl")
            assert result is True

        Path(f.name).unlink()


def test_changespec_exists_not_found() -> None:
    """Test changespec_exists returns False when CL name is not found."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("# Project File\n\nNAME: other_cl\nSTATUS: WIP\n")
        f.flush()

        with patch(
            "commit_workflow.changespec_queries.get_project_file_path"
        ) as mock_get_path:
            mock_get_path.return_value = f.name
            result = changespec_exists("test_project", "nonexistent_cl")
            assert result is False

        Path(f.name).unlink()


def test_changespec_exists_empty_file() -> None:
    """Test changespec_exists returns False for empty file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("")
        f.flush()

        with patch(
            "commit_workflow.changespec_queries.get_project_file_path"
        ) as mock_get_path:
            mock_get_path.return_value = f.name
            result = changespec_exists("test_project", "any_cl")
            assert result is False

        Path(f.name).unlink()


@patch("commit_workflow.changespec_queries.get_project_file_path")
@patch("builtins.open")
def test_changespec_exists_exception(
    mock_open: MagicMock, mock_get_path: MagicMock
) -> None:
    """Test changespec_exists returns False on exception."""
    mock_get_path.return_value = "/some/path.gp"
    mock_open.side_effect = PermissionError("Access denied")

    with patch("os.path.isfile", return_value=True):
        result = changespec_exists("test_project", "test_cl")
        assert result is False


# === Tests for get_blocking_exact_match_changespec ===


@patch("commit_workflow.changespec_queries.get_project_file_path")
def test_get_blocking_exact_match_no_file(mock_get_path: MagicMock) -> None:
    """Test returns None when project file doesn't exist."""
    mock_get_path.return_value = "/nonexistent/path.gp"
    result = get_blocking_exact_match_changespec("proj", "foo")
    assert result is None


@patch("commit_workflow.changespec_queries.get_project_file_path")
@patch("ace.changespec.parse_project_file")
def test_get_blocking_exact_match_wip_status(
    mock_parse: MagicMock, mock_get_path: MagicMock
) -> None:
    """Test returns None when ChangeSpec exists with WIP status."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("# Project File\n")
        f.flush()
        mock_get_path.return_value = f.name

        mock_cs = MagicMock()
        mock_cs.name = "proj_foo"
        mock_cs.status = "WIP"
        mock_parse.return_value = [mock_cs]

        result = get_blocking_exact_match_changespec("proj", "foo")
        assert result is None

        Path(f.name).unlink()


@patch("commit_workflow.changespec_queries.get_project_file_path")
@patch("ace.changespec.parse_project_file")
def test_get_blocking_exact_match_drafted_status(
    mock_parse: MagicMock, mock_get_path: MagicMock
) -> None:
    """Test returns (name, 'Drafted') when exact match with Drafted status."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("# Project File\n")
        f.flush()
        mock_get_path.return_value = f.name

        mock_cs = MagicMock()
        mock_cs.name = "proj_foo"
        mock_cs.status = "Drafted"
        mock_parse.return_value = [mock_cs]

        result = get_blocking_exact_match_changespec("proj", "foo")
        assert result == ("proj_foo", "Drafted")

        Path(f.name).unlink()


@patch("commit_workflow.changespec_queries.get_project_file_path")
@patch("ace.changespec.parse_project_file")
def test_get_blocking_exact_match_mailed_status(
    mock_parse: MagicMock, mock_get_path: MagicMock
) -> None:
    """Test returns (name, 'Mailed') when exact match with Mailed status."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("# Project File\n")
        f.flush()
        mock_get_path.return_value = f.name

        mock_cs = MagicMock()
        mock_cs.name = "proj_bar"
        mock_cs.status = "Mailed"
        mock_parse.return_value = [mock_cs]

        result = get_blocking_exact_match_changespec("proj", "proj_bar")
        assert result == ("proj_bar", "Mailed")

        Path(f.name).unlink()


@patch("commit_workflow.changespec_queries.get_project_file_path")
@patch("ace.changespec.parse_project_file")
def test_get_blocking_exact_match_suffixed_not_blocking(
    mock_parse: MagicMock, mock_get_path: MagicMock
) -> None:
    """Test returns None when suffixed version exists but not exact match."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("# Project File\n")
        f.flush()
        mock_get_path.return_value = f.name

        # Only proj_foo__1 exists (suffixed), not proj_foo (exact)
        mock_cs = MagicMock()
        mock_cs.name = "proj_foo__1"
        mock_cs.status = "Drafted"
        mock_parse.return_value = [mock_cs]

        result = get_blocking_exact_match_changespec("proj", "foo")
        assert result is None

        Path(f.name).unlink()
