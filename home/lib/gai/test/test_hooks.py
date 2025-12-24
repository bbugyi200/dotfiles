"""Tests for HOOKS field parsing and hooks module."""

import os
import tempfile

from work.changespec import HookEntry, HookStatusLine, _parse_changespec_from_lines
from work.hooks import (
    _calculate_duration_from_timestamps,
    _format_duration,
    _format_hooks_field,
    _format_timestamp_display,
    _get_hooks_directory,
    get_failing_hooks,
    get_failing_test_target_hooks,
    get_hook_output_path,
    get_test_target_from_hook,
    has_failing_hooks,
    has_failing_test_target_hooks,
    has_running_hooks,
    hook_needs_run,
    update_changespec_hooks_field,
)


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


# Tests for HookEntry dataclass
def test_hook_entry_all_fields() -> None:
    """Test HookEntry with all fields via status_lines."""
    entry = _make_hook(
        command="flake8 src",
        timestamp="240601123456",
        status="PASSED",
        duration="1m23s",
    )
    assert entry.command == "flake8 src"
    assert entry.timestamp == "240601123456"
    assert entry.status == "PASSED"
    assert entry.duration == "1m23s"


def test_hook_entry_minimal() -> None:
    """Test HookEntry with only command (never run)."""
    entry = HookEntry(command="mypy src")
    assert entry.command == "mypy src"
    assert entry.timestamp is None
    assert entry.status is None
    assert entry.duration is None


def test_hook_entry_running() -> None:
    """Test HookEntry in RUNNING state (no duration)."""
    entry = _make_hook(
        command="pytest src",
        timestamp="240601123456",
        status="RUNNING",
        duration=None,
    )
    assert entry.command == "pytest src"
    assert entry.timestamp == "240601123456"
    assert entry.status == "RUNNING"
    assert entry.duration is None


