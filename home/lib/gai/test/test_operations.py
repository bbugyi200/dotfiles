"""Tests for work workflow operations and status management."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from status_state_machine import remove_workspace_suffix
from work.changespec import ChangeSpec, _get_status_color
from work.field_updates import (
    add_failing_test_targets,
    remove_failed_markers_from_test_targets,
)
from work.main import WorkWorkflow
from work.operations import (
    _get_workspace_suffix,
    _is_in_progress_status,
    get_available_workflows,
    get_workspace_directory,
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


def test_get_available_workflows_drafted() -> None:
    """Test that Drafted status returns no workflows."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Drafted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_mailed() -> None:
    """Test that Mailed status returns no workflows."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Mailed",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_changes_requested() -> None:
    """Test that Changes Requested status returns crs workflow."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Changes Requested",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == ["crs"]


def test_get_available_workflows_with_failed_test_targets() -> None:
    """Test that failing test targets trigger fix-tests workflow."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=["target1 (FAILED)"],
        status="Drafted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == ["fix-tests"]


def test_get_available_workflows_submitted_status() -> None:
    """Test that Submitted status returns no workflows."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Submitted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_status_color_changes_requested() -> None:
    """Test that 'Changes Requested' status has the correct color."""
    color = _get_status_color("Changes Requested")
    assert color == "#FFAF00"


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
        status="Drafted",
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
        status="Drafted",
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
    current_status = "Drafted"
    available = _get_available_statuses(current_status)
    assert current_status not in available


def test_get_available_statuses_includes_others() -> None:
    """Test that _get_available_statuses includes other valid statuses."""
    current_status = "Drafted"
    available = _get_available_statuses(current_status)
    # Should include some other statuses but not current
    assert len(available) > 0
    assert all(s != current_status for s in available)


def test_get_status_color_making_change_requests() -> None:
    """Test that 'Making Change Requests...' status has the correct color."""
    color = _get_status_color("Making Change Requests...")
    assert color == "#87AFFF"


def test_get_status_color_drafted() -> None:
    """Test that 'Drafted' status has the correct color."""
    color = _get_status_color("Drafted")
    assert color == "#87D700"


def test_get_status_color_mailed() -> None:
    """Test that 'Mailed' status has the correct color."""
    color = _get_status_color("Mailed")
    assert color == "#00D787"


def test_get_status_color_submitted() -> None:
    """Test that 'Submitted' status has the correct color."""
    color = _get_status_color("Submitted")
    assert color == "#00AF00"


def test_get_status_color_with_workspace_suffix() -> None:
    """Test that status colors work with workspace suffixes."""
    # Test various in-progress statuses with workspace suffixes
    assert _get_status_color("Running QA... (test_2)") == "#87AFFF"
    assert _get_status_color("Making Change Requests... (foo_10)") == "#87AFFF"
    assert _get_status_color("Making Change Requests... (cr_1)") == "#87AFFF"


# Workspace share tests


def test_get_workspace_suffix_with_suffix() -> None:
    """Test extracting workspace suffix from status."""
    suffix = _get_workspace_suffix("Running QA... (fig_3)")
    assert suffix == "fig_3"


def test_get_workspace_suffix_without_suffix() -> None:
    """Test that no suffix returns None."""
    suffix = _get_workspace_suffix("Running QA...")
    assert suffix is None


def test_get_workspace_suffix_with_different_project() -> None:
    """Test extracting workspace suffix with different project name."""
    suffix = _get_workspace_suffix("Fixing Tests... (myproject_42)")
    assert suffix == "myproject_42"


def test_remove_workspace_suffix_with_suffix() -> None:
    """Test removing workspace suffix from status."""
    status = remove_workspace_suffix("Running QA... (fig_3)")
    assert status == "Running QA..."


def test_remove_workspace_suffix_without_suffix() -> None:
    """Test that removing suffix with no suffix is a no-op."""
    status = remove_workspace_suffix("Running QA...")
    assert status == "Running QA..."


def test_remove_workspace_suffix_multiple_suffixes() -> None:
    """Test that only the suffix at the end is removed."""
    status = remove_workspace_suffix("Fixing Tests... (project_2)")
    assert status == "Fixing Tests..."


def test_is_in_progress_status_with_ellipsis() -> None:
    """Test that status ending with ... is in-progress."""
    assert _is_in_progress_status("Running QA...")
    assert _is_in_progress_status("Making Change Requests...")


def test_is_in_progress_status_with_ellipsis_and_suffix() -> None:
    """Test that status ending with ... and suffix is in-progress."""
    assert _is_in_progress_status("Running QA... (fig_3)")
    assert _is_in_progress_status("Making Change Requests... (project_5)")


def test_is_in_progress_status_without_ellipsis() -> None:
    """Test that status not ending with ... is not in-progress."""
    assert not _is_in_progress_status("Drafted")
    assert not _is_in_progress_status("Mailed")
    assert not _is_in_progress_status("Submitted")
    assert not _is_in_progress_status("Changes Requested")


