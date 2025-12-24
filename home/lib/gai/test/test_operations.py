"""Tests for work workflow operations and status management."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from running_field import (
    _WorkspaceClaim,
    claim_workspace,
    get_claimed_workspaces,
    get_first_available_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from running_field import (
    get_workspace_directory as get_workspace_dir,
)
from work.changespec import ChangeSpec, HookEntry, HookStatusLine, _get_status_color
from work.main import WorkWorkflow
from work.operations import (
    get_available_workflows,
    get_workspace_directory,
    update_to_changespec,
)
from work.status import _get_available_statuses


def _make_hook(
    command: str,
    history_entry_num: int = 1,
    timestamp: str | None = None,
    status: str | None = None,
    duration: str | None = None,
) -> HookEntry:
    """Helper function to create a HookEntry with a status line."""
    if timestamp is None and status is None:
        return HookEntry(command=command)
    status_line = HookStatusLine(
        history_entry_num=history_entry_num,
        timestamp=timestamp or "",
        status=status or "",
        duration=duration,
    )
    return HookEntry(command=command, status_lines=[status_line])


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
    """Test that failing test target hooks trigger fix-hook and fix-tests workflows."""
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
        hooks=[
            _make_hook(command="bb_rabbit_test //target1", status="FAILED"),
        ],
    )
    workflows = get_available_workflows(cs)
    # fix-hook is available for any failing hook, fix-tests for failing test target hooks
    assert workflows == ["fix-hook", "fix-tests"]


def test_get_available_workflows_with_non_test_target_failed_hook() -> None:
    """Test that failing non-test hooks trigger only fix-hook workflow."""
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
        hooks=[
            _make_hook(command="flake8 src", status="FAILED"),
        ],
    )
    workflows = get_available_workflows(cs)
    # fix-hook is available for any failing hook, but fix-tests only for test targets
    assert workflows == ["fix-hook"]


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

    with patch("work.operations.get_workspace_dir_from_project") as mock_get_ws:
        mock_get_ws.return_value = "/tmp/project/src"
        with patch("subprocess.run") as mock_run:
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

    with patch("work.operations.get_workspace_dir_from_project") as mock_get_ws:
        mock_get_ws.return_value = "/tmp/project/src"
        with patch("subprocess.run") as mock_run:
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


def test_get_available_statuses_excludes_transient() -> None:
    """Test that _get_available_statuses excludes transient statuses with '...'"""
    available = _get_available_statuses("Drafted")
    # Should not include any status ending with "..."
    assert all(not s.endswith("...") for s in available)


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


def test_update_to_changespec_with_revision() -> None:
    """Test that update_to_changespec uses provided revision when specified."""
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

    with patch("work.operations.get_workspace_dir_from_project") as mock_get_ws:
        mock_get_ws.return_value = "/tmp/project/src"
        with patch("subprocess.run") as mock_run:
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


# RUNNING field tests


def _create_project_file_with_running(
    running_claims: list[_WorkspaceClaim] | None = None,
    has_bug_field: bool = False,
) -> str:
    """Create a temporary project file with optional RUNNING field."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("# Test Project\n\n")
        if has_bug_field:
            f.write("BUG: b/12345\n")
        if running_claims:
            f.write("RUNNING:\n")
            for claim in running_claims:
                f.write(claim.to_line() + "\n")
        f.write("NAME: Test Feature\n")
        f.write("DESCRIPTION:\n")
        f.write("  Test description\n")
        f.write("PARENT: None\n")
        f.write("CL: None\n")
        f.write("STATUS: Drafted\n")
        return f.name


def test_workspace_claim_to_line() -> None:
    """Test _WorkspaceClaim.to_line formatting."""
    claim = _WorkspaceClaim(workspace_num=1, workflow="crs", cl_name="my_feature")
    assert claim.to_line() == "  #1 | crs | my_feature"


