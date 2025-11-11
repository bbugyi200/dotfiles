"""Tests for work workflow operations and status management."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from work.changespec import ChangeSpec, _get_status_color
from work.main import WorkWorkflow
from work.operations import (
    extract_changespec_text,
    should_show_run_option,
    update_to_changespec,
)


def test_workflow_name() -> None:
    """Test that workflow name is correct."""
    workflow = WorkWorkflow()
    assert workflow.name == "work"


def test_workflow_description() -> None:
    """Test that workflow description is correct."""
    workflow = WorkWorkflow()
    assert "ChangeSpecs" in workflow.description
    assert "project files" in workflow.description


def test_should_show_run_option_unstarted_ez() -> None:
    """Test that run option is shown for Unstarted (EZ)."""
    changespec = ChangeSpec(
        name="cs1",
        description="Test",
        parent=None,
        cl=None,
        status="Unstarted (EZ)",
        test_targets=None,
        tap=None,
        file_path="/path/to/project.md",
        line_number=1,
    )
    assert should_show_run_option(changespec) is True


def test_should_show_run_option_unstarted_tdd() -> None:
    """Test that run option is shown for Unstarted (TDD)."""
    changespec = ChangeSpec(
        name="cs1",
        description="Test",
        parent=None,
        cl=None,
        status="Unstarted (TDD)",
        test_targets=["None"],
        tap=None,
        file_path="/path/to/project.md",
        line_number=1,
    )
    assert should_show_run_option(changespec) is True


def test_should_show_run_option_tdd_cl_created() -> None:
    """Test that run option is shown for TDD CL Created."""
    changespec = ChangeSpec(
        name="cs1",
        description="Test",
        parent=None,
        cl="12345",
        status="TDD CL Created",
        test_targets=["//some:test"],
        tap=None,
        file_path="/path/to/project.md",
        line_number=1,
    )
    assert should_show_run_option(changespec) is True


def test_should_show_run_option_ready_for_qa() -> None:
    """Test that run option is shown for Ready for QA."""
    changespec = ChangeSpec(
        name="cs1",
        description="Test",
        parent=None,
        cl="12345",
        status="Ready for QA",
        test_targets=None,
        tap=None,
        file_path="/path/to/project.md",
        line_number=1,
    )
    assert should_show_run_option(changespec) is True


def test_should_show_run_option_in_progress() -> None:
    """Test that run option is NOT shown for In Progress status."""
    changespec = ChangeSpec(
        name="cs1",
        description="Test",
        parent=None,
        cl=None,
        status="In Progress",
        test_targets=None,
        tap=None,
        file_path="/path/to/project.md",
        line_number=1,
    )
    assert should_show_run_option(changespec) is False


def test_should_show_run_option_with_test_targets() -> None:
    """Test that run option IS shown for Unstarted (TDD) with test targets."""
    changespec = ChangeSpec(
        name="cs1",
        description="Test",
        parent=None,
        cl=None,
        status="Unstarted (TDD)",
        test_targets=["//some:test"],
        tap=None,
        file_path="/path/to/project.md",
        line_number=1,
    )
    assert should_show_run_option(changespec) is True


def test_extract_changespec_text_basic() -> None:
    """Test extracting ChangeSpec text from a project file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """# Test Project

NAME: Test Feature
DESCRIPTION:
  A test feature
PARENT: None
CL: None
TEST TARGETS: None
STATUS: Unstarted (EZ)

---
"""
        )
        project_file = f.name

    try:
        text = extract_changespec_text(project_file, "Test Feature")

        assert text is not None
        assert "NAME: Test Feature" in text
        assert "DESCRIPTION:" in text
        assert "A test feature" in text
        assert "STATUS: Unstarted (EZ)" in text
    finally:
        Path(project_file).unlink()


def test_extract_changespec_text_multiple_changespecs() -> None:
    """Test extracting one ChangeSpec from a file with multiple."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """# Test Project

