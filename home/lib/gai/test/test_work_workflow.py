"""Tests for the work workflow filtering functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from work.changespec import ChangeSpec, _get_status_color
from work.filters import filter_changespecs, validate_filters
from work.main import WorkWorkflow
from work.operations import (
    _parse_bug_id_from_project_file,
    _update_cl_field,
    extract_changespec_text,
    should_show_run_option,
    update_to_changespec,
)


def test_validate_filters_valid_status() -> None:
    """Test that valid status filters are accepted."""
    is_valid, error_msg = validate_filters(
        status_filters=["Unstarted (TDD)", "In Progress"], project_filters=None
    )
    assert is_valid is True
    assert error_msg is None


def test_validate_filters_invalid_status() -> None:
    """Test that invalid status filters are rejected."""
    is_valid, error_msg = validate_filters(
        status_filters=["Invalid Status"], project_filters=None
    )
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
            is_valid, error_msg = validate_filters(
                status_filters=None, project_filters=["test_project"]
            )
            assert is_valid is True
            assert error_msg is None


def test_validate_filters_nonexistent_project() -> None:
    """Test that nonexistent project filters are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        projects_dir = Path(tmpdir) / ".gai" / "projects"
        projects_dir.mkdir(parents=True)

        with patch("os.path.expanduser", return_value=str(projects_dir)):
            is_valid, error_msg = validate_filters(
                status_filters=None, project_filters=["nonexistent"]
            )
            assert is_valid is False
            assert error_msg is not None
            assert "Project file not found" in error_msg


def test_validate_filters_no_filters() -> None:
    """Test that no filters is valid."""
    is_valid, error_msg = validate_filters(status_filters=None, project_filters=None)
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
            status="Unstarted (TDD)",
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
            status="Blocked (TDD)",
            test_targets=None,
            file_path="/path/to/project2.md",
            line_number=1,
        ),
    ]

    filtered = filter_changespecs(
        changespecs,
        status_filters=["Unstarted (TDD)", "Blocked (TDD)"],
        project_filters=None,
    )

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
                status="Unstarted (TDD)",
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
                status="Blocked (TDD)",
                test_targets=None,
                file_path=project1_path,
                line_number=10,
            ),
        ]

        with patch("pathlib.Path.home", return_value=Path(tmpdir)):
            filtered = filter_changespecs(
                changespecs, status_filters=None, project_filters=["project1"]
            )

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
            filtered = filter_changespecs(
                changespecs,
                status_filters=["Not Started"],
                project_filters=["project1"],
            )

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

    filtered = filter_changespecs(
        changespecs,
        status_filters=["Not Started", "In Progress"],
        project_filters=None,
    )

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

    filtered = filter_changespecs(
        changespecs, status_filters=None, project_filters=None
    )

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


def test_should_show_run_option_unstarted_ez() -> None:
    """Test that run option is shown for Unstarted (EZ)."""
    changespec = ChangeSpec(
        name="cs1",
        description="Test",
        parent=None,
        cl=None,
        status="Unstarted (EZ)",
        test_targets=None,
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
    from unittest.mock import MagicMock, patch

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
                    success, error = update_to_changespec(changespec)

                    assert success is True
                    assert error is None
                    # Verify bb_hg_update was called with parent value
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert args == ["bb_hg_update", "parent_cl_123"]


def test_update_to_changespec_without_parent() -> None:
    """Test that update_to_changespec uses p4head when PARENT is None."""
    from unittest.mock import MagicMock, patch

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
                    success, error = update_to_changespec(changespec)

                    assert success is True
                    assert error is None
                    # Verify bb_hg_update was called with p4head
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert args == ["bb_hg_update", "p4head"]


def test_parse_bug_id_from_project_file_plain_id() -> None:
    """Test parsing plain bug ID from project file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("BUG: 12345\n\n\nNAME: test\n")
        project_file = f.name

    try:
        bug_id = _parse_bug_id_from_project_file(project_file)
        assert bug_id == "12345"
    finally:
        Path(project_file).unlink()


def test_parse_bug_id_from_project_file_url_http() -> None:
    """Test parsing bug ID from HTTP URL format."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("BUG: http://b/450606779\n\n\nNAME: test\n")
        project_file = f.name

    try:
        bug_id = _parse_bug_id_from_project_file(project_file)
        assert bug_id == "450606779"
    finally:
        Path(project_file).unlink()


def test_parse_bug_id_from_project_file_url_https() -> None:
    """Test parsing bug ID from HTTPS URL format."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("BUG: https://b/987654321\n\n\nNAME: test\n")
        project_file = f.name

    try:
        bug_id = _parse_bug_id_from_project_file(project_file)
        assert bug_id == "987654321"
    finally:
        Path(project_file).unlink()


def test_parse_bug_id_from_project_file_not_found() -> None:
    """Test parsing when BUG field is not present."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("NAME: test\nDESCRIPTION: test\n")
        project_file = f.name

    try:
        bug_id = _parse_bug_id_from_project_file(project_file)
        assert bug_id is None
    finally:
        Path(project_file).unlink()


def test_update_cl_field_success() -> None:
    """Test successfully updating CL field in a ChangeSpec."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """BUG: 12345


NAME: test_feature
DESCRIPTION:
  A test feature
PARENT: None
CL: None
STATUS: Unstarted (EZ)
"""
        )
        project_file = f.name

    try:
        success, error = _update_cl_field(project_file, "test_feature", "54321")
        assert success is True
        assert error is None

        # Verify the file was updated
        with open(project_file) as f:
            content = f.read()
        assert "CL: 54321" in content
        assert "CL: None" not in content
    finally:
        Path(project_file).unlink()


def test_update_cl_field_changespec_not_found() -> None:
    """Test updating CL field when ChangeSpec doesn't exist."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """BUG: 12345


NAME: test_feature
DESCRIPTION:
  A test feature
PARENT: None
CL: None
STATUS: Unstarted (EZ)
"""
        )
        project_file = f.name

    try:
        success, error = _update_cl_field(project_file, "nonexistent_feature", "54321")
        assert success is False
        assert error is not None
        assert "Could not find ChangeSpec" in error
    finally:
        Path(project_file).unlink()


def test_update_cl_field_multiple_changespecs() -> None:
    """Test updating CL field in the correct ChangeSpec when multiple exist."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """BUG: 12345


NAME: feature_a
DESCRIPTION:
  First feature
PARENT: None
CL: None
STATUS: Unstarted (EZ)


NAME: feature_b
DESCRIPTION:
  Second feature
PARENT: None
CL: None
STATUS: Unstarted (TDD)
"""
        )
        project_file = f.name

    try:
        success, error = _update_cl_field(project_file, "feature_b", "99999")
        assert success is True
        assert error is None

        # Verify only feature_b was updated
        with open(project_file) as f:
            lines = f.readlines()

        # Find lines with CL fields
        cl_lines = [line for line in lines if line.startswith("CL:")]
        assert len(cl_lines) == 2
        assert "CL: None\n" in cl_lines  # feature_a unchanged
        assert "CL: 99999\n" in cl_lines  # feature_b updated
    finally:
        Path(project_file).unlink()
