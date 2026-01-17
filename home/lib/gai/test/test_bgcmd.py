"""Tests for the bgcmd module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from ace.tui.bgcmd import (
    BGCMD_STATE_DIR,
    MAX_SLOTS,
    BackgroundCommandInfo,
    _ensure_slot_dir,
    _get_slot_dir,
    _is_process_running,
    _read_pid,
    _remove_pid,
    _write_info,
    _write_pid,
    clear_slot_output,
    find_first_available_slot,
    get_running_slots,
    get_slot_info,
    is_slot_running,
    read_slot_output_tail,
)


def test_get_slot_dir() -> None:
    """Test that _get_slot_dir returns correct path."""
    slot_dir = _get_slot_dir(5)
    assert slot_dir.name == "5"
    assert slot_dir.parent.name == "bgcmd"


def test_max_slots() -> None:
    """Test that MAX_SLOTS is 9."""
    assert MAX_SLOTS == 9


def test_write_and_read_pid() -> None:
    """Test writing and reading PID file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            _write_pid(1, 12345)
            pid = _read_pid(1)
            assert pid == 12345


def test_read_pid_not_exists() -> None:
    """Test reading PID when file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            pid = _read_pid(1)
            assert pid is None


def test_is_process_running_current_process() -> None:
    """Test _is_process_running returns True for current process."""
    import os

    assert _is_process_running(os.getpid()) is True


def test_is_process_running_invalid_pid() -> None:
    """Test _is_process_running returns False for invalid PID."""
    # PID 99999999 should not exist
    assert _is_process_running(99999999) is False


def test_is_slot_running_no_pid() -> None:
    """Test is_slot_running returns False when no PID file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            assert is_slot_running(1) is False


def test_get_slot_info_not_exists() -> None:
    """Test get_slot_info returns None when info.json doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            info = get_slot_info(1)
            assert info is None


def test_get_running_slots_empty() -> None:
    """Test get_running_slots returns empty list when no slots running."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            slots = get_running_slots()
            assert slots == []


def test_find_first_available_slot_all_available() -> None:
    """Test find_first_available_slot returns 1 when all slots available."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            slot = find_first_available_slot()
            assert slot == 1


def test_background_command_info_dataclass() -> None:
    """Test BackgroundCommandInfo dataclass."""
    info = BackgroundCommandInfo(
        command="make test",
        project="myproject",
        workspace_num=1,
        workspace_dir="/path/to/workspace",
        started_at="2025-01-01T12:00:00",
    )
    assert info.command == "make test"
    assert info.project == "myproject"
    assert info.workspace_num == 1
    assert info.workspace_dir == "/path/to/workspace"
    assert info.started_at == "2025-01-01T12:00:00"


def test_read_pid_invalid_content() -> None:
    """Test reading PID when file contains invalid content."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            slot_dir = Path(tmp_dir) / "1"
            slot_dir.mkdir(parents=True)
            (slot_dir / "pid").write_text("not_a_number")
            pid = _read_pid(1)
            assert pid is None


def test_get_slot_info_invalid_json() -> None:
    """Test get_slot_info when info.json contains invalid JSON."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            slot_dir = Path(tmp_dir) / "1"
            slot_dir.mkdir(parents=True)
            (slot_dir / "info.json").write_text("not valid json")
            info = get_slot_info(1)
            assert info is None


def test_get_slot_info_valid() -> None:
    """Test get_slot_info with valid info.json."""
    import json

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            slot_dir = Path(tmp_dir) / "1"
            slot_dir.mkdir(parents=True)
            info_data = {
                "command": "make test",
                "project": "myproject",
                "workspace_num": 1,
                "workspace_dir": "/path/to/workspace",
                "started_at": "2025-01-01T12:00:00",
            }
            (slot_dir / "info.json").write_text(json.dumps(info_data))
            info = get_slot_info(1)
            assert info is not None
            assert info.command == "make test"
            assert info.project == "myproject"


def test_get_slot_info_missing_fields() -> None:
    """Test get_slot_info when info.json has missing fields."""
    import json

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            slot_dir = Path(tmp_dir) / "1"
            slot_dir.mkdir(parents=True)
            info_data = {"command": "make test"}  # Missing other fields
            (slot_dir / "info.json").write_text(json.dumps(info_data))
            info = get_slot_info(1)
            assert info is None  # Should fail due to TypeError


def test_ensure_slot_dir() -> None:
    """Test that _ensure_slot_dir creates the directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            slot_dir = _ensure_slot_dir(5)
            assert slot_dir.exists()
            assert slot_dir.is_dir()


def test_remove_pid() -> None:
    """Test _remove_pid removes the pid file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            _write_pid(1, 12345)
            pid_file = Path(tmp_dir) / "1" / "pid"
            assert pid_file.exists()
            _remove_pid(1)
            assert not pid_file.exists()


def test_remove_pid_not_exists() -> None:
    """Test _remove_pid doesn't fail if pid file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            # This should not raise
            _remove_pid(1)


