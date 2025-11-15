"""Tests for gai.shared_utils module."""

import os
import string
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from shared_utils import (
    _has_uncommitted_changes,
    add_postmortem_to_log,
    add_research_to_log,
    copy_design_docs_locally,
    create_artifacts_directory,
    ensure_str_content,
    finalize_gai_log,
    finalize_workflow_log,
    generate_workflow_tag,
    initialize_gai_log,
    initialize_tests_log,
    initialize_workflow_log,
    run_bam_command,
    run_shell_command,
    run_shell_command_with_input,
    safe_hg_amend,
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


def test_run_shell_command_with_input_success() -> None:
    """Test shell command with input text."""
    result = run_shell_command_with_input("cat", "test input", capture_output=True)
    assert result.returncode == 0
    assert result.stdout == "test input"


def test_create_artifacts_directory() -> None:
    """Test that artifacts directory is created with proper format."""
    # Use explicit project name to avoid dependency on workspace_name command
    project_name = "test-project"
    workflow_name = "test-workflow"
    artifacts_dir = create_artifacts_directory(workflow_name, project_name)

    # Check format: ~/.gai/projects/<project>/<workflow>/YYYYMMDDHHMMSS
    expanded_home = str(Path.home())
    expected_prefix = f"{expanded_home}/.gai/projects/{project_name}/{workflow_name}/"
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


@patch("shared_utils.run_shell_command")
def test__has_uncommitted_changes_true(mock_run: MagicMock) -> None:
    """Test that uncommitted changes are detected."""
    mock_result = MagicMock()
    mock_result.stdout = "diff --git a/file.txt b/file.txt"
    mock_run.return_value = mock_result

    assert _has_uncommitted_changes() is True
    mock_run.assert_called_once_with("hg diff", capture_output=True)


@patch("shared_utils.run_shell_command")
def test__has_uncommitted_changes_false(mock_run: MagicMock) -> None:
    """Test that no uncommitted changes returns False."""
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_run.return_value = mock_result

    assert _has_uncommitted_changes() is False
    mock_run.assert_called_once_with("hg diff", capture_output=True)


@patch("shared_utils.run_shell_command")
def test__has_uncommitted_changes_exception(mock_run: MagicMock) -> None:
    """Test that exceptions during hg diff check are handled gracefully."""
    mock_run.side_effect = Exception("hg command not found")

    # Should return False and not raise exception
    assert _has_uncommitted_changes() is False


def test_initialize_gai_log() -> None:
    """Test that gai.md log is initialized correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        initialize_gai_log(tmpdir, "fix-tests", "ABC")

        log_file = os.path.join(tmpdir, "gai.md")
        assert os.path.exists(log_file)

        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "GAI Workflow Log - fix-tests (ABC)" in content
        assert "Started:" in content
        assert "Artifacts Directory:" in content
        assert tmpdir in content


def test_finalize_gai_log() -> None:
    """Test that gai.md log is finalized correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize first
        initialize_gai_log(tmpdir, "fix-tests", "XYZ")

        # Finalize with success
        finalize_gai_log(tmpdir, "fix-tests", "XYZ", success=True)

        log_file = os.path.join(tmpdir, "gai.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "Workflow Completed" in content
        assert "SUCCESS" in content
        assert "fix-tests" in content
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


def test_initialize_workflow_log() -> None:
    """Test that workflow log.md is initialized correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        initialize_workflow_log(tmpdir, "fix-tests", "GHI")

        log_file = os.path.join(tmpdir, "log.md")
        assert os.path.exists(log_file)

        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "Fix-Tests Workflow Log (GHI)" in content
        assert "Started:" in content
        assert "Artifacts Directory:" in content


def test_initialize_tests_log() -> None:
    """Test that tests.md log is initialized correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        initialize_tests_log(tmpdir, "fix-tests", "JKL")

        tests_file = os.path.join(tmpdir, "tests.md")
        assert os.path.exists(tests_file)

        with open(tests_file, encoding="utf-8") as f:
            content = f.read()

        assert "Fix-Tests Tests Log (JKL)" in content
        assert "Started:" in content
        assert "This log contains only test output" in content


def test_add_postmortem_to_log() -> None:
    """Test adding postmortem analysis to workflow log."""
    with tempfile.TemporaryDirectory() as tmpdir:
        initialize_workflow_log(tmpdir, "fix-tests", "MNO")

        postmortem_content = "Analysis of test failures:\n- Issue 1\n- Issue 2"
        add_postmortem_to_log(tmpdir, 1, postmortem_content)

        log_file = os.path.join(tmpdir, "log.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "Iteration Postmortem" in content
        assert "Analysis of test failures" in content
        assert "Issue 1" in content


def test_add_postmortem_to_log_empty_content() -> None:
    """Test that empty postmortem content is handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        initialize_workflow_log(tmpdir, "fix-tests", "PQR")

        # This should not raise an exception
        add_postmortem_to_log(tmpdir, 1, "")

        log_file = os.path.join(tmpdir, "log.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        # Should not contain postmortem section
        assert "Iteration Postmortem" not in content


def test_add_research_to_log() -> None:
    """Test adding research results to workflow log."""
    with tempfile.TemporaryDirectory() as tmpdir:
        initialize_workflow_log(tmpdir, "fix-tests", "STU")

        research_results = {
            "cl_scope": {
                "title": "CL Scope Analysis",
                "content": "Research finding 1",
            },
            "similar_tests": {
                "title": "Similar Tests",
                "content": "Research finding 2",
            },
        }
        add_research_to_log(tmpdir, 1, research_results)

        log_file = os.path.join(tmpdir, "log.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "Research Findings" in content
        assert "CL Scope Analysis" in content
        assert "Research finding 1" in content
        assert "Similar Tests" in content
        assert "Research finding 2" in content


def test_add_research_to_log_empty_results() -> None:
    """Test that empty research results are handled gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        initialize_workflow_log(tmpdir, "fix-tests", "VWX")

        # This should not raise an exception
        add_research_to_log(tmpdir, 1, {})

        log_file = os.path.join(tmpdir, "log.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        # Should not contain research section
        assert "Research Findings" not in content


def test_add_test_output_to_log_meaningful() -> None:
    """Test adding meaningful test output to logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from shared_utils import add_test_output_to_log

        initialize_workflow_log(tmpdir, "fix-tests", "YZA")
        initialize_tests_log(tmpdir, "fix-tests", "YZA")

        test_output = "Test failed: AssertionError on line 42"
        add_test_output_to_log(
            tmpdir, iteration=1, test_output=test_output, test_output_is_meaningful=True
        )

        # Check workflow log
        log_file = os.path.join(tmpdir, "log.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "Iteration 1" in content
        assert "Test Output" in content
        assert "AssertionError on line 42" in content

        # Check tests log
        tests_file = os.path.join(tmpdir, "tests.md")
        with open(tests_file, encoding="utf-8") as f:
            tests_content = f.read()

        assert "Iteration 1" in tests_content
        assert "Test Output" in tests_content
        assert "AssertionError on line 42" in tests_content


def test_add_test_output_to_log_not_meaningful_with_match() -> None:
    """Test adding non-meaningful test output with matched iteration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from shared_utils import add_test_output_to_log

        initialize_workflow_log(tmpdir, "fix-tests", "BCD")
        initialize_tests_log(tmpdir, "fix-tests", "BCD")

        add_test_output_to_log(
            tmpdir,
            iteration=2,
            test_output_is_meaningful=False,
            matched_iteration=1,
        )

        log_file = os.path.join(tmpdir, "log.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "Iteration 2" in content
        assert "same as iteration 1" in content


def test_add_test_output_to_log_not_meaningful_without_match() -> None:
    """Test adding non-meaningful test output without matched iteration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from shared_utils import add_test_output_to_log

        initialize_workflow_log(tmpdir, "fix-tests", "EFG")
        initialize_tests_log(tmpdir, "fix-tests", "EFG")

        add_test_output_to_log(
            tmpdir, iteration=3, test_output_is_meaningful=False, matched_iteration=None
        )

        log_file = os.path.join(tmpdir, "log.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "Iteration 3" in content
        assert "No meaningful change to test output" in content


@patch("shared_utils._has_uncommitted_changes")
def test_safe_hg_amend_no_changes(mock_has_changes: MagicMock) -> None:
    """Test that safe_hg_amend returns True when no changes exist."""
    mock_has_changes.return_value = False

    result = safe_hg_amend("Test commit message")
    assert result is True
    mock_has_changes.assert_called_once()


@patch("shared_utils.run_shell_command")
@patch("shared_utils._has_uncommitted_changes")
def test_safe_hg_amend_success(
    mock_has_changes: MagicMock, mock_run_cmd: MagicMock
) -> None:
    """Test successful hg amend operation."""
    mock_has_changes.return_value = True
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run_cmd.return_value = mock_result

    result = safe_hg_amend("Test commit")
    assert result is True


@patch("shared_utils.run_shell_command")
@patch("shared_utils._has_uncommitted_changes")
def test_safe_hg_amend_with_unamend(
    mock_has_changes: MagicMock, mock_run_cmd: MagicMock
) -> None:
    """Test hg amend with unamend first."""
    mock_has_changes.return_value = True
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run_cmd.return_value = mock_result

    result = safe_hg_amend("Test commit", use_unamend_first=True)
    assert result is True
    assert mock_run_cmd.call_count == 2  # unamend + amend


@patch("shared_utils.run_shell_command")
@patch("shared_utils._has_uncommitted_changes")
def test_safe_hg_amend_unamend_fails(
    mock_has_changes: MagicMock, mock_run_cmd: MagicMock
) -> None:
    """Test that amend fails when unamend fails."""
    mock_has_changes.return_value = True
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "unamend failed"
    mock_run_cmd.return_value = mock_result

    result = safe_hg_amend("Test commit", use_unamend_first=True)
    assert result is False
    mock_run_cmd.assert_called_once()  # Only unamend was called


@patch("shared_utils.run_shell_command")
@patch("shared_utils._has_uncommitted_changes")
def test_safe_hg_amend_amend_fails(
    mock_has_changes: MagicMock, mock_run_cmd: MagicMock
) -> None:
    """Test that function returns False when amend fails."""
    mock_has_changes.return_value = True
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "amend failed"
    mock_run_cmd.return_value = mock_result

    result = safe_hg_amend("Test commit")
    assert result is False


@patch("shared_utils.run_shell_command")
@patch("shared_utils._has_uncommitted_changes")
def test_safe_hg_amend_exception(
    mock_has_changes: MagicMock, mock_run_cmd: MagicMock
) -> None:
    """Test that exceptions are handled gracefully."""
    mock_has_changes.return_value = True
    mock_run_cmd.side_effect = Exception("Command failed")

    result = safe_hg_amend("Test commit")
    assert result is False


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


def test_finalize_workflow_log() -> None:
    """Test finalizing the workflow log."""
    with tempfile.TemporaryDirectory() as tmpdir:
        initialize_workflow_log(tmpdir, "fix-tests", "HIJ")

        # Finalize with success
        finalize_workflow_log(tmpdir, "fix-tests", "HIJ", success=True)

        log_file = os.path.join(tmpdir, "log.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "Workflow Complete" in content
        assert "SUCCESS" in content


def test_finalize_workflow_log_failure() -> None:
    """Test finalizing the workflow log with failure status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        initialize_workflow_log(tmpdir, "add-tests", "KLM")

        # Finalize with failure
        finalize_workflow_log(tmpdir, "add-tests", "KLM", success=False)

        log_file = os.path.join(tmpdir, "log.md")
        with open(log_file, encoding="utf-8") as f:
            content = f.read()

        assert "Workflow Complete" in content
        assert "FAILED" in content


def test_copy_design_docs_locally_basic() -> None:
    """Test copying design docs from source directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a source directory with some design docs
        source_dir = os.path.join(tmpdir, "source")
        os.makedirs(source_dir)

        # Create some test files
        with open(os.path.join(source_dir, "design1.md"), "w") as f:
            f.write("# Design 1")
        with open(os.path.join(source_dir, "notes.txt"), "w") as f:
            f.write("Some notes")
        with open(os.path.join(source_dir, "ignore.py"), "w") as f:
            f.write("# Should be ignored")

        # Change to tmpdir so bb/gai/context is created there
        original_dir = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Call the function
            result = copy_design_docs_locally([source_dir])

            # Check that files were copied
            assert result is not None
            assert result == "bb/gai/context"
            assert os.path.exists(
                os.path.join(tmpdir, "bb", "gai", "context", "design1.md")
            )
            assert os.path.exists(
                os.path.join(tmpdir, "bb", "gai", "context", "notes.txt")
            )
            assert not os.path.exists(
                os.path.join(tmpdir, "bb", "gai", "context", "ignore.py")
            )
        finally:
            os.chdir(original_dir)


def test_copy_design_docs_locally_no_files() -> None:
    """Test copying design docs when no files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create an empty source directory
        source_dir = os.path.join(tmpdir, "source")
        os.makedirs(source_dir)

        original_dir = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Call the function
            result = copy_design_docs_locally([source_dir])

            # Check that no directory was created
            assert result is None
        finally:
            os.chdir(original_dir)


def test_copy_design_docs_locally_multiple_sources() -> None:
    """Test copying design docs from multiple source directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple source directories
        source_dir1 = os.path.join(tmpdir, "source1")
        source_dir2 = os.path.join(tmpdir, "source2")
        os.makedirs(source_dir1)
        os.makedirs(source_dir2)

        # Create test files in different directories
        with open(os.path.join(source_dir1, "design1.md"), "w") as f:
            f.write("# Design 1")
        with open(os.path.join(source_dir2, "design2.md"), "w") as f:
            f.write("# Design 2")

        original_dir = os.getcwd()
        try:
            os.chdir(tmpdir)

            # Call the function with multiple sources
            result = copy_design_docs_locally([source_dir1, source_dir2])

            # Check that files from both directories were copied
            assert result is not None
            assert os.path.exists(
                os.path.join(tmpdir, "bb", "gai", "context", "design1.md")
            )
            assert os.path.exists(
                os.path.join(tmpdir, "bb", "gai", "context", "design2.md")
            )
        finally:
            os.chdir(original_dir)
