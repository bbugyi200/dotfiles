"""Tests for update_to_changespec operations."""

from unittest.mock import MagicMock, patch

from ace.changespec import ChangeSpec
from ace.operations import update_to_changespec


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

    with patch("ace.operations.get_workspace_dir_from_project") as mock_get_ws:
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

    with patch("ace.operations.get_workspace_dir_from_project") as mock_get_ws:
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

    with patch("ace.operations.get_workspace_dir_from_project") as mock_get_ws:
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