def test_get_workspace_directory_no_in_progress() -> None:
    """Test that no in-progress changespecs returns main workspace."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="None",
        test_targets=None,
        status="Drafted",
        file_path="/tmp/test.gp",
        line_number=1,
        kickstart=None,
    )
    all_changespecs = [cs]

    with patch.dict(
        "os.environ",
        {"GOOG_CLOUD_DIR": "/cloud", "GOOG_SRC_DIR_BASE": "google3"},
    ):
        workspace_dir, workspace_suffix = get_workspace_directory(cs, all_changespecs)
        assert workspace_dir == "/cloud/test/google3"
        assert workspace_suffix is None


def test_get_workspace_directory_main_workspace_available() -> None:
    """Test that main workspace is used when available."""
    cs1 = ChangeSpec(
        name="Test1",
        description="Test1",
        parent="None",
        cl="None",
        test_targets=None,
        status="Drafted",
        file_path="/tmp/test.gp",
        line_number=1,
        kickstart=None,
    )
    cs2 = ChangeSpec(
        name="Test2",
        description="Test2",
        parent="None",
        cl="None",
        test_targets=None,
        status="Running QA... (test_3)",  # Using workspace share
        file_path="/tmp/test.gp",
        line_number=10,
        kickstart=None,
    )
    all_changespecs = [cs1, cs2]

    with patch.dict(
        "os.environ",
        {"GOOG_CLOUD_DIR": "/cloud", "GOOG_SRC_DIR_BASE": "google3"},
    ):
        workspace_dir, workspace_suffix = get_workspace_directory(cs1, all_changespecs)
        assert workspace_dir == "/cloud/test/google3"
        assert workspace_suffix is None


def test_get_workspace_directory_main_workspace_in_use() -> None:
    """Test that workspace share is used when main workspace is in use."""
    cs1 = ChangeSpec(
        name="Test1",
        description="Test1",
        parent="None",
        cl="None",
        test_targets=None,
        status="Running QA...",  # Using main workspace
        file_path="/tmp/test.gp",
        line_number=1,
        kickstart=None,
    )
    cs2 = ChangeSpec(
        name="Test2",
        description="Test2",
        parent="None",
        cl="None",
        test_targets=None,
        status="Drafted",
        file_path="/tmp/test.gp",
        line_number=10,
        kickstart=None,
    )
    all_changespecs = [cs1, cs2]

    with patch.dict(
        "os.environ",
        {"GOOG_CLOUD_DIR": "/cloud", "GOOG_SRC_DIR_BASE": "google3"},
    ):
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=True),
        ):
            workspace_dir, workspace_suffix = get_workspace_directory(
                cs2, all_changespecs
            )
            assert workspace_dir == "/cloud/test_2/google3"
            assert workspace_suffix == "test_2"


def test_update_to_changespec_with_revision() -> None:
    """Test that update_to_changespec uses provided revision when specified."""
    from unittest.mock import MagicMock

    changespec = ChangeSpec(
        name="test_feature",
        description="Test",
        parent="parent_cl_123",
        cl="cl_456",
        status="Drafted",
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
                    # Pass a specific revision
                    success, error = update_to_changespec(
                        changespec, revision="custom_revision"
                    )

                    assert success is True
                    assert error is None
                    # Verify bb_hg_update was called with custom revision
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert args == ["bb_hg_update", "custom_revision"]


def test_update_to_changespec_with_workspace_dir() -> None:
    """Test that update_to_changespec uses provided workspace_dir."""
    from unittest.mock import MagicMock

    changespec = ChangeSpec(
        name="test_feature",
        description="Test",
        parent="parent_cl_123",
        cl=None,
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
    )

    with patch("subprocess.run") as mock_run:
        with patch("os.path.exists", return_value=True):
            with patch("os.path.isdir", return_value=True):
                mock_run.return_value = MagicMock(returncode=0)
                # Pass a specific workspace directory
                success, error = update_to_changespec(
                    changespec, workspace_dir="/custom/workspace"
                )

                assert success is True
                assert error is None
                # Verify the cwd was set to the custom workspace
                assert mock_run.call_args[1]["cwd"] == "/custom/workspace"


def test_get_workspace_directory_finds_next_available() -> None:
    """Test that next available workspace share is found."""
    cs1 = ChangeSpec(
        name="Test1",
        description="Test1",
        parent="None",
        cl="None",
        test_targets=None,
        status="Running QA...",  # Using main workspace
        file_path="/tmp/test.gp",
        line_number=1,
        kickstart=None,
    )
    cs2 = ChangeSpec(
        name="Test2",
        description="Test2",
        parent="None",
        cl="None",
        test_targets=None,
        status="Making Change Requests... (test_2)",  # Using test_2
        file_path="/tmp/test.gp",
        line_number=10,
        kickstart=None,
    )
    cs3 = ChangeSpec(
        name="Test3",
        description="Test3",
        parent="None",
        cl="None",
        test_targets=None,
        status="Drafted",
        file_path="/tmp/test.gp",
        line_number=20,
        kickstart=None,
    )
    all_changespecs = [cs1, cs2, cs3]

    with patch.dict(
        "os.environ",
        {"GOOG_CLOUD_DIR": "/cloud", "GOOG_SRC_DIR_BASE": "google3"},
    ):
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=True),
        ):
            workspace_dir, workspace_suffix = get_workspace_directory(
                cs3, all_changespecs
            )
            assert workspace_dir == "/cloud/test_3/google3"
            assert workspace_suffix == "test_3"


# Tests for field_updates functions


def _create_project_file_with_targets(
    targets: list[str], status: str = "Drafted"
) -> str:
    """Create a temporary project file with test targets."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("# Test Project\n\n")
        f.write("NAME: Test Feature\n")
        f.write("DESCRIPTION:\n")
        f.write("  Test description\n")
        f.write("PARENT: None\n")
        f.write("CL: None\n")
        if targets:
            f.write("TEST TARGETS:\n")
            for target in targets:
                f.write(f"  {target}\n")
        f.write(f"STATUS: {status}\n")
        return f.name


