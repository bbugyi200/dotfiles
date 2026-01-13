"""Tests for ace.operations module."""

import tempfile
from unittest.mock import MagicMock, patch

from ace.operations import (
    _has_failing_hooks_for_fix,
    get_available_workflows,
    get_workspace_directory,
    update_to_changespec,
)

# === Tests for get_workspace_directory ===


@patch("ace.operations.get_workspace_directory_for_num")
@patch("ace.operations.get_first_available_workspace")
def test_get_workspace_directory_returns_tuple(
    mock_get_first: MagicMock, mock_get_dir: MagicMock
) -> None:
    """Test get_workspace_directory returns workspace directory and suffix."""
    mock_get_first.return_value = 3
    mock_get_dir.return_value = ("/path/to/workspace", "fig_3")

    mock_changespec = MagicMock()
    mock_changespec.file_path = "/path/to/project.gp"
    mock_changespec.project_basename = "my_project"

    result = get_workspace_directory(mock_changespec)

    assert result == ("/path/to/workspace", "fig_3")
    mock_get_first.assert_called_once_with("/path/to/project.gp")
    mock_get_dir.assert_called_once_with(3, "my_project")


@patch("ace.operations.get_workspace_directory_for_num")
@patch("ace.operations.get_first_available_workspace")
def test_get_workspace_directory_main_workspace(
    mock_get_first: MagicMock, mock_get_dir: MagicMock
) -> None:
    """Test get_workspace_directory returns None suffix for main workspace."""
    mock_get_first.return_value = 1
    mock_get_dir.return_value = ("/path/to/main", None)

    mock_changespec = MagicMock()
    mock_changespec.file_path = "/project.gp"
    mock_changespec.project_basename = "project"

    result = get_workspace_directory(mock_changespec)

    assert result == ("/path/to/main", None)


# === Tests for _has_failing_hooks_for_fix ===


@patch("ace.operations.has_failing_hooks_for_fix")
def test_has_failing_hooks_for_fix_true(mock_has_failing: MagicMock) -> None:
    """Test _has_failing_hooks_for_fix returns True when hooks are eligible."""
    mock_has_failing.return_value = True

    mock_changespec = MagicMock()
    mock_changespec.hooks = [MagicMock()]

    assert _has_failing_hooks_for_fix(mock_changespec) is True
    mock_has_failing.assert_called_once_with(mock_changespec.hooks)


@patch("ace.operations.has_failing_hooks_for_fix")
def test_has_failing_hooks_for_fix_false(mock_has_failing: MagicMock) -> None:
    """Test _has_failing_hooks_for_fix returns False when no eligible hooks."""
    mock_has_failing.return_value = False

    mock_changespec = MagicMock()
    mock_changespec.hooks = []

    assert _has_failing_hooks_for_fix(mock_changespec) is False


# === Tests for get_available_workflows ===


@patch("ace.operations._has_failing_hooks_for_fix")
def test_get_available_workflows_empty(mock_has_failing: MagicMock) -> None:
    """Test get_available_workflows returns empty list when no workflows."""
    mock_has_failing.return_value = False

    mock_changespec = MagicMock()
    mock_changespec.comments = []

    result = get_available_workflows(mock_changespec)

    assert result == []


@patch("ace.operations._has_failing_hooks_for_fix")
def test_get_available_workflows_fix_hook_only(mock_has_failing: MagicMock) -> None:
    """Test get_available_workflows returns fix-hook when failing hooks."""
    mock_has_failing.return_value = True

    mock_changespec = MagicMock()
    mock_changespec.comments = []

    result = get_available_workflows(mock_changespec)

    assert result == ["fix-hook"]


@patch("ace.operations._has_failing_hooks_for_fix")
def test_get_available_workflows_crs_only(mock_has_failing: MagicMock) -> None:
    """Test get_available_workflows returns crs when critique comment exists."""
    mock_has_failing.return_value = False

    mock_comment = MagicMock()
    mock_comment.reviewer = "critique"
    mock_comment.suffix = None

    mock_changespec = MagicMock()
    mock_changespec.comments = [mock_comment]

    result = get_available_workflows(mock_changespec)

    assert result == ["crs"]


