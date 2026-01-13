"""Tests for commit_workflow/branch_info.py - branch and CL info retrieval."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from commit_workflow.branch_info import (
    get_cl_number,
    get_existing_changespec_description,
    get_parent_branch_name,
)


# Tests for get_parent_branch_name
@patch("commit_workflow.branch_info.run_shell_command")
def test_get_parent_branch_name_success(mock_run_shell: MagicMock) -> None:
    """Test get_parent_branch_name with successful command."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "parent_branch\n"
    mock_run_shell.return_value = mock_result

    result = get_parent_branch_name()

    assert result == "parent_branch"
    mock_run_shell.assert_called_once_with("branch_name", capture_output=True)


@patch("commit_workflow.branch_info.run_shell_command")
def test_get_parent_branch_name_failure(mock_run_shell: MagicMock) -> None:
    """Test get_parent_branch_name when command fails."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_run_shell.return_value = mock_result

    result = get_parent_branch_name()

    assert result is None


@patch("commit_workflow.branch_info.run_shell_command")
def test_get_parent_branch_name_empty_output(mock_run_shell: MagicMock) -> None:
    """Test get_parent_branch_name with empty output."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "\n"
    mock_run_shell.return_value = mock_result

    result = get_parent_branch_name()

    assert result is None


@patch("commit_workflow.branch_info.run_shell_command")
def test_get_parent_branch_name_whitespace_only(mock_run_shell: MagicMock) -> None:
    """Test get_parent_branch_name with whitespace only output."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "   \n"
    mock_run_shell.return_value = mock_result

    result = get_parent_branch_name()

    assert result is None


# Tests for get_cl_number
@patch("commit_workflow.branch_info.run_shell_command")
def test_get_cl_number_success(mock_run_shell: MagicMock) -> None:
    """Test get_cl_number with successful command."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "12345\n"
    mock_run_shell.return_value = mock_result

    result = get_cl_number()

    assert result == "12345"
    mock_run_shell.assert_called_once_with("branch_number", capture_output=True)


@patch("commit_workflow.branch_info.run_shell_command")
def test_get_cl_number_failure(mock_run_shell: MagicMock) -> None:
    """Test get_cl_number when command fails."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_run_shell.return_value = mock_result

    result = get_cl_number()

    assert result is None


@patch("commit_workflow.branch_info.run_shell_command")
def test_get_cl_number_non_digit(mock_run_shell: MagicMock) -> None:
    """Test get_cl_number returns None for non-digit output."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "abc123\n"
    mock_run_shell.return_value = mock_result

    result = get_cl_number()

    assert result is None


@patch("commit_workflow.branch_info.run_shell_command")
def test_get_cl_number_empty_output(mock_run_shell: MagicMock) -> None:
    """Test get_cl_number with empty output."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "\n"
    mock_run_shell.return_value = mock_result

    result = get_cl_number()

    assert result is None


# Tests for get_existing_changespec_description
@patch("commit_workflow.branch_info.get_project_file_path")
def test_get_existing_changespec_description_not_found(
    mock_get_path: MagicMock,
) -> None:
    """Test get_existing_changespec_description when file doesn't exist."""
    mock_get_path.return_value = "/nonexistent/file.gp"

    result = get_existing_changespec_description("project", "cl_name")

    assert result is None


@patch("commit_workflow.branch_info.get_project_file_path")
def test_get_existing_changespec_description_simple(mock_get_path: MagicMock) -> None:
    """Test get_existing_changespec_description with simple description."""
    content = """NAME: test_cl
DESCRIPTION: This is a test description
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        mock_get_path.return_value = temp_path
        result = get_existing_changespec_description("project", "test_cl")
        assert result == "This is a test description"
    finally:
        Path(temp_path).unlink()


@patch("commit_workflow.branch_info.get_project_file_path")
def test_get_existing_changespec_description_multiline(
    mock_get_path: MagicMock,
) -> None:
    """Test get_existing_changespec_description with multi-line description."""
    content = """NAME: test_cl
DESCRIPTION:
  Line 1
  Line 2
  Line 3
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        mock_get_path.return_value = temp_path
        result = get_existing_changespec_description("project", "test_cl")
        assert result == "Line 1\nLine 2\nLine 3"
    finally:
        Path(temp_path).unlink()


@patch("commit_workflow.branch_info.get_project_file_path")
def test_get_existing_changespec_description_with_blank_lines(
    mock_get_path: MagicMock,
) -> None:
    """Test get_existing_changespec_description with blank lines in description."""
    content = """NAME: test_cl
DESCRIPTION:
  First paragraph

  Second paragraph
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        mock_get_path.return_value = temp_path
        result = get_existing_changespec_description("project", "test_cl")
        assert result == "First paragraph\n\nSecond paragraph"
    finally:
        Path(temp_path).unlink()


@patch("commit_workflow.branch_info.get_project_file_path")
def test_get_existing_changespec_description_cl_not_found(
    mock_get_path: MagicMock,
) -> None:
    """Test get_existing_changespec_description when CL name doesn't match."""
    content = """NAME: other_cl
DESCRIPTION: Other description
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        mock_get_path.return_value = temp_path
        result = get_existing_changespec_description("project", "nonexistent_cl")
        assert result is None
    finally:
        Path(temp_path).unlink()


@patch("commit_workflow.branch_info.get_project_file_path")
def test_get_existing_changespec_description_multiple_changespecs(
    mock_get_path: MagicMock,
) -> None:
    """Test get_existing_changespec_description with multiple CLs in file."""
    content = """NAME: first_cl
DESCRIPTION: First CL description
STATUS: Drafted

NAME: target_cl
DESCRIPTION: Target CL description
STATUS: Mailed

NAME: third_cl
DESCRIPTION: Third CL description
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        mock_get_path.return_value = temp_path
        result = get_existing_changespec_description("project", "target_cl")
        assert result == "Target CL description"
    finally:
        Path(temp_path).unlink()


@patch("commit_workflow.branch_info.get_project_file_path")
def test_get_existing_changespec_description_stops_at_next_field(
    mock_get_path: MagicMock,
) -> None:
    """Test that description reading stops at next field."""
    content = """NAME: test_cl
DESCRIPTION:
  Description line
PARENT: parent_branch
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        mock_get_path.return_value = temp_path
        result = get_existing_changespec_description("project", "test_cl")
        assert result == "Description line"
    finally:
        Path(temp_path).unlink()


@patch("commit_workflow.branch_info.get_project_file_path")
def test_get_existing_changespec_description_no_description_field(
    mock_get_path: MagicMock,
) -> None:
    """Test get_existing_changespec_description when no DESCRIPTION field."""
    content = """NAME: test_cl
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        mock_get_path.return_value = temp_path
        result = get_existing_changespec_description("project", "test_cl")
        assert result is None
    finally:
        Path(temp_path).unlink()
