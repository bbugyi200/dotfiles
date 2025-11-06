"""Tests for hitl_review_workflow module."""

import os
from pathlib import Path

import pytest
from hitl_review_workflow import (
    _change_to_project_directory,
    _extract_bug_id,
    _extract_cl_id,
    _find_changespecs_for_review,
    _format_changespec_for_display,
    _get_test_output_file_path,
    _has_test_output,
    _parse_project_spec,
    _update_changespec_status,
)
from main import _create_parser


def test_parse_project_spec_basic() -> None:
    """Test parsing a basic ProjectSpec file."""
    content = """BUG: 12345


NAME: test_project_add_feature
DESCRIPTION:
  Add a new feature

  This is the feature description.
PARENT: None
CL: None
STATUS: Not Started


NAME: test_project_update_docs
DESCRIPTION:
  Update documentation

  This updates the docs.
PARENT: test_project_add_feature
CL: cl/123456
STATUS: Pre-Mailed
"""
    bug_id, changespecs = _parse_project_spec(content)

    assert bug_id == "12345"
    assert len(changespecs) == 2

    # Check first ChangeSpec
    assert changespecs[0]["NAME"] == "test_project_add_feature"
    assert "Add a new feature" in changespecs[0]["DESCRIPTION"]
    assert changespecs[0]["PARENT"] == "None"
    assert changespecs[0]["CL"] == "None"
    assert changespecs[0]["STATUS"] == "Not Started"

    # Check second ChangeSpec
    assert changespecs[1]["NAME"] == "test_project_update_docs"
    assert "Update documentation" in changespecs[1]["DESCRIPTION"]
    assert changespecs[1]["PARENT"] == "test_project_add_feature"
    assert changespecs[1]["CL"] == "cl/123456"
    assert changespecs[1]["STATUS"] == "Pre-Mailed"


def test_parse_project_spec_with_test_targets() -> None:
    """Test parsing a ProjectSpec with TEST TARGETS field."""
    content = """BUG: 12345


NAME: test_project_with_tests
DESCRIPTION:
  Feature with tests

  This has test targets.
PARENT: None
CL: None
TEST TARGETS: //path/to:test1 //path/to:test2
STATUS: TDD CL Created
"""
    bug_id, changespecs = _parse_project_spec(content)

    assert bug_id == "12345"
    assert len(changespecs) == 1
    assert changespecs[0]["NAME"] == "test_project_with_tests"
    assert changespecs[0]["TEST TARGETS"] == "//path/to:test1 //path/to:test2"
    assert changespecs[0]["STATUS"] == "TDD CL Created"


def test_parse_project_spec_no_bug() -> None:
    """Test parsing a ProjectSpec without BUG field."""
    content = """NAME: test_project_no_bug
DESCRIPTION:
  Feature without bug

  This has no bug ID.
PARENT: None
CL: None
STATUS: Not Started
"""
    bug_id, changespecs = _parse_project_spec(content)

    assert bug_id is None
    assert len(changespecs) == 1


def test_update_changespec_status(tmp_path: Path) -> None:
    """Test updating ChangeSpec STATUS in a project file."""
    project_file = tmp_path / "test_project.md"
    content = """BUG: 12345


NAME: test_cs1
DESCRIPTION:
  First change

  Description here.
PARENT: None
CL: None
STATUS: Not Started


NAME: test_cs2
DESCRIPTION:
  Second change

  Description here.
PARENT: test_cs1
CL: None
STATUS: In Progress
"""
    project_file.write_text(content)

    # Update the first ChangeSpec
    _update_changespec_status(str(project_file), "test_cs1", "Pre-Mailed")

    # Read and verify
    updated_content = project_file.read_text()
    bug_id, changespecs = _parse_project_spec(updated_content)

    assert changespecs[0]["STATUS"] == "Pre-Mailed"
    assert changespecs[1]["STATUS"] == "In Progress"  # Unchanged


