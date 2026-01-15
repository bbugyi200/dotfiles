"""Tests for the axe state management module."""

import json
import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from axe.state import (
    AxeMetrics,
    AxeStatus,
    CycleResult,
    _atomic_write_json,
    _read_json,
    append_error,
    get_timestamp,
    read_cycle_result,
    read_errors,
    read_metrics,
    read_pid_file,
    read_status,
    remove_pid_file,
    write_cycle_result,
    write_metrics,
    write_pid_file,
    write_status,
)


@pytest.fixture
def temp_state_dir(tmp_path: Path) -> Iterator[Path]:
    """Create a temporary state directory for testing."""
    state_dir = tmp_path / ".gai" / "axe"
    with patch("axe.state.AXE_STATE_DIR", state_dir):
        yield state_dir


# --- PID File Tests ---


def test_write_pid_file_creates_file(temp_state_dir: Path) -> None:
    """Test that write_pid_file creates a PID file with current PID."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        write_pid_file()
        pid_file = temp_state_dir / "pid"
        assert pid_file.exists()
        assert int(pid_file.read_text().strip()) == os.getpid()


def test_read_pid_file_returns_pid(temp_state_dir: Path) -> None:
    """Test that read_pid_file returns the PID from the file."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        temp_state_dir.mkdir(parents=True, exist_ok=True)
        pid_file = temp_state_dir / "pid"
        pid_file.write_text("12345")
        assert read_pid_file() == 12345


def test_read_pid_file_returns_none_when_missing(temp_state_dir: Path) -> None:
    """Test that read_pid_file returns None when file doesn't exist."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        assert read_pid_file() is None


def test_read_pid_file_returns_none_on_invalid_content(temp_state_dir: Path) -> None:
    """Test that read_pid_file returns None on invalid content."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        temp_state_dir.mkdir(parents=True, exist_ok=True)
        pid_file = temp_state_dir / "pid"
        pid_file.write_text("not_a_number")
        assert read_pid_file() is None


def test_remove_pid_file_removes_file(temp_state_dir: Path) -> None:
    """Test that remove_pid_file removes the PID file."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        temp_state_dir.mkdir(parents=True, exist_ok=True)
        pid_file = temp_state_dir / "pid"
        pid_file.write_text("12345")
        assert pid_file.exists()
        remove_pid_file()
        assert not pid_file.exists()


def test_remove_pid_file_no_error_when_missing(temp_state_dir: Path) -> None:
    """Test that remove_pid_file doesn't error when file is missing."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        # Should not raise
        remove_pid_file()


# --- Status Tests ---


def test_write_and_read_status(temp_state_dir: Path) -> None:
    """Test writing and reading status."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        status = AxeStatus(
            pid=12345,
            started_at="2025-01-15T10:00:00-05:00",
            status="running",
            full_check_interval=300,
            hook_interval=1,
            max_runners=5,
            query="",
            zombie_timeout=7200,
            current_runners=2,
            last_full_cycle="2025-01-15T10:00:00-05:00",
            last_hook_cycle="2025-01-15T10:00:05-05:00",
            next_full_cycle="2025-01-15T10:05:00-05:00",
            total_changespecs=10,
            filtered_changespecs=8,
            uptime_seconds=300,
        )
        write_status(status)

        result = read_status()
        assert result is not None
        assert result.pid == 12345
        assert result.status == "running"
        assert result.max_runners == 5
        assert result.uptime_seconds == 300


def test_read_status_returns_none_when_missing(temp_state_dir: Path) -> None:
    """Test that read_status returns None when file doesn't exist."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        assert read_status() is None


def test_read_status_returns_none_on_invalid_json(temp_state_dir: Path) -> None:
    """Test that read_status returns None on invalid JSON."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        temp_state_dir.mkdir(parents=True, exist_ok=True)
        status_file = temp_state_dir / "status.json"
        status_file.write_text("not valid json")
        assert read_status() is None


# --- Cycle Result Tests ---


def test_write_and_read_full_cycle_result(temp_state_dir: Path) -> None:
    """Test writing and reading full cycle result."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        result = CycleResult(
            timestamp="2025-01-15T10:00:00-05:00",
            cycle_type="full",
            duration_ms=1234,
            changespecs_processed=10,
            updates=[{"changespec": "test", "message": "update"}],
            errors=[],
        )
        write_cycle_result(result)

        read_result = read_cycle_result("full")
        assert read_result is not None
        assert read_result.cycle_type == "full"
        assert read_result.duration_ms == 1234
        assert len(read_result.updates) == 1


def test_write_and_read_hook_cycle_result(temp_state_dir: Path) -> None:
    """Test writing and reading hook cycle result."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        result = CycleResult(
            timestamp="2025-01-15T10:00:05-05:00",
            cycle_type="hook",
            duration_ms=45,
            changespecs_processed=10,
            updates=[],
            errors=[],
        )
        write_cycle_result(result)

        read_result = read_cycle_result("hook")
        assert read_result is not None
        assert read_result.cycle_type == "hook"
        assert read_result.duration_ms == 45


def test_read_cycle_result_returns_none_when_missing(temp_state_dir: Path) -> None:
    """Test that read_cycle_result returns None when file doesn't exist."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        assert read_cycle_result("full") is None
        assert read_cycle_result("hook") is None