@patch("ace.operations._has_failing_hooks_for_fix")
def test_get_available_workflows_crs_critique_me(mock_has_failing: MagicMock) -> None:
    """Test get_available_workflows returns crs for critique:me comment."""
    mock_has_failing.return_value = False

    mock_comment = MagicMock()
    mock_comment.reviewer = "critique:me"
    mock_comment.suffix = None

    mock_changespec = MagicMock()
    mock_changespec.comments = [mock_comment]

    result = get_available_workflows(mock_changespec)

    assert result == ["crs"]


@patch("ace.operations._has_failing_hooks_for_fix")
def test_get_available_workflows_crs_with_suffix_ignored(
    mock_has_failing: MagicMock,
) -> None:
    """Test critique comment with suffix is not included in workflows."""
    mock_has_failing.return_value = False

    mock_comment = MagicMock()
    mock_comment.reviewer = "critique"
    mock_comment.suffix = "timestamp_123"

    mock_changespec = MagicMock()
    mock_changespec.comments = [mock_comment]

    result = get_available_workflows(mock_changespec)

    assert result == []


@patch("ace.operations._has_failing_hooks_for_fix")
def test_get_available_workflows_both(mock_has_failing: MagicMock) -> None:
    """Test get_available_workflows returns both workflows when applicable."""
    mock_has_failing.return_value = True

    mock_comment = MagicMock()
    mock_comment.reviewer = "critique"
    mock_comment.suffix = None

    mock_changespec = MagicMock()
    mock_changespec.comments = [mock_comment]

    result = get_available_workflows(mock_changespec)

    assert result == ["fix-hook", "crs"]


@patch("ace.operations._has_failing_hooks_for_fix")
def test_get_available_workflows_no_comments(mock_has_failing: MagicMock) -> None:
    """Test get_available_workflows handles None comments."""
    mock_has_failing.return_value = False

    mock_changespec = MagicMock()
    mock_changespec.comments = None

    result = get_available_workflows(mock_changespec)

    assert result == []


@patch("ace.operations._has_failing_hooks_for_fix")
def test_get_available_workflows_only_first_critique(
    mock_has_failing: MagicMock,
) -> None:
    """Test that only first critique comment triggers crs workflow."""
    mock_has_failing.return_value = False

    mock_comment1 = MagicMock()
    mock_comment1.reviewer = "critique"
    mock_comment1.suffix = None

    mock_comment2 = MagicMock()
    mock_comment2.reviewer = "critique"
    mock_comment2.suffix = None

    mock_changespec = MagicMock()
    mock_changespec.comments = [mock_comment1, mock_comment2]

    result = get_available_workflows(mock_changespec)

    # Should only have one "crs" entry even with multiple critique comments
    assert result == ["crs"]


# === Tests for update_to_changespec ===


@patch("ace.operations.get_workspace_dir_from_project")
def test_update_to_changespec_workspace_not_found(
    mock_get_dir: MagicMock,
) -> None:
    """Test update_to_changespec handles workspace lookup failure."""
    mock_get_dir.side_effect = RuntimeError("Workspace not found")

    mock_changespec = MagicMock()
    mock_changespec.project_basename = "test_project"

    success, error = update_to_changespec(mock_changespec)

    assert success is False
    assert error == "Workspace not found"


def test_update_to_changespec_directory_not_exists() -> None:
    """Test update_to_changespec handles non-existent directory."""
    mock_changespec = MagicMock()

    success, error = update_to_changespec(
        mock_changespec, workspace_dir="/nonexistent/path"
    )

    assert success is False
    assert error is not None
    assert "does not exist" in error