def test_find_changespecs_for_review(tmp_path: Path) -> None:
    """Test finding ChangeSpecs that need review."""
    # Create test project files
    project1 = tmp_path / "project1.md"
    project1.write_text(
        """BUG: 1


NAME: p1_cs1
DESCRIPTION:
  Change 1

  Desc
PARENT: None
CL: None
STATUS: Pre-Mailed


NAME: p1_cs2
DESCRIPTION:
  Change 2

  Desc
PARENT: None
CL: None
STATUS: Not Started
"""
    )

    project2 = tmp_path / "project2.md"
    project2.write_text(
        """BUG: 2


NAME: p2_cs1
DESCRIPTION:
  Change 1

  Desc
PARENT: None
CL: None
STATUS: Failed to Fix Tests


NAME: p2_cs2
DESCRIPTION:
  Change 2

  Desc
PARENT: None
CL: None
STATUS: Failed to Create CL
"""
    )

    # Find ChangeSpecs for review
    project_files = [str(project1), str(project2)]
    changespecs_for_review = _find_changespecs_for_review(project_files)

    # Should find 3 ChangeSpecs (Pre-Mailed, Failed to Fix Tests, Failed to Create CL)
    assert len(changespecs_for_review) == 3

    # Verify ordering: Pre-Mailed first, then Failed to Fix Tests, then Failed to Create CL
    assert changespecs_for_review[0][1]["NAME"] == "p1_cs1"  # Pre-Mailed
    assert changespecs_for_review[0][2] == "Pre-Mailed"

    assert changespecs_for_review[1][1]["NAME"] == "p2_cs1"  # Failed to Fix Tests
    assert changespecs_for_review[1][2] == "Failed to Fix Tests"

    assert changespecs_for_review[2][1]["NAME"] == "p2_cs2"  # Failed to Create CL
    assert changespecs_for_review[2][2] == "Failed to Create CL"


def test_find_changespecs_for_review_no_flagged() -> None:
    """Test finding ChangeSpecs when none need review."""
    # Test with empty list
    changespecs_for_review = _find_changespecs_for_review([])
    assert len(changespecs_for_review) == 0


def test_create_parser_has_review_command() -> None:
    """Test that parser has the top-level 'review' command."""
    parser = _create_parser()

    # Parse the review command
    args = parser.parse_args(["review"])
    assert args.command == "review"


def test_create_parser_run_review_still_works() -> None:
    """Test that 'run review' command still works for CL review."""
    parser = _create_parser()

    # Parse the 'run review' command
    args = parser.parse_args(["run", "review"])
    assert args.command == "run"
    assert args.workflow == "review"


def test_format_changespec_for_display_single_line_fields() -> None:
    """Test formatting a ChangeSpec with single-line fields."""
    cs = {
        "NAME": "test_project_add_feature",
        "PARENT": "None",
        "CL": "None",
        "STATUS": "Not Started",
    }

    result = _format_changespec_for_display(cs)

    # Check that all fields are present
    assert "NAME" in result
    assert "test_project_add_feature" in result
    assert "PARENT" in result
    assert "None" in result
    assert "CL" in result
    assert "STATUS" in result
    assert "Not Started" in result


def test_format_changespec_for_display_multiline_fields() -> None:
    """Test formatting a ChangeSpec with multi-line fields."""
    cs = {
        "NAME": "test_project_add_feature",
        "DESCRIPTION": "Add a new feature\n\nThis is the feature description.",
        "PARENT": "None",
        "CL": "None",
        "STATUS": "Pre-Mailed",
    }

    result = _format_changespec_for_display(cs)

    # Check that all fields are present
    assert "NAME" in result
    assert "test_project_add_feature" in result
    assert "DESCRIPTION" in result
    assert "Add a new feature" in result
    assert "This is the feature description." in result
    assert "PARENT" in result
    assert "STATUS" in result
    assert "Pre-Mailed" in result

    # Check that multi-line descriptions have proper indentation
    assert (
        "  Add a new feature" in result or "  This is the feature description" in result
    )


def test_get_test_output_file_path() -> None:
    """Test getting the test output file path."""
    project_file = "/home/user/.gai/projects/test_project.md"
    cs_name = "test_project_add_feature"

    result = _get_test_output_file_path(project_file, cs_name)

    assert result.endswith(".test_outputs/test_project_add_feature.txt")
    assert "/home/user/.gai/projects/.test_outputs/" in result


def test_get_test_output_file_path_sanitizes_name() -> None:
    """Test that test output file path sanitizes ChangeSpec names."""
    project_file = "/home/user/.gai/projects/test_project.md"
    cs_name = "test/project with spaces"

    result = _get_test_output_file_path(project_file, cs_name)

    # Should replace "/" and spaces with "_"
    assert "test_project_with_spaces.txt" in result