# --- Metrics Tests ---


def test_write_and_read_metrics(temp_state_dir: Path) -> None:
    """Test writing and reading metrics."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        metrics = AxeMetrics(
            full_cycles_run=100,
            hook_cycles_run=30000,
            total_updates=450,
            hooks_started=120,
            hooks_completed=118,
            mentors_started=25,
            mentors_completed=25,
            workflows_started=50,
            workflows_completed=48,
            zombies_detected=2,
            errors_encountered=5,
        )
        write_metrics(metrics)

        result = read_metrics()
        assert result is not None
        assert result.full_cycles_run == 100
        assert result.hooks_started == 120
        assert result.errors_encountered == 5


def test_read_metrics_returns_none_when_missing(temp_state_dir: Path) -> None:
    """Test that read_metrics returns None when file doesn't exist."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        assert read_metrics() is None


def test_axe_metrics_default_values() -> None:
    """Test that AxeMetrics has sensible default values."""
    metrics = AxeMetrics()
    assert metrics.full_cycles_run == 0
    assert metrics.hook_cycles_run == 0
    assert metrics.total_updates == 0
    assert metrics.errors_encountered == 0


# --- Error Tests ---


def test_append_and_read_errors(temp_state_dir: Path) -> None:
    """Test appending and reading errors."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        append_error({"timestamp": "t1", "job": "hooks", "error": "error 1"})
        append_error({"timestamp": "t2", "job": "mentors", "error": "error 2"})

        errors = read_errors()
        assert len(errors) == 2
        assert errors[0]["job"] == "hooks"
        assert errors[1]["job"] == "mentors"


def test_errors_are_limited_to_100(temp_state_dir: Path) -> None:
    """Test that errors are limited to the last 100."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        # Add 150 errors
        for i in range(150):
            append_error({"timestamp": f"t{i}", "job": "test", "error": f"error {i}"})

        errors = read_errors()
        assert len(errors) == 100
        # Should have errors 50-149 (the last 100)
        assert errors[0]["error"] == "error 50"
        assert errors[-1]["error"] == "error 149"


def test_read_errors_returns_empty_list_when_missing(temp_state_dir: Path) -> None:
    """Test that read_errors returns empty list when file doesn't exist."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        assert read_errors() == []


# --- Utility Tests ---


def test_get_timestamp_returns_iso_format() -> None:
    """Test that get_timestamp returns ISO formatted string."""
    timestamp = get_timestamp()
    # Should be parseable ISO format with timezone
    assert "T" in timestamp
    assert "-" in timestamp or "+" in timestamp  # Has timezone offset


# --- Atomic Write Tests ---


def test_atomic_write_json_creates_file(temp_state_dir: Path) -> None:
    """Test that _atomic_write_json creates a file atomically."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        test_file = temp_state_dir / "test.json"
        data = {"key": "value", "number": 42}

        _atomic_write_json(test_file, data)

        assert test_file.exists()
        with open(test_file) as f:
            result = json.load(f)
        assert result == data


def test_atomic_write_json_no_temp_file_remains(temp_state_dir: Path) -> None:
    """Test that _atomic_write_json doesn't leave temp files."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        test_file = temp_state_dir / "test.json"
        _atomic_write_json(test_file, {"key": "value"})

        # No .tmp file should remain
        tmp_file = test_file.with_suffix(".tmp")
        assert not tmp_file.exists()


def test_atomic_write_json_handles_list(temp_state_dir: Path) -> None:
    """Test that _atomic_write_json handles lists."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        test_file = temp_state_dir / "test.json"
        data = [{"a": 1}, {"b": 2}]

        _atomic_write_json(test_file, data)

        assert test_file.exists()
        with open(test_file) as f:
            result = json.load(f)
        assert result == data


# --- read_json Tests ---


def test_read_json_returns_dict(temp_state_dir: Path) -> None:
    """Test that _read_json returns parsed JSON."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        temp_state_dir.mkdir(parents=True, exist_ok=True)
        test_file = temp_state_dir / "test.json"
        test_file.write_text('{"key": "value"}')

        result = _read_json(test_file)
        assert result == {"key": "value"}


def test_read_json_returns_none_for_missing_file(temp_state_dir: Path) -> None:
    """Test that _read_json returns None for missing file."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        test_file = temp_state_dir / "nonexistent.json"
        assert _read_json(test_file) is None


def test_read_json_returns_none_for_invalid_json(temp_state_dir: Path) -> None:
    """Test that _read_json returns None for invalid JSON."""
    with patch("axe.state.AXE_STATE_DIR", temp_state_dir):
        temp_state_dir.mkdir(parents=True, exist_ok=True)
        test_file = temp_state_dir / "test.json"
        test_file.write_text("not valid json")

        assert _read_json(test_file) is None
