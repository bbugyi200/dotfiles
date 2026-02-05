"""Tests for gai.shared_utils module."""

import os
import string
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from gai_utils import run_shell_command
from shared_utils import (
    _finalize_log_file,
    _initialize_log_file,
    apply_section_marker_handling,
    convert_timestamp_to_artifacts_format,
    create_artifacts_directory,
    ensure_str_content,
    finalize_gai_log,
    generate_workflow_tag,
    get_gai_log_file,
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


# Tests for get_gai_log_file
def test_get_gai_log_file() -> None:
    """Test get_gai_log_file returns correct path."""
    result = get_gai_log_file("/path/to/artifacts")
    assert result == "/path/to/artifacts/gai.md"


def test_get_gai_log_file_trailing_slash() -> None:
    """Test get_gai_log_file handles various path formats."""
    result = get_gai_log_file("/artifacts")
    assert result.endswith("gai.md")


# Tests for _initialize_log_file
@patch("shared_utils.print_file_operation")
def test_initialize_log_file_success(mock_print: MagicMock) -> None:
    """Test _initialize_log_file creates file with content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.md")
        _initialize_log_file(log_path, "Test content\n", "Init log")

        content = Path(log_path).read_text()
        assert content == "Test content\n"
        mock_print.assert_called_once_with("Init log", log_path, True)


@patch("shared_utils.print_status")
def test_initialize_log_file_error(mock_print_status: MagicMock) -> None:
    """Test _initialize_log_file handles write errors gracefully."""
    _initialize_log_file("/nonexistent/dir/file.md", "content", "Test op")
    mock_print_status.assert_called_once()
    call_msg = mock_print_status.call_args[0][0]
    assert "Failed" in call_msg


# Tests for _finalize_log_file
@patch("shared_utils.print_file_operation")
def test_finalize_log_file_appends(mock_print: MagicMock) -> None:
    """Test _finalize_log_file appends to existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.md")
        # Create initial file
        Path(log_path).write_text("Initial\n")

        _finalize_log_file(log_path, "Final\n", "Finalize log")

        content = Path(log_path).read_text()
        assert "Initial" in content
        assert "Final" in content
        mock_print.assert_called_once_with("Finalize log", log_path, True)


@patch("shared_utils.print_status")
def test_finalize_log_file_error(mock_print_status: MagicMock) -> None:
    """Test _finalize_log_file handles errors gracefully."""
    _finalize_log_file("/nonexistent/dir/file.md", "content", "Test op")
    mock_print_status.assert_called_once()
    call_msg = mock_print_status.call_args[0][0]
    assert "Failed" in call_msg


# Tests for apply_section_marker_handling
def test_apply_section_marker_handling_no_marker() -> None:
    """Test that content without section markers is returned unchanged."""
    content = "Regular content without markers"
    assert apply_section_marker_handling(content, True) == content
    assert apply_section_marker_handling(content, False) == content


def test_apply_section_marker_handling_triple_hash_at_line_start() -> None:
    """Test ### marker at line start is returned unchanged."""
    content = "### Section Header\nContent here"
    result = apply_section_marker_handling(content, is_at_line_start=True)
    assert result == content


def test_apply_section_marker_handling_triple_hash_not_at_line_start() -> None:
    """Test ### marker not at line start gets \\n\\n prepended."""
    content = "### Section Header\nContent here"
    result = apply_section_marker_handling(content, is_at_line_start=False)
    assert result == "\n\n### Section Header\nContent here"


def test_apply_section_marker_handling_hr_marker_only() -> None:
    """Test standalone --- marker is stripped entirely."""
    content = "---"
    result = apply_section_marker_handling(content, is_at_line_start=True)
    assert result == ""


def test_apply_section_marker_handling_hr_marker_only_not_at_line_start() -> None:
    """Test standalone --- marker not at line start is stripped (no newlines added for empty)."""
    content = "---"
    result = apply_section_marker_handling(content, is_at_line_start=False)
    assert result == ""


def test_apply_section_marker_handling_hr_marker_with_content() -> None:
    """Test --- marker with following content strips marker and leading newlines."""
    content = "---\nActual content"
    result = apply_section_marker_handling(content, is_at_line_start=True)
    assert result == "Actual content"


def test_apply_section_marker_handling_hr_marker_with_content_not_at_line_start() -> (
    None
):
    """Test --- marker with content not at line start strips marker and prepends \\n\\n."""
    content = "---\nActual content"
    result = apply_section_marker_handling(content, is_at_line_start=False)
    assert result == "\n\nActual content"


def test_apply_section_marker_handling_hr_marker_strips_leading_newlines() -> None:
    """Test --- marker strips both marker and leading newlines from content."""
    content = "---\n\n\nContent after newlines"
    result = apply_section_marker_handling(content, is_at_line_start=True)
    assert result == "Content after newlines"


def test_apply_section_marker_handling_hr_with_leading_whitespace() -> None:
    """Test --- with leading whitespace is NOT treated as a section marker."""
    content = "  ---  "
    # Content doesn't start with --- due to leading whitespace, so returned unchanged
    result = apply_section_marker_handling(content, is_at_line_start=True)
    assert result == "  ---  "


def test_apply_section_marker_handling_triple_hash_empty_content() -> None:
    """Test that ### at start with no following content works correctly."""
    content = "###"
    result = apply_section_marker_handling(content, is_at_line_start=True)
    assert result == "###"
    result = apply_section_marker_handling(content, is_at_line_start=False)
    assert result == "\n\n###"


# Tests for convert_timestamp_to_artifacts_format
def test_convert_timestamp_to_artifacts_format() -> None:
    """Test conversion from YYmmdd_HHMMSS to YYYYmmddHHMMSS format."""
    assert convert_timestamp_to_artifacts_format("251227_143052") == "20251227143052"


def test_convert_timestamp_to_artifacts_format_different_date() -> None:
    """Test conversion with a different timestamp."""
    assert convert_timestamp_to_artifacts_format("240101_000000") == "20240101000000"


# Tests for create_artifacts_directory with timestamp parameter
def test_create_artifacts_directory_with_timestamp() -> None:
    """Test that pre-existing timestamp is used instead of generating new one."""
    project_name = "test-project-ts"
    workflow_name = "test-workflow"
    timestamp = "251227_143052"
    artifacts_dir = create_artifacts_directory(
        workflow_name, project_name, timestamp=timestamp
    )

    # Check that the directory uses the converted timestamp
    expected_suffix = "20251227143052"
    assert artifacts_dir.endswith(expected_suffix)

    # Verify format: ~/.gai/projects/<project>/artifacts/<workflow>/<timestamp>
    expanded_home = str(Path.home())
    expected_path = (
        f"{expanded_home}/.gai/projects/{project_name}"
        f"/artifacts/{workflow_name}/{expected_suffix}"
    )
    assert artifacts_dir == expected_path

    # Check directory exists
    assert Path(artifacts_dir).exists()

    # Cleanup
    import shutil

    project_dir = Path.home() / ".gai" / "projects" / project_name
    shutil.rmtree(project_dir)
