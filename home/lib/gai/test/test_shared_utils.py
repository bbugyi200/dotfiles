"""Tests for gai.shared_utils module."""

import os
import string
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from gai_utils import run_shell_command
from shared_utils import (
    create_artifacts_directory,
    ensure_str_content,
    finalize_gai_log,
    generate_workflow_tag,
    initialize_gai_log,
    run_bam_command,
)


def test_ensure_str_content_with_string() -> None:
    """Test that string content is returned as-is."""
    content = "Hello, world!"
    assert ensure_str_content(content) == "Hello, world!"


def test_ensure_str_content_with_list() -> None:
    """Test that list content is converted to string."""
    content: list[str | dict[str, str]] = ["part1", "part2", {"key": "value"}]
    result = ensure_str_content(content)
    assert isinstance(result, str)
    assert "part1" in result
    assert "part2" in result


def test_ensure_str_content_with_empty_string() -> None:
    """Test that empty string is handled correctly."""
    assert ensure_str_content("") == ""


def test_run_shell_command_success() -> None:
    """Test that successful shell command returns proper result."""
    result = run_shell_command("echo 'test'", capture_output=True)
    assert result.returncode == 0
    assert "test" in result.stdout


def test_run_shell_command_failure() -> None:
    """Test that failed shell command returns non-zero exit code."""
    result = run_shell_command("exit 1", capture_output=True)
    assert result.returncode != 0


def test_create_artifacts_directory() -> None:
    """Test that artifacts directory is created with proper format."""
    # Use explicit project name to avoid dependency on workspace_name command
    project_name = "test-project"
    workflow_name = "test-workflow"
    artifacts_dir = create_artifacts_directory(workflow_name, project_name)

    # Check format: ~/.gai/projects/<project>/artifacts/<workflow>/YYYYMMDDHHMMSS
    expanded_home = str(Path.home())
    expected_prefix = (
        f"{expanded_home}/.gai/projects/{project_name}/artifacts/{workflow_name}/"
    )
    assert artifacts_dir.startswith(expected_prefix)
    timestamp_part = artifacts_dir.split("/")[-1]
    assert len(timestamp_part) == 14  # YYYYMMDDHHMMSS
    assert timestamp_part.isdigit()

    # Check directory exists
    assert Path(artifacts_dir).exists()
    assert Path(artifacts_dir).is_dir()

    # Cleanup - remove the entire test project directory
    project_dir = Path.home() / ".gai" / "projects" / project_name
    import shutil

    shutil.rmtree(project_dir)


def test_generate_workflow_tag() -> None:
    """Test that workflow tag is generated with correct format."""
    tag = generate_workflow_tag()

    # Should be 3 characters
    assert len(tag) == 3

    # Should only contain digits and uppercase letters
    valid_chars = string.digits + string.ascii_uppercase
    assert all(c in valid_chars for c in tag)


def test_generate_workflow_tag_uniqueness() -> None:
    """Test that generated tags are reasonably unique."""
    # Generate multiple tags and check they're not all the same
    tags = [generate_workflow_tag() for _ in range(100)]
    unique_tags = set(tags)

    # With 36^3 = 46656 possible combinations, we expect high uniqueness
    # Even with 100 samples, we should see at least 90 unique values
    assert len(unique_tags) >= 90


def test_initialize_gai_log() -> None:
    """Test that gai.md log is initialized correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        initialize_gai_log(tmpdir, "crs", "ABC")

        log_file = os.path.join(tmpdir, "gai.md")
        assert os.path.exists(log_file)

        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "GAI Workflow Log - crs (ABC)" in content
        assert "Started:" in content
        assert "Artifacts Directory:" in content
        assert tmpdir in content


def test_finalize_gai_log() -> None:
    """Test that gai.md log is finalized correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize first
        initialize_gai_log(tmpdir, "crs", "XYZ")

        # Finalize with success
        finalize_gai_log(tmpdir, "crs", "XYZ", success=True)

        log_file = os.path.join(tmpdir, "gai.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "Workflow Completed" in content
        assert "SUCCESS" in content
        assert "crs" in content
        assert "XYZ" in content


def test_finalize_gai_log_failure() -> None:
    """Test that gai.md log is finalized correctly with failure status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        initialize_gai_log(tmpdir, "add-tests", "DEF")
        finalize_gai_log(tmpdir, "add-tests", "DEF", success=False)

        log_file = os.path.join(tmpdir, "gai.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "FAILED" in content


@patch("shared_utils.run_shell_command")
def test_run_bam_command_success(mock_run_cmd: MagicMock) -> None:
    """Test that bam command is run successfully."""
    # This should not raise an exception
    run_bam_command("Test completed")
    mock_run_cmd.assert_called_once()


@patch("shared_utils.run_shell_command")
def test_run_bam_command_exception(mock_run_cmd: MagicMock) -> None:
    """Test that bam command exceptions are handled gracefully."""
    mock_run_cmd.side_effect = Exception("bam not found")

    # Should not raise an exception
    run_bam_command("Test message")


@patch("shared_utils.run_shell_command")
def test_create_artifacts_directory_without_project_name(
    mock_run_cmd: MagicMock,
) -> None:
    """Test creating artifacts directory when project_name is None."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "auto-project"
    mock_run_cmd.return_value = mock_result

    artifacts_dir = create_artifacts_directory("test-workflow")

    # Verify workspace_name was called
    mock_run_cmd.assert_called_once_with("workspace_name", capture_output=True)

    # Check directory format includes the auto-detected project name
    expanded_home = str(Path.home())
    expected_prefix = (
        f"{expanded_home}/.gai/projects/auto-project/artifacts/test-workflow/"
    )
    assert artifacts_dir.startswith(expected_prefix)

    # Cleanup
    import shutil

    project_dir = Path.home() / ".gai" / "projects" / "auto-project"
    if project_dir.exists():
        shutil.rmtree(project_dir)


@patch("shared_utils.run_shell_command")
def test_create_artifacts_directory_workspace_name_fails(
    mock_run_cmd: MagicMock,
) -> None:
    """Test that RuntimeError is raised when workspace_name fails."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "workspace_name not found"
    mock_run_cmd.return_value = mock_result

    with pytest.raises(RuntimeError) as exc_info:
        create_artifacts_directory("test-workflow")

    assert "Failed to get project name" in str(exc_info.value)
    assert "workspace_name not found" in str(exc_info.value)
