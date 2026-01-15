"""Tests for the axe process control module."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from axe.process import (
    get_axe_pid,
    get_axe_status,
    is_axe_running,
    stop_axe_daemon,
)
from axe.state import AxeStatus


@pytest.fixture
def temp_state_dir(tmp_path: Path) -> Iterator[Path]:
    """Create a temporary state directory for testing."""
    state_dir = tmp_path / ".gai" / "axe"
    state_dir.mkdir(parents=True, exist_ok=True)
    with patch("axe.state.AXE_STATE_DIR", state_dir):
        with patch("axe.process.AXE_STATE_DIR", state_dir):
            yield state_dir


# --- is_axe_running Tests ---


def test_is_axe_running_returns_false_when_no_pid_file(
    temp_state_dir: Path,
) -> None:
    """Test is_axe_running returns False when no PID file exists."""
    assert is_axe_running() is False


@patch("axe.process.is_process_running")
def test_is_axe_running_returns_true_when_process_running(
    mock_is_running: MagicMock,
    temp_state_dir: Path,
) -> None:
    """Test is_axe_running returns True when process is running."""
    # Create PID file
    pid_file = temp_state_dir / "pid"
    pid_file.write_text("12345")

    mock_is_running.return_value = True

    assert is_axe_running() is True
    mock_is_running.assert_called_once_with(12345)


@patch("axe.process.is_process_running")
def test_is_axe_running_returns_false_and_cleans_stale_pid(
    mock_is_running: MagicMock,
    temp_state_dir: Path,
) -> None:
    """Test is_axe_running returns False and cleans up stale PID file."""
    # Create stale PID file
    pid_file = temp_state_dir / "pid"
    pid_file.write_text("12345")

    mock_is_running.return_value = False

    assert is_axe_running() is False
    # PID file should be cleaned up
    assert not pid_file.exists()


# --- stop_axe_daemon Tests ---


def test_stop_axe_daemon_returns_false_when_no_pid_file(
    temp_state_dir: Path,
) -> None:
    """Test stop_axe_daemon returns False when no PID file exists."""
    assert stop_axe_daemon() is False


@patch("axe.process.is_process_running")
def test_stop_axe_daemon_returns_false_when_process_dead(
    mock_is_running: MagicMock,
    temp_state_dir: Path,
) -> None:
    """Test stop_axe_daemon returns False when process is already dead."""
    pid_file = temp_state_dir / "pid"
    pid_file.write_text("12345")

    mock_is_running.return_value = False

    assert stop_axe_daemon() is False
    # PID file should be cleaned up
    assert not pid_file.exists()


@patch("axe.process.os.kill")
@patch("axe.process.is_process_running")
def test_stop_axe_daemon_sends_sigterm(
    mock_is_running: MagicMock,
    mock_kill: MagicMock,
    temp_state_dir: Path,
) -> None:
    """Test stop_axe_daemon sends SIGTERM to the process."""
    import signal

    pid_file = temp_state_dir / "pid"
    pid_file.write_text("12345")

    mock_is_running.return_value = True

    assert stop_axe_daemon() is True
    mock_kill.assert_called_once_with(12345, signal.SIGTERM)


@patch("axe.process.os.kill")
@patch("axe.process.is_process_running")
def test_stop_axe_daemon_handles_process_not_found(
    mock_is_running: MagicMock,
    mock_kill: MagicMock,
    temp_state_dir: Path,
) -> None:
    """Test stop_axe_daemon handles ProcessLookupError."""
    pid_file = temp_state_dir / "pid"
    pid_file.write_text("12345")

    mock_is_running.return_value = True
    mock_kill.side_effect = ProcessLookupError

    assert stop_axe_daemon() is False
    # PID file should be cleaned up
    assert not pid_file.exists()


# --- get_axe_status Tests ---


def test_get_axe_status_returns_none_when_no_pid_file(
    temp_state_dir: Path,
) -> None:
    """Test get_axe_status returns None when no PID file exists."""
    assert get_axe_status() is None


@patch("axe.process.is_process_running")
def test_get_axe_status_returns_none_when_process_dead(
    mock_is_running: MagicMock,
    temp_state_dir: Path,
) -> None:
    """Test get_axe_status returns None when process is dead."""
    pid_file = temp_state_dir / "pid"
    pid_file.write_text("12345")

    mock_is_running.return_value = False

    assert get_axe_status() is None
    # PID file should be cleaned up
    assert not pid_file.exists()


@patch("axe.process.is_process_running")
def test_get_axe_status_returns_basic_status_when_no_status_file(
    mock_is_running: MagicMock,
    temp_state_dir: Path,
) -> None:
    """Test get_axe_status returns basic status when no status.json exists."""
    pid_file = temp_state_dir / "pid"
    pid_file.write_text("12345")

    mock_is_running.return_value = True

    status = get_axe_status()
    assert status is not None
    assert status["pid"] == 12345
    assert "initializing" in status["status"]


@patch("axe.process.is_process_running")
@patch("axe.process.read_status")
def test_get_axe_status_returns_full_status(
    mock_read_status: MagicMock,
    mock_is_running: MagicMock,
    temp_state_dir: Path,
) -> None:
    """Test get_axe_status returns full status from status.json."""
    pid_file = temp_state_dir / "pid"
    pid_file.write_text("12345")

    mock_is_running.return_value = True
    mock_read_status.return_value = AxeStatus(
        pid=12345,
        started_at="2025-01-15T10:00:00-05:00",
        status="running",
        full_check_interval=300,
        hook_interval=1,
        max_runners=5,
        query="test query",
        zombie_timeout=7200,
        current_runners=2,
        last_full_cycle="2025-01-15T10:00:00-05:00",
        last_hook_cycle="2025-01-15T10:00:05-05:00",
        next_full_cycle="2025-01-15T10:05:00-05:00",
        total_changespecs=10,
        filtered_changespecs=8,
        uptime_seconds=300,
    )

    status = get_axe_status()
    assert status is not None
    assert status["pid"] == 12345
    assert status["status"] == "running"
    assert status["max_runners"] == 5
    assert status["query"] == "test query"
    assert status["uptime_seconds"] == 300


# --- get_axe_pid Tests ---


def test_get_axe_pid_returns_none_when_no_pid_file(
    temp_state_dir: Path,
) -> None:
    """Test get_axe_pid returns None when no PID file exists."""
    assert get_axe_pid() is None


@patch("axe.process.is_process_running")
def test_get_axe_pid_returns_pid_when_running(
    mock_is_running: MagicMock,
    temp_state_dir: Path,
) -> None:
    """Test get_axe_pid returns PID when process is running."""
    pid_file = temp_state_dir / "pid"
    pid_file.write_text("12345")

    mock_is_running.return_value = True

    assert get_axe_pid() == 12345


@patch("axe.process.is_process_running")
def test_get_axe_pid_returns_none_and_cleans_stale_pid(
    mock_is_running: MagicMock,
    temp_state_dir: Path,
) -> None:
    """Test get_axe_pid returns None and cleans up stale PID file."""
    pid_file = temp_state_dir / "pid"
    pid_file.write_text("12345")

    mock_is_running.return_value = False

    assert get_axe_pid() is None
    # PID file should be cleaned up
    assert not pid_file.exists()