def test_workspace_claim_to_line_no_cl_name() -> None:
    """Test _WorkspaceClaim.to_line without cl_name."""
    claim = _WorkspaceClaim(workspace_num=3, workflow="qa", cl_name=None)
    assert claim.to_line() == "  #3 | qa | "


def test_workspace_claim_from_line_valid() -> None:
    """Test parsing a valid RUNNING field line."""
    claim = _WorkspaceClaim.from_line("  #2 | fix-tests | my_change")
    assert claim is not None
    assert claim.workspace_num == 2
    assert claim.workflow == "fix-tests"
    assert claim.cl_name == "my_change"


def test_workspace_claim_from_line_no_cl_name() -> None:
    """Test parsing a RUNNING field line without cl_name."""
    claim = _WorkspaceClaim.from_line("  #1 | run | ")
    assert claim is not None
    assert claim.workspace_num == 1
    assert claim.workflow == "run"
    assert claim.cl_name is None


def test_workspace_claim_from_line_invalid() -> None:
    """Test parsing an invalid line returns None."""
    assert _WorkspaceClaim.from_line("not a valid line") is None
    assert _WorkspaceClaim.from_line("NAME: Test") is None


def test_get_claimed_workspaces_empty() -> None:
    """Test getting claims from file with no RUNNING field."""
    project_file = _create_project_file_with_running()
    try:
        claims = get_claimed_workspaces(project_file)
        assert claims == []
    finally:
        Path(project_file).unlink()


def test_get_claimed_workspaces_single() -> None:
    """Test getting single workspace claim."""
    project_file = _create_project_file_with_running(
        running_claims=[_WorkspaceClaim(1, "crs", "feature")]
    )
    try:
        claims = get_claimed_workspaces(project_file)
        assert len(claims) == 1
        assert claims[0].workspace_num == 1
        assert claims[0].workflow == "crs"
        assert claims[0].cl_name == "feature"
    finally:
        Path(project_file).unlink()


def test_get_claimed_workspaces_multiple() -> None:
    """Test getting multiple workspace claims."""
    project_file = _create_project_file_with_running(
        running_claims=[
            _WorkspaceClaim(1, "crs", "feature1"),
            _WorkspaceClaim(3, "qa", "feature2"),
        ]
    )
    try:
        claims = get_claimed_workspaces(project_file)
        assert len(claims) == 2
        assert claims[0].workspace_num == 1
        assert claims[1].workspace_num == 3
    finally:
        Path(project_file).unlink()


def test_claim_workspace_new_running_field() -> None:
    """Test claiming a workspace when RUNNING field doesn't exist."""
    project_file = _create_project_file_with_running(has_bug_field=True)
    try:
        success = claim_workspace(project_file, 1, "crs", "my_feature")
        assert success is True

        with open(project_file) as f:
            content = f.read()

        assert "RUNNING:" in content
        assert "#1 | crs | my_feature" in content
    finally:
        Path(project_file).unlink()


def test_claim_workspace_existing_running_field() -> None:
    """Test claiming a workspace when RUNNING field already exists."""
    project_file = _create_project_file_with_running(
        running_claims=[_WorkspaceClaim(1, "crs", "existing")]
    )
    try:
        success = claim_workspace(project_file, 2, "qa", "new_feature")
        assert success is True

        claims = get_claimed_workspaces(project_file)
        assert len(claims) == 2
        workspace_nums = {c.workspace_num for c in claims}
        assert workspace_nums == {1, 2}
    finally:
        Path(project_file).unlink()


def test_release_workspace_single() -> None:
    """Test releasing the only workspace claim."""
    project_file = _create_project_file_with_running(
        running_claims=[_WorkspaceClaim(1, "crs", "feature")]
    )
    try:
        success = release_workspace(project_file, 1)
        assert success is True

        with open(project_file) as f:
            content = f.read()

        # RUNNING field should be removed entirely
        assert "RUNNING:" not in content
    finally:
        Path(project_file).unlink()