# Tests for HOOKS field parsing
def test_parse_changespec_with_hooks() -> None:
    """Test parsing ChangeSpec with HOOKS field."""
    lines = [
        "## ChangeSpec\n",
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  flake8 src\n",
        "    [240601_123456] PASSED (1m23s)\n",
        "  mypy src\n",
        "    [240601_123456] RUNNING\n",
        "  pylint src\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.name == "test_cl"
    assert changespec.hooks is not None
    assert len(changespec.hooks) == 3

    # Check first hook (PASSED with duration)
    assert changespec.hooks[0].command == "flake8 src"
    assert changespec.hooks[0].timestamp == "240601123456"
    assert changespec.hooks[0].status == "PASSED"
    assert changespec.hooks[0].duration == "1m23s"

    # Check second hook (RUNNING, no duration)
    assert changespec.hooks[1].command == "mypy src"
    assert changespec.hooks[1].timestamp == "240601123456"
    assert changespec.hooks[1].status == "RUNNING"
    assert changespec.hooks[1].duration is None

    # Check third hook (never run)
    assert changespec.hooks[2].command == "pylint src"
    assert changespec.hooks[2].timestamp is None
    assert changespec.hooks[2].status is None
    assert changespec.hooks[2].duration is None


def test_parse_changespec_without_hooks() -> None:
    """Test parsing ChangeSpec without HOOKS field."""
    lines = [
        "## ChangeSpec\n",
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.name == "test_cl"
    assert changespec.hooks is None


def test_parse_changespec_hooks_with_failed_status() -> None:
    """Test parsing HOOKS with FAILED status."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  pytest src\n",
        "    [240601_123456] FAILED (5m30s)\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.hooks is not None
    assert len(changespec.hooks) == 1
    assert changespec.hooks[0].command == "pytest src"
    assert changespec.hooks[0].status == "FAILED"
    assert changespec.hooks[0].duration == "5m30s"


def test_parse_changespec_hooks_with_zombie_status() -> None:
    """Test parsing HOOKS with ZOMBIE status."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  pytest src\n",
        "    [240601_123456] ZOMBIE (24h0m)\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.hooks is not None
    assert len(changespec.hooks) == 1
    assert changespec.hooks[0].command == "pytest src"
    assert changespec.hooks[0].status == "ZOMBIE"
    assert changespec.hooks[0].duration == "24h0m"


# Tests for hook utility functions
def test_get_hooks_directory() -> None:
    """Test getting hooks directory path."""
    expected = os.path.expanduser("~/.gai/hooks")
    assert _get_hooks_directory() == expected


def test_format_duration_seconds_only() -> None:
    """Test formatting duration with only seconds."""
    assert _format_duration(45) == "45s"
    assert _format_duration(0) == "0s"
    assert _format_duration(59) == "59s"


def test_format_duration_with_minutes() -> None:
    """Test formatting duration with minutes and seconds."""
    assert _format_duration(60) == "1m0s"
    assert _format_duration(83) == "1m23s"


def test_format_duration_with_hours() -> None:
    """Test formatting duration with hours, minutes, and seconds."""
    assert _format_duration(3600) == "1h0m0s"
    assert _format_duration(3661) == "1h1m1s"
    assert _format_duration(7323) == "2h2m3s"
    assert _format_duration(86400) == "24h0m0s"  # 24 hours


def test_format_duration_fractional() -> None:
    """Test formatting duration with fractional seconds (truncated)."""
    assert _format_duration(45.9) == "45s"
    assert _format_duration(83.7) == "1m23s"


# Tests for _calculate_duration_from_timestamps
def test_calculate_duration_from_timestamps_basic() -> None:
    """Test calculating duration between two timestamps."""
    # 1 minute apart
    start = "240601120000"  # 12:00:00
    end = "240601120100"  # 12:01:00
    assert _calculate_duration_from_timestamps(start, end) == 60.0


def test_calculate_duration_from_timestamps_hours() -> None:
    """Test calculating duration with hours difference."""
    start = "240601120000"  # 12:00:00
    end = "240601140000"  # 14:00:00
    assert _calculate_duration_from_timestamps(start, end) == 7200.0  # 2 hours


def test_calculate_duration_from_timestamps_complex() -> None:
    """Test calculating duration with hours, minutes, and seconds."""
    start = "240601120000"  # 12:00:00
    end = "240601132345"  # 13:23:45
    # 1h 23m 45s = 3600 + 1380 + 45 = 5025 seconds
    assert _calculate_duration_from_timestamps(start, end) == 5025.0


def test_calculate_duration_from_timestamps_same() -> None:
    """Test calculating duration when timestamps are the same."""
    timestamp = "240601120000"
    assert _calculate_duration_from_timestamps(timestamp, timestamp) == 0.0


def test_calculate_duration_from_timestamps_invalid() -> None:
    """Test that invalid timestamps return None."""
    assert _calculate_duration_from_timestamps("invalid", "240601120000") is None
    assert _calculate_duration_from_timestamps("240601120000", "invalid") is None
    assert _calculate_duration_from_timestamps("", "") is None


# Tests for hook_needs_run
def test_hook_needs_run_never_run() -> None:
    """Test that hook needs run if never run before."""
    hook = HookEntry(command="flake8 src")
    # Hook needs run if no status line exists for history entry 1
    assert hook_needs_run(hook, 1) is True


def test_hook_needs_run_no_history_entry() -> None:
    """Test that hook doesn't need run if no history entry number."""
    hook = HookEntry(command="flake8 src")
    # No history entry means no run needed
    assert hook_needs_run(hook, None) is False

    hook2 = _make_hook(
        command="flake8 src",
        history_entry_num=1,
        timestamp="240601123456",
        status="PASSED",
    )
    assert hook_needs_run(hook2, None) is False  # No history entry


def test_hook_needs_run_stale() -> None:
    """Test that hook needs run if no status line for current history entry."""
    # Hook has status line for history entry 1, but we want entry 2
    hook = _make_hook(
        command="flake8 src",
        history_entry_num=1,
        timestamp="240601100000",
        status="PASSED",
    )
    assert hook_needs_run(hook, 2) is True  # No status for entry 2


def test_hook_needs_run_up_to_date() -> None:
    """Test that hook doesn't need run if status line exists for current entry."""
    hook = _make_hook(
        command="flake8 src",
        history_entry_num=1,
        timestamp="240601130000",
        status="PASSED",
    )
    assert hook_needs_run(hook, 1) is False  # Has status for entry 1


def test_hook_needs_run_same_entry() -> None:
    """Test that hook doesn't need run if status line exists for same entry."""
    hook = _make_hook(
        command="flake8 src",
        history_entry_num=2,
        timestamp="240601123456",
        status="PASSED",
    )
    assert hook_needs_run(hook, 2) is False  # Has status for entry 2


# Tests for test target hook functions
def test_get_test_target_from_hook_valid() -> None:
    """Test extracting test target from a valid test target hook."""
    hook = _make_hook(command="bb_rabbit_test //foo/bar:test1", status="PASSED")
    assert get_test_target_from_hook(hook) == "//foo/bar:test1"


def test_get_test_target_from_hook_with_spaces() -> None:
    """Test extracting test target from hook with extra spaces."""
    hook = _make_hook(command="bb_rabbit_test  //foo/bar:test1 ", status="PASSED")
    assert get_test_target_from_hook(hook) == "//foo/bar:test1"


def test_get_test_target_from_hook_not_test_target() -> None:
    """Test that non-test target hook returns None."""
    hook = _make_hook(command="flake8 src", status="PASSED")
    assert get_test_target_from_hook(hook) is None


def test_get_failing_test_target_hooks_mixed() -> None:
    """Test getting failing test target hooks from mixed list."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="FAILED"),
        _make_hook(command="bb_rabbit_test //foo:test2", status="PASSED"),
        _make_hook(command="flake8 src", status="FAILED"),
        _make_hook(command="bb_rabbit_test //bar:test3", status="FAILED"),
    ]
    failing = get_failing_test_target_hooks(hooks)
    assert len(failing) == 2
    assert failing[0].command == "bb_rabbit_test //foo:test1"
    assert failing[1].command == "bb_rabbit_test //bar:test3"


def test_get_failing_test_target_hooks_none_failing() -> None:
    """Test that empty list is returned when no failing test target hooks."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="PASSED"),
        _make_hook(command="flake8 src", status="FAILED"),
    ]
    failing = get_failing_test_target_hooks(hooks)
    assert failing == []


def test_has_failing_test_target_hooks_true() -> None:
    """Test has_failing_test_target_hooks returns True when failing hooks exist."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="FAILED"),
        _make_hook(command="bb_rabbit_test //foo:test2", status="PASSED"),
    ]
    assert has_failing_test_target_hooks(hooks) is True


def test_has_failing_test_target_hooks_false() -> None:
    """Test has_failing_test_target_hooks returns False when no failing hooks."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="PASSED"),
        _make_hook(command="flake8 src", status="FAILED"),
    ]
    assert has_failing_test_target_hooks(hooks) is False


