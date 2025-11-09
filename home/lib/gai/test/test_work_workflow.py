"""Tests for the work workflow filtering functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from work.changespec import ChangeSpec, _get_status_color
from work.main import WorkWorkflow


def test_validate_filters_valid_status() -> None:
    """Test that valid status filters are accepted."""
    workflow = WorkWorkflow(status_filters=["Not Started", "In Progress"])
    is_valid, error_msg = workflow._validate_filters()
    assert is_valid is True
    assert error_msg is None


def test_validate_filters_invalid_status() -> None:
    """Test that invalid status filters are rejected."""
    workflow = WorkWorkflow(status_filters=["Invalid Status"])
    is_valid, error_msg = workflow._validate_filters()
    assert is_valid is False
    assert error_msg is not None
    assert "Invalid status" in error_msg
    assert "Invalid Status" in error_msg


def test_validate_filters_valid_project_with_temp_dir() -> None:
    """Test that valid project filters are accepted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock project file
        projects_dir = Path(tmpdir) / ".gai" / "projects"
        projects_dir.mkdir(parents=True)
        project_file = projects_dir / "test_project.md"
        project_file.write_text("# Test Project\n")

        with patch("os.path.expanduser", return_value=str(projects_dir)):
            workflow = WorkWorkflow(project_filters=["test_project"])
            is_valid, error_msg = workflow._validate_filters()
            assert is_valid is True
            assert error_msg is None


def test_validate_filters_nonexistent_project() -> None:
    """Test that nonexistent project filters are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        projects_dir = Path(tmpdir) / ".gai" / "projects"
        projects_dir.mkdir(parents=True)

        with patch("os.path.expanduser", return_value=str(projects_dir)):
            workflow = WorkWorkflow(project_filters=["nonexistent"])
            is_valid, error_msg = workflow._validate_filters()
            assert is_valid is False
            assert error_msg is not None
            assert "Project file not found" in error_msg


def test_validate_filters_no_filters() -> None:
    """Test that no filters is valid."""
    workflow = WorkWorkflow()
    is_valid, error_msg = workflow._validate_filters()
    assert is_valid is True
    assert error_msg is None


def test_filter_changespecs_by_status() -> None:
    """Test filtering changespecs by status."""
    changespecs = [
        ChangeSpec(
            name="cs1",
            description="Test 1",
            parent=None,
            cl=None,
            status="Not Started",
            test_targets=None,
            file_path="/path/to/project1.md",
            line_number=1,
        ),
        ChangeSpec(
            name="cs2",
            description="Test 2",
            parent=None,
            cl=None,
            status="In Progress",
            test_targets=None,
            file_path="/path/to/project1.md",
            line_number=10,
        ),
        ChangeSpec(
            name="cs3",
            description="Test 3",
            parent=None,
            cl=None,
            status="Blocked",
            test_targets=None,
            file_path="/path/to/project2.md",
            line_number=1,
        ),
    ]

    workflow = WorkWorkflow(status_filters=["Not Started", "Blocked"])
    filtered = workflow._filter_changespecs(changespecs)

    assert len(filtered) == 2
    assert filtered[0].name == "cs1"
    assert filtered[1].name == "cs3"


def test_filter_changespecs_by_project() -> None:
    """Test filtering changespecs by project file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        projects_dir = Path(tmpdir) / ".gai" / "projects"
        projects_dir.mkdir(parents=True)

        project1_path = str(projects_dir / "project1.md")
        project2_path = str(projects_dir / "project2.md")

        changespecs = [
            ChangeSpec(
                name="cs1",
                description="Test 1",
                parent=None,
                cl=None,
                status="Not Started",
                test_targets=None,
                file_path=project1_path,
                line_number=1,
            ),
            ChangeSpec(
                name="cs2",
                description="Test 2",
                parent=None,
                cl=None,
                status="In Progress",
                test_targets=None,
                file_path=project2_path,
                line_number=1,
            ),
            ChangeSpec(
                name="cs3",
                description="Test 3",
                parent=None,
                cl=None,
                status="Blocked",
                test_targets=None,
                file_path=project1_path,
                line_number=10,
            ),
        ]

        with patch("pathlib.Path.home", return_value=Path(tmpdir)):
            workflow = WorkWorkflow(project_filters=["project1"])
            filtered = workflow._filter_changespecs(changespecs)

            assert len(filtered) == 2
            assert filtered[0].name == "cs1"
            assert filtered[1].name == "cs3"