def test_add_failing_test_targets_new_targets() -> None:
    """Test adding new failing test targets."""
    project_file = _create_project_file_with_targets([])
    try:
        success, error = add_failing_test_targets(
            project_file, "Test Feature", ["//foo:bar", "//baz:qux"]
        )
        assert success is True
        assert error is None

        with open(project_file) as f:
            content = f.read()

        assert "//foo:bar (FAILED)" in content
        assert "//baz:qux (FAILED)" in content
    finally:
        Path(project_file).unlink()


def test_add_failing_test_targets_marks_existing() -> None:
    """Test that existing targets are marked as FAILED."""
    project_file = _create_project_file_with_targets(["//foo:bar", "//baz:qux"])
    try:
        success, error = add_failing_test_targets(
            project_file, "Test Feature", ["//foo:bar"]
        )
        assert success is True
        assert error is None

        with open(project_file) as f:
            content = f.read()

        # foo:bar should be marked FAILED
        assert "//foo:bar (FAILED)" in content
        # baz:qux should remain unchanged
        assert "//baz:qux\n" in content
        assert "//baz:qux (FAILED)" not in content
    finally:
        Path(project_file).unlink()


def test_add_failing_test_targets_already_failed() -> None:
    """Test that already-FAILED targets remain FAILED."""
    project_file = _create_project_file_with_targets(["//foo:bar (FAILED)"])
    try:
        success, error = add_failing_test_targets(
            project_file, "Test Feature", ["//foo:bar"]
        )
        assert success is True
        assert error is None

        with open(project_file) as f:
            content = f.read()

        # Should still have exactly one (FAILED) marker
        assert content.count("//foo:bar (FAILED)") == 1
    finally:
        Path(project_file).unlink()


def test_remove_failed_markers_basic() -> None:
    """Test removing FAILED markers from test targets."""
    project_file = _create_project_file_with_targets(
        ["//foo:bar (FAILED)", "//baz:qux (FAILED)"]
    )
    try:
        success, error = remove_failed_markers_from_test_targets(
            project_file, "Test Feature"
        )
        assert success is True
        assert error is None

        with open(project_file) as f:
            content = f.read()

        # FAILED markers should be removed
        assert "(FAILED)" not in content
        assert "//foo:bar" in content
        assert "//baz:qux" in content
    finally:
        Path(project_file).unlink()


def test_remove_failed_markers_mixed() -> None:
    """Test removing FAILED markers when some targets are not failed."""
    project_file = _create_project_file_with_targets(
        ["//foo:bar (FAILED)", "//baz:qux"]
    )
    try:
        success, error = remove_failed_markers_from_test_targets(
            project_file, "Test Feature"
        )
        assert success is True
        assert error is None

        with open(project_file) as f:
            content = f.read()

        # FAILED markers should be removed, other targets unchanged
        assert "(FAILED)" not in content
        assert "//foo:bar" in content
        assert "//baz:qux" in content
    finally:
        Path(project_file).unlink()


def test_remove_failed_markers_no_markers() -> None:
    """Test that remove_failed_markers succeeds when no markers present."""
    project_file = _create_project_file_with_targets(["//foo:bar", "//baz:qux"])
    try:
        success, error = remove_failed_markers_from_test_targets(
            project_file, "Test Feature"
        )
        assert success is True
        assert error is None

        with open(project_file) as f:
            content = f.read()

        # Content should be unchanged
        assert "//foo:bar" in content
        assert "//baz:qux" in content
    finally:
        Path(project_file).unlink()


def test_remove_failed_markers_no_targets() -> None:
    """Test that remove_failed_markers succeeds when no test targets exist."""
    project_file = _create_project_file_with_targets([])
    try:
        success, error = remove_failed_markers_from_test_targets(
            project_file, "Test Feature"
        )
        assert success is True
        assert error is None
    finally:
        Path(project_file).unlink()
