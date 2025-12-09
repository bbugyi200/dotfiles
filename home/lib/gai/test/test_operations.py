"""Tests for work workflow operations and status management."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from status_state_machine import remove_workspace_suffix
from work.changespec import ChangeSpec, _get_status_color
from work.main import WorkWorkflow
from work.operations import (
    _get_workspace_suffix,
    _is_in_progress_status,
    extract_changespec_text,
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


def test_get_available_workflows_tdd_cl_created() -> None:
    """Test that TDD CL Created status returns new-tdd-feature workflow."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=["target1"],
        status="TDD CL Created",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == ["new-tdd-feature"]


def test_get_available_workflows_needs_qa() -> None:
    """Test that Needs QA status returns qa workflow."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Needs QA",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == ["qa"]


def test_get_available_workflows_pre_mailed() -> None:
    """Test that Pre-Mailed status returns no workflows (QA moved to Needs QA)."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Pre-Mailed",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_mailed() -> None:
    """Test that Mailed status returns no workflows (QA moved to Needs QA)."""
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


def test_get_available_workflows_failing_tests_status() -> None:
    """Test that 'Failing Tests' status returns fix-tests workflow."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=["target1 (FAILED)"],
        status="Failing Tests",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == ["fix-tests"]


def test_get_available_workflows_needs_qa_no_fix_tests() -> None:
    """Test that Needs QA with failed tests does NOT return fix-tests (only Failing Tests status does)."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=["target1 (FAILED)"],
        status="Needs QA",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    # fix-tests is only available for "Failing Tests" status
    assert workflows == ["qa"]


def test_get_available_workflows_blocked_status() -> None:
    """Test that Blocked status returns no workflows."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="None",
        test_targets=None,
        status="Blocked",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


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


def test_get_status_color_with_workspace_suffix() -> None:
    """Test that status colors work with workspace suffixes."""
    # Test various in-progress statuses with workspace suffixes
    assert _get_status_color("Creating EZ CL... (fig_3)") == "#87AFFF"
    assert _get_status_color("Creating TDD CL... (project_5)") == "#5F87FF"
    assert _get_status_color("Running QA... (test_2)") == "#87AFFF"
    assert _get_status_color("Finishing TDD CL... (myproj_42)") == "#5F87FF"
    assert _get_status_color("Fixing Tests... (foo_10)") == "#87AFFF"


# Workspace share tests


def test_get_workspace_suffix_with_suffix() -> None:
    """Test extracting workspace suffix from status."""
    suffix = _get_workspace_suffix("Creating EZ CL... (fig_3)")
    assert suffix == "fig_3"


def test_get_workspace_suffix_without_suffix() -> None:
    """Test that no suffix returns None."""
    suffix = _get_workspace_suffix("Creating EZ CL...")
    assert suffix is None


def test_get_workspace_suffix_with_different_project() -> None:
    """Test extracting workspace suffix with different project name."""
    suffix = _get_workspace_suffix("Finishing TDD CL... (myproject_42)")
    assert suffix == "myproject_42"


def test_remove_workspace_suffix_with_suffix() -> None:
    """Test removing workspace suffix from status."""
    status = remove_workspace_suffix("Creating EZ CL... (fig_3)")
    assert status == "Creating EZ CL..."


def test_remove_workspace_suffix_without_suffix() -> None:
    """Test that removing suffix with no suffix is a no-op."""
    status = remove_workspace_suffix("Creating EZ CL...")
    assert status == "Creating EZ CL..."


def test_remove_workspace_suffix_multiple_suffixes() -> None:
    """Test that only the suffix at the end is removed."""
    status = remove_workspace_suffix("Finishing TDD CL... (project_2)")
    assert status == "Finishing TDD CL..."


def test_is_in_progress_status_with_ellipsis() -> None:
    """Test that status ending with ... is in-progress."""
    assert _is_in_progress_status("Creating EZ CL...")
    assert _is_in_progress_status("Creating TDD CL...")
    assert _is_in_progress_status("Running QA...")
    assert _is_in_progress_status("Finishing TDD CL...")
    assert _is_in_progress_status("Fixing Tests...")


def test_is_in_progress_status_with_ellipsis_and_suffix() -> None:
    """Test that status ending with ... and suffix is in-progress."""
    assert _is_in_progress_status("Creating EZ CL... (fig_3)")
    assert _is_in_progress_status("Finishing TDD CL... (project_5)")


def test_is_in_progress_status_without_ellipsis() -> None:
    """Test that status not ending with ... is not in-progress."""
    assert not _is_in_progress_status("Unstarted")
    assert not _is_in_progress_status("TDD CL Created")
    assert not _is_in_progress_status("Pre-Mailed")
    assert not _is_in_progress_status("Mailed")
    assert not _is_in_progress_status("Submitted")


def test_get_workspace_directory_no_in_progress() -> None:
    """Test that no in-progress changespecs returns main workspace."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="None",
        test_targets=None,
        status="Unstarted",
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
        status="Unstarted",
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
        status="Creating EZ CL... (test_3)",  # Using workspace share
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
        status="Creating EZ CL...",  # Using main workspace
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
        status="Unstarted",
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
        status="Pre-Mailed",
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
        status="Unstarted",
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


def test_extract_changespec_text_with_section_header() -> None:
    """Test extracting ChangeSpec that appears after a section header."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """# Test Project

## Section 1

NAME: Feature A
DESCRIPTION:
  First feature
PARENT: None
CL: None
STATUS: Unstarted
TEST TARGETS: None
"""
        )
        project_file = f.name

    try:
        text = extract_changespec_text(project_file, "Feature A")

        assert text is not None
        assert "NAME: Feature A" in text
        assert "First feature" in text
    finally:
        Path(project_file).unlink()


def test_get_workspace_directory_finds_next_available() -> None:
    """Test that next available workspace share is found."""
    cs1 = ChangeSpec(
        name="Test1",
        description="Test1",
        parent="None",
        cl="None",
        test_targets=None,
        status="Creating EZ CL...",  # Using main workspace
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
        status="Finishing TDD CL... (test_2)",  # Using test_2
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
        status="Unstarted",
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