def test_filter_changespecs_by_status_and_project() -> None:
    """Test filtering changespecs by both status and project (AND logic)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        projects_dir = Path(tmpdir) / ".gai" / "projects"
        projects_dir.mkdir(parents=True)

        project1_path = str(projects_dir / "project1.md")
        project2_path = str(projects_dir / "project2.md")

        changespecs = [
            ChangeSpec(
                name="cs1",
                description="Test 1",
                parent=None,
                cl=None,
                status="Not Started",
                test_targets=None,
                file_path=project1_path,
                line_number=1,
            ),
            ChangeSpec(
                name="cs2",
                description="Test 2",
                parent=None,
                cl=None,
                status="In Progress",
                test_targets=None,
                file_path=project1_path,
                line_number=10,
            ),
            ChangeSpec(
                name="cs3",
                description="Test 3",
                parent=None,
                cl=None,
                status="Not Started",
                test_targets=None,
                file_path=project2_path,
                line_number=1,
            ),
        ]

        with patch("pathlib.Path.home", return_value=Path(tmpdir)):
            # Filter by "Not Started" status AND project1
            workflow = WorkWorkflow(
                status_filters=["Not Started"], project_filters=["project1"]
            )
            filtered = workflow._filter_changespecs(changespecs)

            # Should only return cs1 (Not Started AND in project1)
            assert len(filtered) == 1
            assert filtered[0].name == "cs1"


def test_filter_changespecs_multiple_statuses() -> None:
    """Test filtering with multiple status values (OR logic)."""
    changespecs = [
        ChangeSpec(
            name="cs1",
            description="Test 1",
            parent=None,
            cl=None,
            status="Not Started",
            test_targets=None,
            file_path="/path/to/project1.md",
            line_number=1,
        ),
        ChangeSpec(
            name="cs2",
            description="Test 2",
            parent=None,
            cl=None,
            status="In Progress",
            test_targets=None,
            file_path="/path/to/project1.md",
            line_number=10,
        ),
        ChangeSpec(
            name="cs3",
            description="Test 3",
            parent=None,
            cl=None,
            status="Blocked",
            test_targets=None,
            file_path="/path/to/project2.md",
            line_number=1,
        ),
    ]

    workflow = WorkWorkflow(status_filters=["Not Started", "In Progress"])
    filtered = workflow._filter_changespecs(changespecs)

    assert len(filtered) == 2
    assert filtered[0].name == "cs1"
    assert filtered[1].name == "cs2"


def test_filter_changespecs_no_filters() -> None:
    """Test that no filters returns all changespecs."""
    changespecs = [
        ChangeSpec(
            name="cs1",
            description="Test 1",
            parent=None,
            cl=None,
            status="Not Started",
            test_targets=None,
            file_path="/path/to/project1.md",
            line_number=1,
        ),
        ChangeSpec(
            name="cs2",
            description="Test 2",
            parent=None,
            cl=None,
            status="In Progress",
            test_targets=None,
            file_path="/path/to/project1.md",
            line_number=10,
        ),
    ]

    workflow = WorkWorkflow()
    filtered = workflow._filter_changespecs(changespecs)

    assert len(filtered) == 2
    assert filtered[0].name == "cs1"
    assert filtered[1].name == "cs2"


def test_workflow_name() -> None:
    """Test that workflow name is correct."""
    workflow = WorkWorkflow()
    assert workflow.name == "work"


def test_workflow_description() -> None:
    """Test that workflow description is correct."""
    workflow = WorkWorkflow()
    assert "ChangeSpecs" in workflow.description
    assert "project files" in workflow.description


def test_should_show_run_option_not_started_no_targets() -> None:
    """Test that run option is shown for Not Started with no test targets."""
    workflow = WorkWorkflow()
    changespec = ChangeSpec(
        name="cs1",
        description="Test",
        parent=None,
        cl=None,
        status="Not Started",
        test_targets=None,
        file_path="/path/to/project.md",
        line_number=1,
    )
    assert workflow._should_show_run_option(changespec) is True


def test_should_show_run_option_not_started_none_targets() -> None:
    """Test that run option is shown for Not Started with 'None' test targets."""
    workflow = WorkWorkflow()
    changespec = ChangeSpec(
        name="cs1",
        description="Test",
        parent=None,
        cl=None,
        status="Not Started",
        test_targets=["None"],
        file_path="/path/to/project.md",
        line_number=1,
    )
    assert workflow._should_show_run_option(changespec) is True


def test_should_show_run_option_in_progress() -> None:
    """Test that run option is NOT shown for In Progress status."""
    workflow = WorkWorkflow()
    changespec = ChangeSpec(
        name="cs1",
        description="Test",
        parent=None,
        cl=None,
        status="In Progress",
        test_targets=None,
        file_path="/path/to/project.md",
        line_number=1,
    )
    assert workflow._should_show_run_option(changespec) is False


def test_should_show_run_option_with_test_targets() -> None:
    """Test that run option is NOT shown when test targets are present."""
    workflow = WorkWorkflow()
    changespec = ChangeSpec(
        name="cs1",
        description="Test",
        parent=None,
        cl=None,
        status="Not Started",
        test_targets=["//some:test"],
        file_path="/path/to/project.md",
        line_number=1,
    )
    assert workflow._should_show_run_option(changespec) is False


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
STATUS: Not Started
TEST TARGETS: None

---
"""
        )
        project_file = f.name

    try:
        workflow = WorkWorkflow()
        text = workflow._extract_changespec_text(project_file, "Test Feature")

        assert text is not None
        assert "NAME: Test Feature" in text
        assert "DESCRIPTION:" in text
        assert "A test feature" in text
        assert "STATUS: Not Started" in text
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
        workflow = WorkWorkflow()
        text = workflow._extract_changespec_text(project_file, "Feature B")

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
        workflow = WorkWorkflow()
        text = workflow._extract_changespec_text(project_file, "Nonexistent Feature")

        assert text is None
    finally:
        Path(project_file).unlink()