def test_release_workspace_one_of_multiple() -> None:
    """Test releasing one of multiple workspace claims."""
    project_file = _create_project_file_with_running(
        running_claims=[
            _WorkspaceClaim(1, "crs", "feature1"),
            _WorkspaceClaim(2, "qa", "feature2"),
        ]
    )
    try:
        success = release_workspace(project_file, 1)
        assert success is True

        claims = get_claimed_workspaces(project_file)
        assert len(claims) == 1
        assert claims[0].workspace_num == 2
    finally:
        Path(project_file).unlink()


def test_release_workspace_with_workflow_filter() -> None:
    """Test releasing workspace with workflow filter."""
    project_file = _create_project_file_with_running(
        running_claims=[
            _WorkspaceClaim(1, "crs", "feature1"),
            _WorkspaceClaim(1, "run", "feature2"),
        ]
    )
    try:
        # Should only release the "crs" claim
        success = release_workspace(project_file, 1, workflow="crs")
        assert success is True

        claims = get_claimed_workspaces(project_file)
        assert len(claims) == 1
        assert claims[0].workflow == "run"
    finally:
        Path(project_file).unlink()


def test_get_first_available_workspace_main_available() -> None:
    """Test that main workspace is returned when available."""
    project_file = _create_project_file_with_running()
    try:
        workspace_num = get_first_available_workspace(project_file, "test")
        assert workspace_num == 1
    finally:
        Path(project_file).unlink()


def test_get_first_available_workspace_main_claimed() -> None:
    """Test that next workspace share is returned when main is claimed."""
    project_file = _create_project_file_with_running(
        running_claims=[_WorkspaceClaim(1, "crs", "feature")]
    )
    try:
        workspace_num = get_first_available_workspace(project_file, "test")
        assert workspace_num == 2
    finally:
        Path(project_file).unlink()


def test_get_first_available_workspace_skips_claimed() -> None:
    """Test that claimed workspaces are skipped."""
    project_file = _create_project_file_with_running(
        running_claims=[
            _WorkspaceClaim(1, "crs", "feature1"),
            _WorkspaceClaim(2, "qa", "feature2"),
        ]
    )
    try:
        workspace_num = get_first_available_workspace(project_file, "test")
        assert workspace_num == 3
    finally:
        Path(project_file).unlink()


def test_running_field_get_workspace_directory_basic() -> None:
    """Test get_workspace_directory returns correct path."""
    with patch("running_field.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="/cloud/myproject/google3\n"
        )
        result = get_workspace_dir("myproject")
        assert result == "/cloud/myproject/google3"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["bb_get_workspace", "myproject", "1"]


def test_running_field_get_workspace_directory_with_workspace_num() -> None:
    """Test get_workspace_directory with workspace number."""
    with patch("running_field.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="/cloud/myproject_3/google3\n"
        )
        result = get_workspace_dir("myproject", 3)
        assert result == "/cloud/myproject_3/google3"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["bb_get_workspace", "myproject", "3"]


def test_running_field_get_workspace_directory_command_failure() -> None:
    """Test get_workspace_directory raises on command failure."""
    import subprocess

    import pytest

    with patch("running_field.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["bb_get_workspace", "myproject", "1"], stderr="Error"
        )
        with pytest.raises(RuntimeError, match="bb_get_workspace failed"):
            get_workspace_dir("myproject")


