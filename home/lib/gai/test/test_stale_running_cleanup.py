"""Tests for stale RUNNING entry cleanup functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ace.scheduler.stale_running_cleanup import (
    _get_all_project_files,
    cleanup_stale_running_entries,
)
from running_field import _WorkspaceClaim


def test_cleanup_removes_dead_process_entries() -> None:
    """Test that entries with dead PIDs are cleaned up."""
    claims = [
        _WorkspaceClaim(
            workspace_num=1, workflow="crs", cl_name="feature_a", pid=12345
        ),
        _WorkspaceClaim(
            workspace_num=2, workflow="run", cl_name="feature_b", pid=67890
        ),
    ]

    with (
        patch(
            "ace.scheduler.stale_running_cleanup._get_all_project_files"
        ) as mock_get_files,
        patch(
            "ace.scheduler.stale_running_cleanup.get_claimed_workspaces"
        ) as mock_get_claims,
        patch(
            "ace.scheduler.stale_running_cleanup.is_process_running"
        ) as mock_is_running,
        patch("ace.scheduler.stale_running_cleanup.release_workspace") as mock_release,
    ):
        mock_get_files.return_value = [
            "/home/user/.gai/projects/myproject/myproject.gp"
        ]
        mock_get_claims.return_value = claims
        # First PID dead, second alive
        mock_is_running.side_effect = [False, True]

        released = cleanup_stale_running_entries()

        assert released == 1
        mock_release.assert_called_once_with(
            "/home/user/.gai/projects/myproject/myproject.gp", 1, "crs", "feature_a"
        )


def test_cleanup_keeps_running_process_entries() -> None:
    """Test that entries with running PIDs are kept."""
    claims = [
        _WorkspaceClaim(
            workspace_num=1, workflow="crs", cl_name="feature_a", pid=12345
        ),
        _WorkspaceClaim(
            workspace_num=2, workflow="run", cl_name="feature_b", pid=67890
        ),
    ]

    with (
        patch(
            "ace.scheduler.stale_running_cleanup._get_all_project_files"
        ) as mock_get_files,
        patch(
            "ace.scheduler.stale_running_cleanup.get_claimed_workspaces"
        ) as mock_get_claims,
        patch(
            "ace.scheduler.stale_running_cleanup.is_process_running"
        ) as mock_is_running,
        patch("ace.scheduler.stale_running_cleanup.release_workspace") as mock_release,
    ):
        mock_get_files.return_value = [
            "/home/user/.gai/projects/myproject/myproject.gp"
        ]
        mock_get_claims.return_value = claims
        # Both PIDs running
        mock_is_running.return_value = True

        released = cleanup_stale_running_entries()

        assert released == 0
        mock_release.assert_not_called()


def test_cleanup_mixed_alive_and_dead() -> None:
    """Test cleanup with mix of alive and dead processes."""
    claims = [
        _WorkspaceClaim(workspace_num=1, workflow="crs", cl_name="a", pid=111),
        _WorkspaceClaim(workspace_num=2, workflow="run", cl_name="b", pid=222),
        _WorkspaceClaim(workspace_num=3, workflow="rerun", cl_name="c", pid=333),
    ]

    with (
        patch(
            "ace.scheduler.stale_running_cleanup._get_all_project_files"
        ) as mock_get_files,
        patch(
            "ace.scheduler.stale_running_cleanup.get_claimed_workspaces"
        ) as mock_get_claims,
        patch(
            "ace.scheduler.stale_running_cleanup.is_process_running"
        ) as mock_is_running,
        patch("ace.scheduler.stale_running_cleanup.release_workspace") as mock_release,
    ):
        mock_get_files.return_value = ["/home/user/.gai/projects/proj/proj.gp"]
        mock_get_claims.return_value = claims
        # PIDs 111 and 333 dead, 222 alive
        mock_is_running.side_effect = [False, True, False]

        released = cleanup_stale_running_entries()

        assert released == 2
        assert mock_release.call_count == 2


def test_cleanup_logs_released_entries() -> None:
    """Test that cleanup logs released entries."""
    claims = [
        _WorkspaceClaim(
            workspace_num=1, workflow="crs", cl_name="feature_a", pid=12345
        ),
    ]

    log_fn = MagicMock()

    with (
        patch(
            "ace.scheduler.stale_running_cleanup._get_all_project_files"
        ) as mock_get_files,
        patch(
            "ace.scheduler.stale_running_cleanup.get_claimed_workspaces"
        ) as mock_get_claims,
        patch(
            "ace.scheduler.stale_running_cleanup.is_process_running"
        ) as mock_is_running,
        patch("ace.scheduler.stale_running_cleanup.release_workspace"),
    ):
        mock_get_files.return_value = ["/home/user/.gai/projects/proj/proj.gp"]
        mock_get_claims.return_value = claims
        mock_is_running.return_value = False

        cleanup_stale_running_entries(log_fn=log_fn)

        log_fn.assert_called_once()
        log_msg = log_fn.call_args[0][0]
        assert "Released stale workspace #1" in log_msg
        assert "crs" in log_msg
        assert "feature_a" in log_msg
        assert "12345" in log_msg


def test_cleanup_logs_entry_without_cl_name() -> None:
    """Test log message for entry without CL name."""
    claims = [
        _WorkspaceClaim(workspace_num=2, workflow="run", cl_name=None, pid=54321),
    ]

    log_fn = MagicMock()

    with (
        patch(
            "ace.scheduler.stale_running_cleanup._get_all_project_files"
        ) as mock_get_files,
        patch(
            "ace.scheduler.stale_running_cleanup.get_claimed_workspaces"
        ) as mock_get_claims,
        patch(
            "ace.scheduler.stale_running_cleanup.is_process_running"
        ) as mock_is_running,
        patch("ace.scheduler.stale_running_cleanup.release_workspace"),
    ):
        mock_get_files.return_value = ["/home/user/.gai/projects/proj/proj.gp"]
        mock_get_claims.return_value = claims
        mock_is_running.return_value = False

        cleanup_stale_running_entries(log_fn=log_fn)

        log_fn.assert_called_once()
        log_msg = log_fn.call_args[0][0]
        assert "Released stale workspace #2" in log_msg
        assert "run" in log_msg
        assert "for CL" not in log_msg  # No CL name


def test_cleanup_empty_project_list() -> None:
    """Test cleanup when no project files exist."""
    with (
        patch(
            "ace.scheduler.stale_running_cleanup._get_all_project_files"
        ) as mock_get_files,
    ):
        mock_get_files.return_value = []

        released = cleanup_stale_running_entries()

        assert released == 0


def test_cleanup_multiple_projects() -> None:
    """Test cleanup across multiple project files."""
    proj1_claims = [
        _WorkspaceClaim(workspace_num=1, workflow="crs", cl_name="a", pid=111),
    ]
    proj2_claims = [
        _WorkspaceClaim(workspace_num=1, workflow="run", cl_name="b", pid=222),
    ]

    with (
        patch(
            "ace.scheduler.stale_running_cleanup._get_all_project_files"
        ) as mock_get_files,
        patch(
            "ace.scheduler.stale_running_cleanup.get_claimed_workspaces"
        ) as mock_get_claims,
        patch(
            "ace.scheduler.stale_running_cleanup.is_process_running"
        ) as mock_is_running,
        patch("ace.scheduler.stale_running_cleanup.release_workspace") as mock_release,
    ):
        mock_get_files.return_value = [
            "/home/user/.gai/projects/proj1/proj1.gp",
            "/home/user/.gai/projects/proj2/proj2.gp",
        ]
        mock_get_claims.side_effect = [proj1_claims, proj2_claims]
        # Both PIDs dead
        mock_is_running.return_value = False

        released = cleanup_stale_running_entries()

        assert released == 2
        assert mock_release.call_count == 2


def test_get_all_project_files_nonexistent_dir() -> None:
    """Test _get_all_project_files when projects dir doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Point home to temp dir with no .gai/projects directory
        fake_home = Path(tmpdir)
        with patch("ace.scheduler.stale_running_cleanup.Path") as mock_path:
            mock_path.home.return_value = fake_home

            result = _get_all_project_files()

            assert result == []


def test_get_all_project_files_finds_gp_files() -> None:
    """Test _get_all_project_files finds .gp files in project dirs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_home = Path(tmpdir)
        projects_dir = fake_home / ".gai" / "projects"
        projects_dir.mkdir(parents=True)

        # Create proj1 with .gp file
        proj1_dir = projects_dir / "proj1"
        proj1_dir.mkdir()
        (proj1_dir / "proj1.gp").write_text("# test")

        # Create proj2 without .gp file
        proj2_dir = projects_dir / "proj2"
        proj2_dir.mkdir()

        # Create a regular file (not a directory)
        (projects_dir / "somefile.txt").write_text("not a dir")

        with patch("ace.scheduler.stale_running_cleanup.Path") as mock_path:
            mock_path.home.return_value = fake_home

            result = _get_all_project_files()

            # Should only find proj1.gp
            assert len(result) == 1
            assert "proj1.gp" in result[0]
