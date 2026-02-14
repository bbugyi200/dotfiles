"""Tests for axe_runner_utils module."""

import signal
from unittest.mock import MagicMock, patch

from axe_runner_utils import (
    _killed_state,
    finalize_axe_runner,
    install_sigterm_handler,
    prepare_workspace,
    was_killed,
)


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


# Tests for was_killed / install_sigterm_handler
def test_was_killed_default_false() -> None:
    """Test was_killed returns False by default."""
    # Reset state
    _killed_state["killed"] = False
    assert was_killed() is False


def test_install_sigterm_handler_registers_handler() -> None:
    """Test that install_sigterm_handler registers a SIGTERM handler."""
    with patch("axe_runner_utils.signal.signal") as mock_signal:
        install_sigterm_handler("test")
        mock_signal.assert_called_once()
        args = mock_signal.call_args[0]
        assert args[0] == signal.SIGTERM


def test_sigterm_handler_sets_killed() -> None:
    """Test that invoking the captured handler sets was_killed to True."""
    _killed_state["killed"] = False
    captured_handler = None

    with patch("axe_runner_utils.signal.signal") as mock_signal:
        install_sigterm_handler("test")
        captured_handler = mock_signal.call_args[0][1]

    # Invoke the handler - it calls sys.exit, so we catch SystemExit
    with patch("axe_runner_utils.sys.exit"):
        captured_handler(signal.SIGTERM, None)

    assert was_killed() is True
    # Reset state
    _killed_state["killed"] = False


# Tests for prepare_workspace
def test_prepare_workspace_clean_fails() -> None:
    """Test prepare_workspace returns False when clean fails."""
    with patch("commit_utils.run_bb_hg_clean", return_value=(False, "clean error")):
        result = prepare_workspace("/workspace", "my_cl", "p4head", backup_suffix="ace")
        assert result is False


def test_prepare_workspace_update_timeout() -> None:
    """Test prepare_workspace returns False on bb_hg_update timeout."""
    mock_provider = MagicMock()
    mock_provider.checkout.return_value = (False, "bb_hg_update timed out")

    with (
        patch("commit_utils.run_bb_hg_clean", return_value=(True, None)),
        patch("axe_runner_utils.get_vcs_provider", return_value=mock_provider),
    ):
        result = prepare_workspace("/workspace", "my_cl", "p4head", backup_suffix="ace")
        assert result is False


def test_prepare_workspace_update_fails() -> None:
    """Test prepare_workspace returns False when bb_hg_update returns non-zero."""
    mock_provider = MagicMock()
    mock_provider.checkout.return_value = (False, "bb_hg_update failed: update error")

    with (
        patch("commit_utils.run_bb_hg_clean", return_value=(True, None)),
        patch("axe_runner_utils.get_vcs_provider", return_value=mock_provider),
    ):
        result = prepare_workspace("/workspace", "my_cl", "p4head", backup_suffix="ace")
        assert result is False


def test_prepare_workspace_update_exception() -> None:
    """Test prepare_workspace returns False on unexpected exception."""
    mock_provider = MagicMock()
    mock_provider.checkout.return_value = (
        False,
        "bb_hg_update command not found",
    )

    with (
        patch("commit_utils.run_bb_hg_clean", return_value=(True, None)),
        patch("axe_runner_utils.get_vcs_provider", return_value=mock_provider),
    ):
        result = prepare_workspace("/workspace", "my_cl", "p4head", backup_suffix="ace")
        assert result is False


def test_prepare_workspace_success() -> None:
    """Test prepare_workspace returns True on success with correct backup suffix."""
    mock_provider = MagicMock()
    mock_provider.checkout.return_value = (True, None)

    with (
        patch("commit_utils.run_bb_hg_clean", return_value=(True, None)) as mock_clean,
        patch("axe_runner_utils.get_vcs_provider", return_value=mock_provider),
    ):
        result = prepare_workspace(
            "/workspace", "my_cl", "p4head", backup_suffix="workflow"
        )
        assert result is True
        # Verify the backup suffix was used correctly
        mock_clean.assert_called_once_with("/workspace", "my_cl-workflow")