def test_read_slot_output_tail_empty() -> None:
    """Test read_slot_output_tail returns empty string when no output."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            output = read_slot_output_tail(1)
            assert output == ""


def test_read_slot_output_tail_with_content() -> None:
    """Test read_slot_output_tail returns content."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            slot_dir = Path(tmp_dir) / "1"
            slot_dir.mkdir(parents=True)
            (slot_dir / "output.log").write_text("line 1\nline 2\nline 3\n")
            output = read_slot_output_tail(1, lines=2)
            assert "line 2" in output
            assert "line 3" in output


def test_clear_slot_output() -> None:
    """Test clear_slot_output clears the output file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            slot_dir = Path(tmp_dir) / "1"
            slot_dir.mkdir(parents=True)
            output_file = slot_dir / "output.log"
            output_file.write_text("some output")
            assert output_file.read_text() == "some output"
            clear_slot_output(1)
            assert output_file.read_text() == ""


def test_clear_slot_output_not_exists() -> None:
    """Test clear_slot_output doesn't fail if file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            # This should not raise
            clear_slot_output(1)


def test_bgcmd_state_dir_is_path() -> None:
    """Test that BGCMD_STATE_DIR is a Path."""
    assert isinstance(BGCMD_STATE_DIR, Path)
    assert "bgcmd" in str(BGCMD_STATE_DIR)


def test_write_info() -> None:
    """Test _write_info writes info.json."""
    import json

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            info = BackgroundCommandInfo(
                command="make test",
                project="myproject",
                workspace_num=2,
                workspace_dir="/path/to/workspace",
                started_at="2025-01-01T12:00:00",
            )
            _write_info(1, info)
            info_file = Path(tmp_dir) / "1" / "info.json"
            assert info_file.exists()
            data = json.loads(info_file.read_text())
            assert data["command"] == "make test"
            assert data["project"] == "myproject"
            assert data["workspace_num"] == 2


def test_is_slot_running_dead_process() -> None:
    """Test is_slot_running returns False for dead process."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            # Write a PID for a non-existent process
            _write_pid(1, 99999999)
            assert is_slot_running(1) is False


def test_find_first_available_slot_some_used() -> None:
    """Test find_first_available_slot skips running slots."""
    import os

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            # Mark slot 1 as running (use current process PID)
            _write_pid(1, os.getpid())
            slot = find_first_available_slot()
            assert slot == 2  # Should return 2 since 1 is "running"


def test_get_running_slots_with_running() -> None:
    """Test get_running_slots returns slots with running processes."""
    import os

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            # Mark slots 1 and 3 as running
            _write_pid(1, os.getpid())
            _write_pid(3, os.getpid())
            # Mark slot 2 as dead
            _write_pid(2, 99999999)

            slots = get_running_slots()
            assert 1 in slots
            assert 3 in slots
            assert 2 not in slots


def test_find_first_available_slot_all_used() -> None:
    """Test find_first_available_slot returns None when all slots used."""
    import os

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            # Mark all 9 slots as running
            for i in range(1, 10):
                _write_pid(i, os.getpid())

            slot = find_first_available_slot()
            assert slot is None


def test_get_running_slots_filters_dead() -> None:
    """Test get_running_slots properly filters dead processes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            # Write PIDs for dead processes
            _write_pid(1, 99999999)
            _write_pid(2, 99999998)

            # Should return empty list since all processes are dead
            slots = get_running_slots()
            assert slots == []


def test_get_slot_info_with_extra_fields() -> None:
    """Test get_slot_info returns None for info.json with extra fields."""
    import json

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            slot_dir = Path(tmp_dir) / "1"
            slot_dir.mkdir(parents=True)
            info_data = {
                "command": "make test",
                "project": "myproject",
                "workspace_num": 1,
                "workspace_dir": "/path/to/workspace",
                "started_at": "2025-01-01T12:00:00",
                "extra_field": "causes TypeError",  # Extra field causes TypeError
            }
            (slot_dir / "info.json").write_text(json.dumps(info_data))
            # dataclass doesn't accept extra fields, returns None
            info = get_slot_info(1)
            assert info is None


def test_bgcmd_state_dir_path() -> None:
    """Test BGCMD_STATE_DIR is a proper Path under .gai/axe."""
    assert BGCMD_STATE_DIR.name == "bgcmd"
    assert "axe" in str(BGCMD_STATE_DIR)
    assert ".gai" in str(BGCMD_STATE_DIR)


def test_read_slot_output_tail_large_file() -> None:
    """Test read_slot_output_tail with many lines."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("ace.tui.bgcmd.BGCMD_STATE_DIR", Path(tmp_dir)):
            slot_dir = Path(tmp_dir) / "1"
            slot_dir.mkdir(parents=True)
            # Create a file with many lines
            lines = [f"line {i}\n" for i in range(100)]
            (slot_dir / "output.log").write_text("".join(lines))
            # Request only last 5 lines
            output = read_slot_output_tail(1, lines=5)
            assert "line 95" in output
            assert "line 99" in output
            # First lines should not be present
            assert "line 0\n" not in output