def test_has_failing_test_target_hooks_none() -> None:
    """Test has_failing_test_target_hooks returns False for None input."""
    assert has_failing_test_target_hooks(None) is False


def test_has_failing_test_target_hooks_empty() -> None:
    """Test has_failing_test_target_hooks returns False for empty list."""
    assert has_failing_test_target_hooks([]) is False


# Tests for get_failing_hooks and has_failing_hooks
def test_get_failing_hooks_mixed() -> None:
    """Test getting all failing hooks from mixed list."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="FAILED"),
        _make_hook(command="bb_rabbit_test //foo:test2", status="PASSED"),
        _make_hook(command="flake8 src", status="FAILED"),
        _make_hook(command="mypy src", status="PASSED"),
        _make_hook(command="bb_rabbit_test //bar:test3", status="FAILED"),
    ]
    failing = get_failing_hooks(hooks)
    assert len(failing) == 3
    assert failing[0].command == "bb_rabbit_test //foo:test1"
    assert failing[1].command == "flake8 src"
    assert failing[2].command == "bb_rabbit_test //bar:test3"


def test_get_failing_hooks_none_failing() -> None:
    """Test that empty list is returned when no failing hooks."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="PASSED"),
        _make_hook(command="flake8 src", status="PASSED"),
    ]
    failing = get_failing_hooks(hooks)
    assert failing == []


def test_get_failing_hooks_empty_list() -> None:
    """Test that empty list is returned for empty input."""
    assert get_failing_hooks([]) == []