def test_running_field_get_workspace_directory_command_not_found() -> None:
    """Test get_workspace_directory raises on command not found."""
    import pytest

    with patch("running_field.subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        with pytest.raises(RuntimeError, match="command not found"):
            get_workspace_dir("myproject")


def test_get_workspace_directory_for_num_main() -> None:
    """Test getting main workspace directory."""
    with patch("running_field.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="/cloud/myproject/google3\n"
        )
        workspace_dir, suffix = get_workspace_directory_for_num(1, "myproject")
        assert workspace_dir == "/cloud/myproject/google3"
        assert suffix is None
        # Verify bb_get_workspace was called correctly
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["bb_get_workspace", "myproject", "1"]


def test_get_workspace_directory_for_num_share() -> None:
    """Test getting workspace share directory."""
    with patch("running_field.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="/cloud/myproject_3/google3\n"
        )
        workspace_dir, suffix = get_workspace_directory_for_num(3, "myproject")
        assert workspace_dir == "/cloud/myproject_3/google3"
        assert suffix == "myproject_3"
        # Verify bb_get_workspace was called correctly
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["bb_get_workspace", "myproject", "3"]


def test_get_workspace_directory_uses_running_field() -> None:
    """Test that get_workspace_directory uses RUNNING field."""
    project_file = _create_project_file_with_running(
        running_claims=[_WorkspaceClaim(1, "crs", "other_feature")]
    )
    try:
        cs = ChangeSpec(
            name="Test",
            description="Test",
            parent="None",
            cl="None",
            test_targets=None,
            status="Drafted",
            file_path=project_file,
            line_number=1,
            kickstart=None,
        )

        with patch("running_field.subprocess.run") as mock_run:
            # Get the project basename from the temp file
            project_basename = Path(project_file).stem
            mock_run.return_value = MagicMock(
                returncode=0, stdout=f"/cloud/{project_basename}_2/google3\n"
            )
            # Since workspace 1 is claimed, should return workspace 2
            workspace_dir, workspace_suffix = get_workspace_directory(cs)
            # Project file is temp file, basename is random
            assert workspace_suffix is not None
            assert "_2" in workspace_suffix
            # Verify bb_get_workspace was called with workspace 2
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "bb_get_workspace"
            assert args[2] == "2"  # workspace number
    finally:
        Path(project_file).unlink()


def test_display_changespec_with_hints_returns_mappings() -> None:
    """Test that display_changespec with hints returns hint mappings."""
    from io import StringIO

    from rich.console import Console
    from work.changespec import ChangeSpec, display_changespec

    # Create a minimal ChangeSpec
    changespec = ChangeSpec(
        name="test_spec",
        description="Test description",
        parent=None,
        cl=None,
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
    )

    # Create a console that writes to a string buffer
    console = Console(file=StringIO(), force_terminal=True)

    # Call with hints enabled
    hint_mappings = display_changespec(changespec, console, with_hints=True)

    # Should have at least hint 0 (the project file)
    assert 0 in hint_mappings
    assert hint_mappings[0] == "/tmp/test.gp"


def test_display_changespec_without_hints_returns_empty() -> None:
    """Test that display_changespec without hints returns empty dict."""
    from io import StringIO

    from rich.console import Console
    from work.changespec import ChangeSpec, display_changespec

    # Create a minimal ChangeSpec
    changespec = ChangeSpec(
        name="test_spec",
        description="Test description",
        parent=None,
        cl=None,
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
    )

    # Create a console that writes to a string buffer
    console = Console(file=StringIO(), force_terminal=True)

    # Call without hints (default)
    hint_mappings = display_changespec(changespec, console)

    # Should be empty when hints not enabled
    assert hint_mappings == {}


def test_get_available_workflows_no_hooks() -> None:
    """Test that no workflows are returned when hooks is None."""
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
        hooks=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_empty_hooks() -> None:
    """Test that no workflows are returned when hooks list is empty."""
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
        hooks=[],
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_all_hooks_passing() -> None:
    """Test that no fix-hook workflow when all hooks passing."""
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
        hooks=[
            _make_hook(command="bb_rabbit_test //target1", status="PASSED"),
            _make_hook(command="flake8 src", status="PASSED"),
        ],
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_with_changes_requested_and_failing_hook() -> None:
    """Test that both fix-hook and crs workflows are returned."""
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
        hooks=[
            _make_hook(command="flake8 src", status="FAILED"),
        ],
    )
    workflows = get_available_workflows(cs)
    # Both fix-hook and crs should be available
    assert workflows == ["fix-hook", "crs"]