def test_has_test_output_when_exists(tmp_path: Path) -> None:
    """Test _has_test_output returns True when test output exists."""
    project_file = tmp_path / "test_project.md"
    project_file.write_text("NAME: test_cs\nSTATUS: Failed to Fix Tests")

    # Create test output directory and file
    test_outputs_dir = tmp_path / ".test_outputs"
    test_outputs_dir.mkdir()
    test_output_file = test_outputs_dir / "test_cs.txt"
    test_output_file.write_text("Test output content")

    cs = {"NAME": "test_cs"}

    result = _has_test_output(str(project_file), cs)
    assert result is True


def test_has_test_output_when_not_exists(tmp_path: Path) -> None:
    """Test _has_test_output returns False when test output doesn't exist."""
    project_file = tmp_path / "test_project.md"
    project_file.write_text("NAME: test_cs\nSTATUS: Not Started")

    cs = {"NAME": "test_cs"}

    result = _has_test_output(str(project_file), cs)
    assert result is False


def test_change_to_project_directory_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test successfully changing to project directory."""
    # Create the directory structure
    project_name = "test_project"
    cloud_dir = tmp_path / "cloud"
    src_base = "src"
    project_dir = cloud_dir / project_name / src_base
    project_dir.mkdir(parents=True)

    # Set environment variables
    monkeypatch.setenv("GOOG_CLOUD_DIR", str(cloud_dir))
    monkeypatch.setenv("GOOG_SRC_DIR_BASE", src_base)

    # Create project file
    project_file = tmp_path / "projects" / f"{project_name}.md"
    project_file.parent.mkdir(parents=True, exist_ok=True)
    project_file.write_text("NAME: test\nSTATUS: Not Started")

    # Call the function
    result = _change_to_project_directory(str(project_file))

    assert result is True
    assert os.getcwd() == str(project_dir)


def test_change_to_project_directory_missing_env_vars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test when environment variables are not set."""
    # Unset environment variables
    monkeypatch.delenv("GOOG_CLOUD_DIR", raising=False)
    monkeypatch.delenv("GOOG_SRC_DIR_BASE", raising=False)

    project_file = tmp_path / "test_project.md"
    project_file.write_text("NAME: test\nSTATUS: Not Started")

    result = _change_to_project_directory(str(project_file))

    assert result is False


def test_change_to_project_directory_dir_not_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test when the project directory doesn't exist."""
    # Set environment variables but don't create the directory
    cloud_dir = tmp_path / "cloud"
    src_base = "src"

    monkeypatch.setenv("GOOG_CLOUD_DIR", str(cloud_dir))
    monkeypatch.setenv("GOOG_SRC_DIR_BASE", src_base)

    project_file = tmp_path / "nonexistent_project.md"
    project_file.write_text("NAME: test\nSTATUS: Not Started")

    result = _change_to_project_directory(str(project_file))

    assert result is False


def test_extract_bug_id_plain_format() -> None:
    """Test extracting bug ID from plain format."""
    assert _extract_bug_id("12345") == "12345"
    assert _extract_bug_id("  12345  ") == "12345"


def test_extract_bug_id_http_url_format() -> None:
    """Test extracting bug ID from HTTP URL format."""
    assert _extract_bug_id("http://b/12345") == "12345"
    assert _extract_bug_id("  http://b/12345  ") == "12345"


def test_extract_bug_id_https_url_format() -> None:
    """Test extracting bug ID from HTTPS URL format."""
    assert _extract_bug_id("https://b/12345") == "12345"
    assert _extract_bug_id("  https://b/12345  ") == "12345"


def test_extract_cl_id_plain_format() -> None:
    """Test extracting CL ID from plain format."""
    assert _extract_cl_id("12345") == "12345"
    assert _extract_cl_id("  12345  ") == "12345"


def test_extract_cl_id_legacy_format() -> None:
    """Test extracting CL ID from legacy cl/ format."""
    assert _extract_cl_id("cl/12345") == "12345"
    assert _extract_cl_id("  cl/12345  ") == "12345"


def test_extract_cl_id_http_url_format() -> None:
    """Test extracting CL ID from HTTP URL format."""
    assert _extract_cl_id("http://cl/12345") == "12345"
    assert _extract_cl_id("  http://cl/12345  ") == "12345"


def test_extract_cl_id_https_url_format() -> None:
    """Test extracting CL ID from HTTPS URL format."""
    assert _extract_cl_id("https://cl/12345") == "12345"
    assert _extract_cl_id("  https://cl/12345  ") == "12345"