def test_has_failing_hooks_true() -> None:
    """Test has_failing_hooks returns True when failing hooks exist."""
    hooks = [
        _make_hook(command="flake8 src", status="FAILED"),
        _make_hook(command="mypy src", status="PASSED"),
    ]
    assert has_failing_hooks(hooks) is True


def test_has_failing_hooks_false() -> None:
    """Test has_failing_hooks returns False when no failing hooks."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="PASSED"),
        _make_hook(command="flake8 src", status="PASSED"),
    ]
    assert has_failing_hooks(hooks) is False


def test_has_failing_hooks_none() -> None:
    """Test has_failing_hooks returns False for None input."""
    assert has_failing_hooks(None) is False


def test_has_failing_hooks_empty() -> None:
    """Test has_failing_hooks returns False for empty list."""
    assert has_failing_hooks([]) is False


# Tests for has_running_hooks
def test_has_running_hooks_true() -> None:
    """Test has_running_hooks returns True when running hooks exist."""
    hooks = [
        _make_hook(command="flake8 src", status="RUNNING", timestamp="240601123456"),
        _make_hook(command="mypy src", status="PASSED"),
    ]
    assert has_running_hooks(hooks) is True


def test_has_running_hooks_false() -> None:
    """Test has_running_hooks returns False when no running hooks."""
    hooks = [
        _make_hook(command="flake8 src", status="PASSED"),
        _make_hook(command="mypy src", status="FAILED"),
    ]
    assert has_running_hooks(hooks) is False


def test_has_running_hooks_none() -> None:
    """Test has_running_hooks returns False for None input."""
    assert has_running_hooks(None) is False


def test_has_running_hooks_empty() -> None:
    """Test has_running_hooks returns False for empty list."""
    assert has_running_hooks([]) is False


# Tests for get_hook_output_path
def test_get_hook_output_path_basic() -> None:
    """Test get_hook_output_path returns correct path."""
    path = get_hook_output_path("my_feature", "240601123456")
    hooks_dir = _get_hooks_directory()
    assert path == os.path.join(hooks_dir, "my_feature_240601123456.txt")


def test_get_hook_output_path_special_chars() -> None:
    """Test get_hook_output_path sanitizes special characters."""
    path = get_hook_output_path("my/feature-test", "240601123456")
    hooks_dir = _get_hooks_directory()
    # Special chars should be replaced with underscore
    assert path == os.path.join(hooks_dir, "my_feature_test_240601123456.txt")


def test_get_failing_hooks_multiple_statuses() -> None:
    """Test getting failing hooks with various status combinations."""
    hooks = [
        _make_hook(command="hook1", status="FAILED"),
        _make_hook(command="hook2", status="PASSED"),
        _make_hook(command="hook3", status="RUNNING"),
        _make_hook(command="hook4", status="ZOMBIE"),
        _make_hook(command="hook5", status="FAILED"),
        HookEntry(command="hook6"),  # Never run (no status lines)
    ]
    failing = get_failing_hooks(hooks)
    # Only FAILED status hooks should be returned
    assert len(failing) == 2
    assert failing[0].command == "hook1"
    assert failing[1].command == "hook5"


def test_get_failing_test_target_hooks_with_zombie() -> None:
    """Test that only FAILED test targets are returned, not ZOMBIE."""
    hooks = [
        _make_hook(command="bb_rabbit_test //foo:test1", status="FAILED"),
        _make_hook(command="bb_rabbit_test //foo:test2", status="ZOMBIE"),
        _make_hook(command="bb_rabbit_test //foo:test3", status="RUNNING"),
    ]
    failing = get_failing_test_target_hooks(hooks)
    # Only FAILED test target hooks should be returned
    assert len(failing) == 1
    assert failing[0].command == "bb_rabbit_test //foo:test1"


# Tests for _format_timestamp_display
def test_format_timestamp_display_basic() -> None:
    """Test formatting timestamp for display."""
    result = _format_timestamp_display("240601123456")
    # Format: [YYmmdd_HHMMSS]
    assert result == "[240601_123456]"


def test_format_timestamp_display_short() -> None:
    """Test formatting short timestamp."""
    result = _format_timestamp_display("2406")
    # Should handle short timestamps gracefully
    assert "[2406" in result


# Tests for _format_hooks_field
def test_format_hooks_field_basic() -> None:
    """Test formatting hooks field for writing."""
    hooks = [
        HookEntry(command="flake8 src"),
        _make_hook(
            command="pytest tests",
            timestamp="240601123456",
            status="PASSED",
            duration="1m23s",
        ),
    ]
    result = _format_hooks_field(hooks)
    # Result is a list of lines
    result_str = "".join(result)
    assert "HOOKS:" in result_str
    assert "  flake8 src" in result_str
    assert "  pytest tests" in result_str
    # New format includes (N) prefix
    assert "(1) [240601_123456] PASSED (1m23s)" in result_str


def test_format_hooks_field_running_no_duration() -> None:
    """Test formatting hooks field with RUNNING status (no duration)."""
    hooks = [
        _make_hook(
            command="pytest tests",
            timestamp="240601123456",
            status="RUNNING",
            duration=None,
        ),
    ]
    result = _format_hooks_field(hooks)
    result_str = "".join(result)
    assert "  pytest tests" in result_str
    # New format includes (N) prefix
    assert "(1) [240601_123456] RUNNING" in result_str
    # Should not have duration
    assert "RUNNING (" not in result_str


def test_format_hooks_field_empty() -> None:
    """Test formatting empty hooks list."""
    result = _format_hooks_field([])
    assert result == []


# Tests for update_changespec_hooks_field
def test_update_changespec_hooks_field_basic() -> None:
    """Test updating hooks field in a project file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(
            """## ChangeSpec
NAME: test_cl
DESCRIPTION:
  Test description
STATUS: Drafted
HOOKS:
  old_command
    (1) [240601_100000] PASSED (1m0s)
"""
        )
        f.flush()
        file_path = f.name

    try:
        # Update hooks
        new_hooks = [
            _make_hook(
                command="new_command",
                timestamp="240601123456",
                status="FAILED",
                duration="2m30s",
            ),
        ]
        success = update_changespec_hooks_field(file_path, "test_cl", new_hooks)
        assert success is True

        # Verify the file was updated
        with open(file_path) as f:
            content = f.read()
        assert "new_command" in content
        # New format with (N) prefix
        assert "(1) [240601_123456] FAILED (2m30s)" in content
        # Old hook should be gone
        assert "old_command" not in content
    finally:
        os.unlink(file_path)