def test_get_status_color_not_started() -> None:
    """Test that 'Not Started' status has the correct color."""
    color = _get_status_color("Not Started")
    assert color == "#D7AF00"


def test_get_status_color_creating_ez_cl() -> None:
    """Test that 'Creating EZ CL...' status has the correct color."""
    color = _get_status_color("Creating EZ CL...")
    assert color == "#FFFFFF"  # Default color


def test_get_status_color_running_tap_tests() -> None:
    """Test that 'Running TAP Tests' status has the correct color."""
    color = _get_status_color("Running TAP Tests")
    assert color == "#FFFFFF"  # Default color


def test_get_status_color_unknown() -> None:
    """Test that unknown status returns default color."""
    color = _get_status_color("Unknown Status")
    assert color == "#FFFFFF"


def test_update_to_changespec_with_parent() -> None:
    """Test that _update_to_changespec uses PARENT field when set."""
    from unittest.mock import MagicMock, patch

    workflow = WorkWorkflow()
    changespec = ChangeSpec(
        name="test_feature",
        description="Test",
        parent="parent_cl_123",
        cl=None,
        status="Not Started",
        test_targets=None,
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
                    success, error = workflow._update_to_changespec(changespec)

                    assert success is True
                    assert error is None
                    # Verify bb_hg_update was called with parent value
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert args == ["bb_hg_update", "parent_cl_123"]


def test_update_to_changespec_without_parent() -> None:
    """Test that _update_to_changespec uses p4head when PARENT is None."""
    from unittest.mock import MagicMock, patch

    workflow = WorkWorkflow()
    changespec = ChangeSpec(
        name="test_feature",
        description="Test",
        parent=None,
        cl=None,
        status="Not Started",
        test_targets=None,
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
                    success, error = workflow._update_to_changespec(changespec)

                    assert success is True
                    assert error is None
                    # Verify bb_hg_update was called with p4head
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert args == ["bb_hg_update", "p4head"]
