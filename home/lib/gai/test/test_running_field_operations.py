"""Tests for RUNNING field and workspace management operations."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ace.changespec import ChangeSpec
from ace.operations import get_workspace_directory
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
    """Test _WorkspaceClaim.to_line formatting (PID is required, second field)."""
    claim = _WorkspaceClaim(
        workspace_num=1, workflow="crs", cl_name="my_feature", pid=12345
    )
    assert claim.to_line() == "  #1 | 12345 | crs | my_feature"


def test_workspace_claim_to_line_no_cl_name() -> None:
    """Test _WorkspaceClaim.to_line without cl_name (PID is required)."""
    claim = _WorkspaceClaim(workspace_num=3, workflow="run", cl_name=None, pid=54321)
    assert claim.to_line() == "  #3 | 54321 | run | "


def test_workspace_claim_from_line_new_format() -> None:
    """Test parsing new format with PID as second field."""
    claim = _WorkspaceClaim.from_line("  #2 | 12345 | crs | my_change")
    assert claim is not None
    assert claim.workspace_num == 2
    assert claim.pid == 12345
    assert claim.workflow == "crs"
    assert claim.cl_name == "my_change"


def test_workspace_claim_from_line_new_format_empty_pid_returns_none() -> None:
    """Test parsing new format with empty PID field returns None (PID required)."""
    claim = _WorkspaceClaim.from_line("  #1 |  | crs | my_feature")
    # Entries without PID are now invalid
    assert claim is None


def test_workspace_claim_from_line_new_format_no_cl_name() -> None:
    """Test parsing new format without cl_name."""
    claim = _WorkspaceClaim.from_line("  #3 | 54321 | run | ")
    assert claim is not None
    assert claim.workspace_num == 3
    assert claim.pid == 54321
    assert claim.workflow == "run"
    assert claim.cl_name is None


def test_workspace_claim_from_line_new_format_with_timestamp() -> None:
    """Test parsing new format with PID and timestamp."""
    claim = _WorkspaceClaim.from_line("  #1 | 12345 | crs | my_feature | 251230_151429")
    assert claim is not None
    assert claim.workspace_num == 1
    assert claim.pid == 12345
    assert claim.workflow == "crs"
    assert claim.cl_name == "my_feature"
    assert claim.artifacts_timestamp == "251230_151429"


def test_workspace_claim_from_line_legacy_format_no_pid_returns_none() -> None:
    """Test parsing legacy format without PID returns None (PID required)."""
    claim = _WorkspaceClaim.from_line("  #2 | crs | my_change")
    # Legacy format without PID is now invalid
    assert claim is None


def test_workspace_claim_from_line_legacy_format_no_pid_no_cl_returns_none() -> None:
    """Test parsing legacy format without PID or cl_name returns None."""
    claim = _WorkspaceClaim.from_line("  #1 | run | ")
    # Legacy format without PID is now invalid
    assert claim is None


def test_workspace_claim_from_line_legacy_format_with_pid() -> None:
    """Test parsing legacy format with PID (fourth field)."""
    claim = _WorkspaceClaim.from_line("  #2 | crs | my_change | 12345")
    assert claim is not None
    assert claim.workspace_num == 2
    assert claim.workflow == "crs"
    assert claim.cl_name == "my_change"
    assert claim.pid == 12345


def test_workspace_claim_from_line_legacy_format_with_pid_no_cl_name() -> None:
    """Test parsing legacy format with PID but no cl_name."""
    claim = _WorkspaceClaim.from_line("  #3 | run |  | 54321")
    assert claim is not None
    assert claim.workspace_num == 3
    assert claim.workflow == "run"
    assert claim.cl_name is None
    assert claim.pid == 54321


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
        running_claims=[_WorkspaceClaim(1, "crs", "feature", pid=12345)]
    )
    try:
        claims = get_claimed_workspaces(project_file)
        assert len(claims) == 1
        assert claims[0].workspace_num == 1
        assert claims[0].workflow == "crs"
        assert claims[0].cl_name == "feature"
        assert claims[0].pid == 12345
    finally:
        Path(project_file).unlink()


def test_get_claimed_workspaces_multiple() -> None:
    """Test getting multiple workspace claims."""
    project_file = _create_project_file_with_running(
        running_claims=[
            _WorkspaceClaim(1, "crs", "feature1", pid=11111),
            _WorkspaceClaim(3, "run", "feature2", pid=22222),
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
    """Test claiming a workspace when RUNNING field doesn't exist (PID required)."""
    project_file = _create_project_file_with_running(has_bug_field=True)
    try:
        # PID is required - pass it as 4th positional arg
        success = claim_workspace(project_file, 1, "crs", 12345, "my_feature")
        assert success is True

        with open(project_file) as f:
            content = f.read()

        assert "RUNNING:" in content
        # Format: #N | PID | WORKFLOW | CL_NAME
        assert "#1 | 12345 | crs | my_feature" in content

        # Verify PID is parsed correctly
        claims = get_claimed_workspaces(project_file)
        assert len(claims) == 1
        assert claims[0].pid == 12345
    finally:
        Path(project_file).unlink()


def test_claim_workspace_existing_running_field() -> None:
    """Test claiming a workspace when RUNNING field already exists."""
    project_file = _create_project_file_with_running(
        running_claims=[_WorkspaceClaim(1, "crs", "existing", pid=11111)]
    )
    try:
        success = claim_workspace(project_file, 2, "run", 22222, "new_feature")
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
        running_claims=[_WorkspaceClaim(1, "crs", "feature", pid=12345)]
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
            _WorkspaceClaim(1, "crs", "feature1", pid=11111),
            _WorkspaceClaim(2, "run", "feature2", pid=22222),
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
            _WorkspaceClaim(1, "crs", "feature1", pid=11111),
            _WorkspaceClaim(1, "run", "feature2", pid=22222),
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
        workspace_num = get_first_available_workspace(project_file)
        assert workspace_num == 1
    finally:
        Path(project_file).unlink()


def test_get_first_available_workspace_main_claimed() -> None:
    """Test that next workspace share is returned when main is claimed."""
    project_file = _create_project_file_with_running(
        running_claims=[_WorkspaceClaim(1, "crs", "feature", pid=12345)]
    )
    try:
        workspace_num = get_first_available_workspace(project_file)
        assert workspace_num == 2
    finally:
        Path(project_file).unlink()


def test_get_first_available_workspace_skips_claimed() -> None:
    """Test that claimed workspaces are skipped."""
    project_file = _create_project_file_with_running(
        running_claims=[
            _WorkspaceClaim(1, "crs", "feature1", pid=11111),
            _WorkspaceClaim(2, "run", "feature2", pid=22222),
        ]
    )
    try:
        workspace_num = get_first_available_workspace(project_file)
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
        running_claims=[_WorkspaceClaim(1, "crs", "other_feature", pid=12345)]
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