def test_update_changespec_hooks_field_clear_status() -> None:
    """Test clearing hook status (for rerun)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(
            """## ChangeSpec
NAME: test_cl
DESCRIPTION:
  Test description
STATUS: Drafted
HOOKS:
  my_command
    (1) [240601_100000] FAILED (1m0s)
"""
        )
        f.flush()
        file_path = f.name

    try:
        # Clear hook status (simulating rerun) - no status lines
        new_hooks = [HookEntry(command="my_command")]
        success = update_changespec_hooks_field(file_path, "test_cl", new_hooks)
        assert success is True

        # Verify status was cleared
        with open(file_path) as f:
            content = f.read()
        assert "my_command" in content
        # Status line should be gone
        assert "[240601_100000]" not in content
        assert "FAILED" not in content
    finally:
        os.unlink(file_path)


def test_update_changespec_hooks_field_delete_hook() -> None:
    """Test deleting a hook entirely."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(
            """## ChangeSpec
NAME: test_cl
DESCRIPTION:
  Test description
STATUS: Drafted
HOOKS:
  hook1
    (1) [240601_100000] PASSED (1m0s)
  hook2
    (1) [240601_100000] FAILED (2m0s)
"""
        )
        f.flush()
        file_path = f.name

    try:
        # Delete hook1, keep hook2
        new_hooks = [
            _make_hook(
                command="hook2",
                timestamp="240601100000",
                status="FAILED",
                duration="2m0s",
            ),
        ]
        success = update_changespec_hooks_field(file_path, "test_cl", new_hooks)
        assert success is True

        # Verify hook1 was deleted
        with open(file_path) as f:
            content = f.read()
        assert "hook1" not in content
        assert "hook2" in content
    finally:
        os.unlink(file_path)
