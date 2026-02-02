"""Tests for commit_workflow/branch_info.py - branch and CL info retrieval."""

from unittest.mock import MagicMock, patch

from commit_workflow.branch_info import (
    get_cl_number,
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
