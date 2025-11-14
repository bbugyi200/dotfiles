"""Tests for the work workflow filtering functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from work.changespec import ChangeSpec
from work.filters import filter_changespecs, validate_filters


def test_validate_filters_valid_status() -> None:
    """Test that valid status filters are accepted."""
    is_valid, error_msg = validate_filters(
        status_filters=["Unstarted", "TDD CL Created"], project_filters=None
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
            status="Unstarted",
            test_targets=None,
            kickstart=None,
            file_path="/path/to/project1.md",
            line_number=1,
        ),
        ChangeSpec(
            name="cs2",
            description="Test 2",
            parent=None,
            cl=None,
            status="Creating TDD CL...",
            test_targets=None,
            kickstart=None,
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
            kickstart=None,
            file_path="/path/to/project2.md",
            line_number=1,
        ),
    ]

    filtered = filter_changespecs(
        changespecs,
        status_filters=["Unstarted", "Blocked"],
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
                status="Unstarted",
                test_targets=None,
                kickstart=None,
                file_path=project1_path,
                line_number=1,
            ),
            ChangeSpec(
                name="cs2",
                description="Test 2",
                parent=None,
                cl=None,
                status="Creating TDD CL...",
                test_targets=None,
                kickstart=None,
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
                kickstart=None,
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
                status="Unstarted",
                test_targets=None,
                kickstart=None,
                file_path=project1_path,
                line_number=1,
            ),
            ChangeSpec(
                name="cs2",
                description="Test 2",
                parent=None,
                cl=None,
                status="Creating TDD CL...",
                test_targets=None,
                kickstart=None,
                file_path=project1_path,
                line_number=10,
            ),
            ChangeSpec(
                name="cs3",
                description="Test 3",
                parent=None,
                cl=None,
                status="Unstarted",
                test_targets=None,
                kickstart=None,
                file_path=project2_path,
                line_number=1,
            ),
        ]

        with patch("pathlib.Path.home", return_value=Path(tmpdir)):
            # Filter by "Unstarted" status AND project1
            filtered = filter_changespecs(
                changespecs,
                status_filters=["Unstarted"],
                project_filters=["project1"],
            )

            # Should only return cs1 (Unstarted AND in project1)
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
            status="Unstarted",
            test_targets=None,
            kickstart=None,
            file_path="/path/to/project1.md",
            line_number=1,
        ),
        ChangeSpec(
            name="cs2",
            description="Test 2",
            parent=None,
            cl=None,
            status="Creating TDD CL...",
            test_targets=None,
            kickstart=None,
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
            kickstart=None,
            file_path="/path/to/project2.md",
            line_number=1,
        ),
    ]

    filtered = filter_changespecs(
        changespecs,
        status_filters=["Unstarted", "Creating TDD CL..."],
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
            status="Unstarted",
            test_targets=None,
            kickstart=None,
            file_path="/path/to/project1.md",
            line_number=1,
        ),
        ChangeSpec(
            name="cs2",
            description="Test 2",
            parent=None,
            cl=None,
            status="Creating TDD CL...",
            test_targets=None,
            kickstart=None,
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
