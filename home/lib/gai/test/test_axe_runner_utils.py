"""Tests for axe_runner_utils module."""

from unittest.mock import MagicMock, patch

from axe_runner_utils import (
    _check_for_local_changes,
    create_proposal_from_changes,
    finalize_axe_runner,
)


def test_check_for_local_changes_with_changes() -> None:
    """Test _check_for_local_changes returns True when changes exist."""
    with patch("axe_runner_utils.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="file1.py\nfile2.py\n")
        result = _check_for_local_changes()
        assert result is True
        mock_run.assert_called_once_with(
            ["branch_local_changes"],
            capture_output=True,
            text=True,
        )


def test_check_for_local_changes_no_changes() -> None:
    """Test _check_for_local_changes returns False when no changes."""
    with patch("axe_runner_utils.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="")
        result = _check_for_local_changes()
        assert result is False


def test_check_for_local_changes_whitespace_only() -> None:
    """Test _check_for_local_changes returns False for whitespace-only output."""
    with patch("axe_runner_utils.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="   \n\n  ")
        result = _check_for_local_changes()
        assert result is False


def test_create_proposal_from_changes_no_changes() -> None:
    """Test create_proposal_from_changes returns failure when no changes."""
    with patch("axe_runner_utils._check_for_local_changes", return_value=False):
        proposal_id, exit_code = create_proposal_from_changes(
            project_file="/path/to/project.gp",
            cl_name="test_cl",
            workspace_dir="/workspace",
            workflow_note="[test]",
            prompt="test prompt",
            response="test response",
            workflow="test",
        )
        assert proposal_id is None
        assert exit_code == 1


def test_create_proposal_from_changes_success() -> None:
    """Test create_proposal_from_changes succeeds with changes."""
    with (
        patch("axe_runner_utils._check_for_local_changes", return_value=True),
        patch("axe_runner_utils.save_chat_history", return_value="/path/chat.md"),
        patch("axe_runner_utils.save_diff", return_value="/path/diff.patch"),
        patch(
            "axe_runner_utils.add_proposed_commit_entry",
            return_value=(True, "abc123"),
        ),
        patch("axe_runner_utils.clean_workspace"),
    ):
        proposal_id, exit_code = create_proposal_from_changes(
            project_file="/path/to/project.gp",
            cl_name="test_cl",
            workspace_dir="/workspace",
            workflow_note="[test]",
            prompt="test prompt",
            response="test response",
            workflow="test",
        )
        assert proposal_id == "abc123"
        assert exit_code == 0


def test_create_proposal_from_changes_diff_fails() -> None:
    """Test create_proposal_from_changes fails when diff save fails."""
    with (
        patch("axe_runner_utils._check_for_local_changes", return_value=True),
        patch("axe_runner_utils.save_chat_history", return_value="/path/chat.md"),
        patch("axe_runner_utils.save_diff", return_value=None),
    ):
        proposal_id, exit_code = create_proposal_from_changes(
            project_file="/path/to/project.gp",
            cl_name="test_cl",
            workspace_dir="/workspace",
            workflow_note="[test]",
            prompt="test prompt",
            response="test response",
            workflow="test",
        )
        assert proposal_id is None
        assert exit_code == 1


def test_create_proposal_from_changes_history_entry_fails() -> None:
    """Test create_proposal_from_changes fails when history entry creation fails."""
    with (
        patch("axe_runner_utils._check_for_local_changes", return_value=True),
        patch("axe_runner_utils.save_chat_history", return_value="/path/chat.md"),
        patch("axe_runner_utils.save_diff", return_value="/path/diff.patch"),
        patch(
            "axe_runner_utils.add_proposed_commit_entry",
            return_value=(False, None),
        ),
    ):
        proposal_id, exit_code = create_proposal_from_changes(
            project_file="/path/to/project.gp",
            cl_name="test_cl",
            workspace_dir="/workspace",
            workflow_note="[test]",
            prompt="test prompt",
            response="test response",
            workflow="test",
        )
        assert proposal_id is None
        assert exit_code == 1


def test_finalize_axe_runner_success() -> None:
    """Test finalize_axe_runner calls all required functions."""
    mock_cs = MagicMock()
    mock_cs.name = "test_cl"

    update_suffix_calls: list[tuple[object, str, str | None, int]] = []

    def mock_update_suffix(cs: object, pf: str, pid: str | None, ec: int) -> None:
        update_suffix_calls.append((cs, pf, pid, ec))

    with (
        patch(
            "axe_runner_utils.parse_project_file",
            return_value=[mock_cs],
        ),
        patch("axe_runner_utils.release_workspace") as mock_release,
    ):
        finalize_axe_runner(
            project_file="/path/project.gp",
            changespec_name="test_cl",
            workspace_num=1,
            workflow_name="test",
            proposal_id="abc123",
            exit_code=0,
            update_suffix_fn=mock_update_suffix,
        )

        # Check update_suffix was called
        assert len(update_suffix_calls) == 1
        assert update_suffix_calls[0] == (mock_cs, "/path/project.gp", "abc123", 0)

        # Check release_workspace was called
        mock_release.assert_called_once_with(
            "/path/project.gp",
            1,
            "test",
            "test_cl",
        )


def test_finalize_axe_runner_no_matching_changespec() -> None:
    """Test finalize_axe_runner skips suffix update when changespec not found."""
    mock_cs = MagicMock()
    mock_cs.name = "other_cl"

    update_suffix_calls: list[tuple[object, str, str | None, int]] = []

    def mock_update_suffix(cs: object, pf: str, pid: str | None, ec: int) -> None:
        update_suffix_calls.append((cs, pf, pid, ec))

    with (
        patch(
            "axe_runner_utils.parse_project_file",
            return_value=[mock_cs],
        ),
        patch("axe_runner_utils.release_workspace"),
    ):
        finalize_axe_runner(
            project_file="/path/project.gp",
            changespec_name="test_cl",
            workspace_num=1,
            workflow_name="test",
            proposal_id="abc123",
            exit_code=0,
            update_suffix_fn=mock_update_suffix,
        )

        # update_suffix should not be called - no matching changespec
        assert len(update_suffix_calls) == 0


def test_finalize_axe_runner_handles_errors() -> None:
    """Test finalize_axe_runner handles errors gracefully."""
    with (
        patch(
            "axe_runner_utils.parse_project_file",
            side_effect=Exception("Parse error"),
        ),
        patch(
            "axe_runner_utils.release_workspace",
            side_effect=Exception("Release error"),
        ),
    ):
        # Should not raise - errors are caught and printed
        finalize_axe_runner(
            project_file="/path/project.gp",
            changespec_name="test_cl",
            workspace_num=1,
            workflow_name="test",
            proposal_id=None,
            exit_code=1,
            update_suffix_fn=lambda *args: None,
        )