def test_update_to_changespec_path_not_directory() -> None:
    """Test update_to_changespec handles path that is not a directory."""
    with tempfile.NamedTemporaryFile() as tmp_file:
        mock_changespec = MagicMock()

        success, error = update_to_changespec(
            mock_changespec, workspace_dir=tmp_file.name
        )

        assert success is False
        assert error is not None
        assert "not a directory" in error


@patch("subprocess.run")
def test_update_to_changespec_success_with_revision(mock_run: MagicMock) -> None:
    """Test update_to_changespec succeeds with specified revision."""
    mock_run.return_value = MagicMock(returncode=0)

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_changespec = MagicMock()

        success, error = update_to_changespec(
            mock_changespec, revision="my_revision", workspace_dir=tmpdir
        )

        assert success is True
        assert error is None
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["bb_hg_update", "my_revision"]
        assert call_args[1]["cwd"] == tmpdir


@patch("subprocess.run")
def test_update_to_changespec_uses_parent_revision(mock_run: MagicMock) -> None:
    """Test update_to_changespec uses parent when no revision specified."""
    mock_run.return_value = MagicMock(returncode=0)

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_changespec = MagicMock()
        mock_changespec.parent = "parent_rev"

        success, error = update_to_changespec(mock_changespec, workspace_dir=tmpdir)

        assert success is True
        call_args = mock_run.call_args
        assert call_args[0][0] == ["bb_hg_update", "parent_rev"]


@patch("subprocess.run")
def test_update_to_changespec_uses_p4head_default(mock_run: MagicMock) -> None:
    """Test update_to_changespec uses p4head when no parent or revision."""
    mock_run.return_value = MagicMock(returncode=0)

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_changespec = MagicMock()
        mock_changespec.parent = None

        success, error = update_to_changespec(mock_changespec, workspace_dir=tmpdir)

        assert success is True
        call_args = mock_run.call_args
        assert call_args[0][0] == ["bb_hg_update", "p4head"]


@patch("subprocess.run")
def test_update_to_changespec_command_fails_stderr(mock_run: MagicMock) -> None:
    """Test update_to_changespec handles command failure with stderr."""
    import subprocess

    err = subprocess.CalledProcessError(returncode=1, cmd=["bb_hg_update"])
    err.stderr = "Update failed"
    err.stdout = ""
    mock_run.side_effect = err

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_changespec = MagicMock()
        mock_changespec.parent = None

        success, error = update_to_changespec(mock_changespec, workspace_dir=tmpdir)

        assert success is False
        assert error is not None
        assert "bb_hg_update failed" in error
        assert "Update failed" in error


@patch("subprocess.run")
def test_update_to_changespec_command_fails_stdout(mock_run: MagicMock) -> None:
    """Test update_to_changespec handles command failure with stdout only."""
    import subprocess

    err = subprocess.CalledProcessError(returncode=1, cmd=["bb_hg_update"])
    err.stderr = ""
    err.stdout = "Conflict detected"
    mock_run.side_effect = err

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_changespec = MagicMock()
        mock_changespec.parent = None

        success, error = update_to_changespec(mock_changespec, workspace_dir=tmpdir)

        assert success is False
        assert error is not None
        assert "Conflict detected" in error


@patch("subprocess.run")
def test_update_to_changespec_command_not_found(mock_run: MagicMock) -> None:
    """Test update_to_changespec handles command not found."""
    mock_run.side_effect = FileNotFoundError()

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_changespec = MagicMock()
        mock_changespec.parent = None

        success, error = update_to_changespec(mock_changespec, workspace_dir=tmpdir)

        assert success is False
        assert error is not None
        assert "not found" in error


@patch("subprocess.run")
def test_update_to_changespec_unexpected_error(mock_run: MagicMock) -> None:
    """Test update_to_changespec handles unexpected errors."""
    mock_run.side_effect = OSError("Disk full")

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_changespec = MagicMock()
        mock_changespec.parent = None

        success, error = update_to_changespec(mock_changespec, workspace_dir=tmpdir)

        assert success is False
        assert error is not None
        assert "Unexpected error" in error
        assert "Disk full" in error
