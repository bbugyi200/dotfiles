"""Tests for work workflow operations and status management."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from work.changespec import ChangeSpec, _get_status_color
from work.main import WorkWorkflow
from work.operations import (
    extract_changespec_text,
    get_available_workflows,
    update_to_changespec,
)
from work.status import _get_available_statuses


def test_workflow_name() -> None:
    """Test that workflow name is correct."""
    workflow = WorkWorkflow()
    assert workflow.name == "work"


def test_workflow_description() -> None:
    """Test that workflow description is correct."""
    workflow = WorkWorkflow()
    assert "ChangeSpecs" in workflow.description
    assert "project files" in workflow.description


def test_get_available_workflows_unstarted_with_test_targets() -> None:
    """Test that Unstarted with test targets returns new-failing-tests workflow."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="None",
        test_targets=["target1"],
        status="Unstarted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == ["new-failing-tests"]


def test_get_available_workflows_unstarted_without_test_targets() -> None:
    """Test that Unstarted without test targets returns new-ez-feature workflow."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="None",
        test_targets=None,
        status="Unstarted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == ["new-ez-feature"]


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
STATUS: Unstarted

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
        assert "STATUS: Unstarted" in text
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
STATUS: Unstarted
TEST TARGETS: None


NAME: Feature B
DESCRIPTION:
  Second feature
PARENT: None
CL: None
STATUS: TDD CL Created
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
        assert "TDD CL Created" in text
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
STATUS: Unstarted
TEST TARGETS: None
"""
        )
        project_file = f.name

    try:
        text = extract_changespec_text(project_file, "Nonexistent Feature")

        assert text is None
    finally:
        Path(project_file).unlink()


def test_get_status_color_unstarted() -> None:
    """Test that 'Unstarted' status has the correct color."""
    color = _get_status_color("Unstarted")
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
        status="Unstarted",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
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
        status="Unstarted",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
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


def test_get_available_statuses_excludes_current() -> None:
    """Test that _get_available_statuses excludes the current status."""
    current_status = "TDD CL Created"
    available = _get_available_statuses(current_status)
    assert current_status not in available
    assert "Blocked" not in available


def test_get_available_statuses_excludes_blocked() -> None:
    """Test that _get_available_statuses excludes 'Blocked' status."""
    current_status = "Unstarted"
    available = _get_available_statuses(current_status)
    assert "Blocked" not in available


def test_get_available_statuses_includes_others() -> None:
    """Test that _get_available_statuses includes other valid statuses."""
    current_status = "TDD CL Created"
    available = _get_available_statuses(current_status)
    # Should include some other statuses but not current or Blocked
    assert len(available) > 0
    assert all(s != current_status and s != "Blocked" for s in available)


def test_get_available_statuses_with_blocked_ez() -> None:
    """Test that _get_available_statuses works with 'Blocked' current status."""
    current_status = "Blocked"
    available = _get_available_statuses(current_status)
    assert current_status not in available
    assert "Blocked" not in available
    assert len(available) > 0


def test_get_available_statuses_with_blocked_tdd() -> None:
    """Test that _get_available_statuses works with 'Blocked' current status."""
    current_status = "Blocked"
    available = _get_available_statuses(current_status)
    assert current_status not in available
    assert "Blocked" not in available
    assert len(available) > 0


def test_get_status_color_fixing_tests() -> None:
    """Test that 'Fixing Tests...' status has the correct color."""
    color = _get_status_color("Fixing Tests...")
    assert color == "#87AFFF"


def test_get_status_color_pre_mailed() -> None:
    """Test that 'Pre-Mailed' status has the correct color."""
    color = _get_status_color("Pre-Mailed")
    assert color == "#87D700"


def test_get_status_color_mailed() -> None:
    """Test that 'Mailed' status has the correct color."""
    color = _get_status_color("Mailed")
    assert color == "#00D787"


def test_get_status_color_submitted() -> None:
    """Test that 'Submitted' status has the correct color."""
    color = _get_status_color("Submitted")
    assert color == "#00AF00"


def test_get_status_color_blocked() -> None:
    """Test that 'Blocked' status has the correct color."""
    color = _get_status_color("Blocked")
    assert color == "#D75F00"


def test_get_status_color_tdd_cl_created() -> None:
    """Test that 'TDD CL Created' status has the correct color."""
    color = _get_status_color("TDD CL Created")
    assert color == "#AF87FF"