NAME: Feature A
DESCRIPTION:
  First feature
PARENT: None
CL: None
STATUS: Not Started
TEST TARGETS: None


NAME: Feature B
DESCRIPTION:
  Second feature
PARENT: None
CL: None
STATUS: In Progress
TEST TARGETS: //some:test

---
"""
        )
        project_file = f.name

    try:
        text = extract_changespec_text(project_file, "Feature B")

        assert text is not None
        assert "NAME: Feature B" in text
        assert "Second feature" in text
        assert "In Progress" in text
        # Should NOT contain Feature A content
        assert "Feature A" not in text
        assert "First feature" not in text
    finally:
        Path(project_file).unlink()


def test_extract_changespec_text_nonexistent() -> None:
    """Test extracting a nonexistent ChangeSpec returns None."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """# Test Project

NAME: Test Feature
DESCRIPTION:
  A test feature
PARENT: None
CL: None
STATUS: Not Started
TEST TARGETS: None
"""
        )
        project_file = f.name

    try:
        text = extract_changespec_text(project_file, "Nonexistent Feature")

        assert text is None
    finally:
        Path(project_file).unlink()


def test_get_status_color_unstarted_ez() -> None:
    """Test that 'Unstarted (EZ)' status has the correct color."""
    color = _get_status_color("Unstarted (EZ)")
    assert color == "#D7AF00"


def test_get_status_color_unstarted_tdd() -> None:
    """Test that 'Unstarted (TDD)' status has the correct color."""
    color = _get_status_color("Unstarted (TDD)")
    assert color == "#FFD700"


def test_get_status_color_creating_ez_cl() -> None:
    """Test that 'Creating EZ CL...' status has the correct color."""
    color = _get_status_color("Creating EZ CL...")
    assert color == "#87AFFF"


def test_get_status_color_running_tap_tests() -> None:
    """Test that 'Running TAP Tests' status has the correct color."""
    color = _get_status_color("Running TAP Tests")
    assert color == "#87FFAF"


def test_get_status_color_unknown() -> None:
    """Test that unknown status returns default color."""
    color = _get_status_color("Unknown Status")
    assert color == "#FFFFFF"


def test_update_to_changespec_with_parent() -> None:
    """Test that update_to_changespec uses PARENT field when set."""
    from unittest.mock import MagicMock

    changespec = ChangeSpec(
        name="test_feature",
        description="Test",
        parent="parent_cl_123",
        cl=None,
        status="Not Started",
        test_targets=None,
        tap=None,
        file_path="/path/to/project.md",
        line_number=1,
    )

    with patch("subprocess.run") as mock_run:
        with patch.dict(
            "os.environ",
            {"GOOG_CLOUD_DIR": "/tmp", "GOOG_SRC_DIR_BASE": "src"},
        ):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.isdir", return_value=True):
                    mock_run.return_value = MagicMock(returncode=0)
                    success, error = update_to_changespec(changespec)

                    assert success is True
                    assert error is None
                    # Verify bb_hg_update was called with parent value
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert args == ["bb_hg_update", "parent_cl_123"]


def test_update_to_changespec_without_parent() -> None:
    """Test that update_to_changespec uses p4head when PARENT is None."""
    from unittest.mock import MagicMock

    changespec = ChangeSpec(
        name="test_feature",
        description="Test",
        parent=None,
        cl=None,
        status="Not Started",
        test_targets=None,
        tap=None,
        file_path="/path/to/project.md",
        line_number=1,
    )

    with patch("subprocess.run") as mock_run:
        with patch.dict(
            "os.environ",
            {"GOOG_CLOUD_DIR": "/tmp", "GOOG_SRC_DIR_BASE": "src"},
        ):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.isdir", return_value=True):
                    mock_run.return_value = MagicMock(returncode=0)
                    success, error = update_to_changespec(changespec)

                    assert success is True
                    assert error is None
                    # Verify bb_hg_update was called with p4head
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert args == ["bb_hg_update", "p4head"]
