"""Tests for HOOKS field parsing and hooks module."""

import os
import tempfile

# Private functions imported directly from their defining modules (allowed for tests)
from gai_utils import get_gai_directory
from search.changespec import (
    HookEntry,
    HookStatusLine,
    _parse_changespec_from_lines,
    parse_history_entry_id,
)

# Public functions via package __init__.py
from search.hooks import (
    calculate_duration_from_timestamps,
    format_duration,
    format_timestamp_display,
    generate_timestamp,
    get_failing_test_target_hooks,
    get_hook_output_path,
    get_test_target_from_hook,
    has_failing_test_target_hooks,
    has_running_hooks,
    hook_needs_run,
    is_suffix_stale,
    is_timestamp_suffix,
    update_changespec_hooks_field,
)
from search.hooks.operations import (
    _format_hooks_field,
)


def _make_hook(
    command: str,
    history_entry_num: str = "1",
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
    assert changespec.hooks[0].timestamp == "240601_123456"
    assert changespec.hooks[0].status == "PASSED"
    assert changespec.hooks[0].duration == "1m23s"

    # Check second hook (RUNNING, no duration)
    assert changespec.hooks[1].command == "mypy src"
    assert changespec.hooks[1].timestamp == "240601_123456"
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
    assert get_gai_directory("hooks") == expected


def testformat_duration_seconds_only() -> None:
    """Test formatting duration with only seconds."""
    assert format_duration(45) == "45s"
    assert format_duration(0) == "0s"
    assert format_duration(59) == "59s"


def testformat_duration_with_minutes() -> None:
    """Test formatting duration with minutes and seconds."""
    assert format_duration(60) == "1m0s"
    assert format_duration(83) == "1m23s"


def testformat_duration_with_hours() -> None:
    """Test formatting duration with hours, minutes, and seconds."""
    assert format_duration(3600) == "1h0m0s"
    assert format_duration(3661) == "1h1m1s"
    assert format_duration(7323) == "2h2m3s"
    assert format_duration(86400) == "24h0m0s"  # 24 hours


def testformat_duration_fractional() -> None:
    """Test formatting duration with fractional seconds (truncated)."""
    assert format_duration(45.9) == "45s"
    assert format_duration(83.7) == "1m23s"


# Tests for calculate_duration_from_timestamps
def testcalculate_duration_from_timestamps_basic() -> None:
    """Test calculating duration between two timestamps."""
    # 1 minute apart
    start = "240601120000"  # 12:00:00
    end = "240601120100"  # 12:01:00
    assert calculate_duration_from_timestamps(start, end) == 60.0


def testcalculate_duration_from_timestamps_hours() -> None:
    """Test calculating duration with hours difference."""
    start = "240601120000"  # 12:00:00
    end = "240601140000"  # 14:00:00
    assert calculate_duration_from_timestamps(start, end) == 7200.0  # 2 hours


def testcalculate_duration_from_timestamps_complex() -> None:
    """Test calculating duration with hours, minutes, and seconds."""
    start = "240601120000"  # 12:00:00
    end = "240601132345"  # 13:23:45
    # 1h 23m 45s = 3600 + 1380 + 45 = 5025 seconds
    assert calculate_duration_from_timestamps(start, end) == 5025.0


def testcalculate_duration_from_timestamps_same() -> None:
    """Test calculating duration when timestamps are the same."""
    timestamp = "240601120000"
    assert calculate_duration_from_timestamps(timestamp, timestamp) == 0.0


def testcalculate_duration_from_timestamps_invalid() -> None:
    """Test that invalid timestamps return None."""
    assert calculate_duration_from_timestamps("invalid", "240601120000") is None
    assert calculate_duration_from_timestamps("240601120000", "invalid") is None
    assert calculate_duration_from_timestamps("", "") is None


# Tests for parse_history_entry_id
def test_parse_history_entry_id_regular() -> None:
    """Test parsing regular history entry IDs (no letter)."""
    assert parse_history_entry_id("1") == (1, "")
    assert parse_history_entry_id("2") == (2, "")
    assert parse_history_entry_id("10") == (10, "")


def test_parse_history_entry_id_proposal() -> None:
    """Test parsing proposal history entry IDs (with letter)."""
    assert parse_history_entry_id("1a") == (1, "a")
    assert parse_history_entry_id("1b") == (1, "b")
    assert parse_history_entry_id("2a") == (2, "a")
    assert parse_history_entry_id("10z") == (10, "z")


def test_parse_history_entry_id_invalid() -> None:
    """Test parsing invalid history entry IDs."""
    # Fallback returns (0, original_string)
    assert parse_history_entry_id("abc") == (0, "abc")
    assert parse_history_entry_id("") == (0, "")


def test_parse_history_entry_id_sorting() -> None:
    """Test that parse_history_entry_id enables proper sorting."""
    # Sorting by tuple (number, letter) gives correct order
    ids = ["1a", "2", "1", "1b", "10", "2a"]
    sorted_ids = sorted(ids, key=parse_history_entry_id)
    assert sorted_ids == ["1", "1a", "1b", "2", "2a", "10"]


# Tests for hook_needs_run
def test_hook_needs_run_never_run() -> None:
    """Test that hook needs run if never run before."""
    hook = HookEntry(command="flake8 src")
    # Hook needs run if no status line exists for history entry 1
    assert hook_needs_run(hook, "1") is True


def test_hook_needs_run_no_history_entry() -> None:
    """Test that hook doesn't need run if no history entry number."""
    hook = HookEntry(command="flake8 src")
    # No history entry means no run needed
    assert hook_needs_run(hook, None) is False

    hook2 = _make_hook(
        command="flake8 src",
        history_entry_num="1",
        timestamp="240601123456",
        status="PASSED",
    )
    assert hook_needs_run(hook2, None) is False  # No history entry


def test_hook_needs_run_stale() -> None:
    """Test that hook needs run if no status line for current history entry."""
    # Hook has status line for history entry 1, but we want entry 2
    hook = _make_hook(
        command="flake8 src",
        history_entry_num="1",
        timestamp="240601100000",
        status="PASSED",
    )
    assert hook_needs_run(hook, "2") is True  # No status for entry 2


def test_hook_needs_run_up_to_date() -> None:
    """Test that hook doesn't need run if status line exists for current entry."""
    hook = _make_hook(
        command="flake8 src",
        history_entry_num="1",
        timestamp="240601130000",
        status="PASSED",
    )
    assert hook_needs_run(hook, "1") is False  # Has status for entry 1


def test_hook_needs_run_proposal_entry() -> None:
    """Test hook needs run distinguishes between regular and proposal entries."""
    # Hook has status line for entry "1", but we want entry "1a" (proposal)
    hook = _make_hook(
        command="flake8 src",
        history_entry_num="1",
        timestamp="240601100000",
        status="PASSED",
    )
    assert hook_needs_run(hook, "1a") is True  # No status for entry 1a
    assert hook_needs_run(hook, "1") is False  # Has status for entry 1


def test_hook_needs_run_same_entry() -> None:
    """Test that hook doesn't need run if status line exists for same entry."""
    hook = _make_hook(
        command="flake8 src",
        history_entry_num="2",
        timestamp="240601123456",
        status="PASSED",
    )
    assert hook_needs_run(hook, "2") is False  # Has status for entry 2


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
    path = get_hook_output_path("my_feature", "240601_123456")
    hooks_dir = get_gai_directory("hooks")
    assert path == os.path.join(hooks_dir, "my_feature-240601_123456.txt")


def test_get_hook_output_path_special_chars() -> None:
    """Test get_hook_output_path sanitizes special characters."""
    path = get_hook_output_path("my/feature-test", "240601_123456")
    hooks_dir = get_gai_directory("hooks")
    # Special chars should be replaced with underscore
    assert path == os.path.join(hooks_dir, "my_feature_test-240601_123456.txt")


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


# Tests for format_timestamp_display
def test_format_timestamp_display_basic() -> None:
    """Test formatting timestamp for display."""
    result = format_timestamp_display("240601_123456")
    # Format: [YYmmdd_HHMMSS]
    assert result == "[240601_123456]"


def test_format_timestamp_display_short() -> None:
    """Test formatting short timestamp."""
    result = format_timestamp_display("2406")
    # Should handle short timestamps gracefully
    assert "[2406]" == result


# Tests for _format_hooks_field
def test_format_hooks_field_basic() -> None:
    """Test formatting hooks field for writing."""
    hooks = [
        HookEntry(command="flake8 src"),
        _make_hook(
            command="pytest tests",
            timestamp="240601_123456",
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
    # Format includes (N) prefix and wrapped timestamp
    assert "(1) [240601_123456] PASSED (1m23s)" in result_str


def test_format_hooks_field_running_no_duration() -> None:
    """Test formatting hooks field with RUNNING status (no duration)."""
    hooks = [
        _make_hook(
            command="pytest tests",
            timestamp="240601_123456",
            status="RUNNING",
            duration=None,
        ),
    ]
    result = _format_hooks_field(hooks)
    result_str = "".join(result)
    assert "  pytest tests" in result_str
    # Format includes (N) prefix and wrapped timestamp
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
                timestamp="240601_123456",
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
        # Format with (N) prefix and wrapped timestamp
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


# Tests for is_timestamp_suffix
def test_is_timestamp_suffix_new_format() -> None:
    """Test is_timestamp_suffix returns True for YYmmdd_HHMMSS format."""
    assert is_timestamp_suffix("241225_120000") is True
    assert is_timestamp_suffix("250101_235959") is True


def test_is_timestamp_suffix_old_format() -> None:
    """Test is_timestamp_suffix returns True for YYmmddHHMMSS format."""
    assert is_timestamp_suffix("241225120000") is True
    assert is_timestamp_suffix("250101235959") is True


def test_is_timestamp_suffix_proposal_id() -> None:
    """Test is_timestamp_suffix returns False for proposal IDs."""
    assert is_timestamp_suffix("2a") is False
    assert is_timestamp_suffix("1b") is False
    assert is_timestamp_suffix("3") is False
    assert is_timestamp_suffix("10c") is False


def test_is_timestamp_suffix_exclamation() -> None:
    """Test is_timestamp_suffix returns False for '!' suffix."""
    assert is_timestamp_suffix("!") is False


def test_is_timestamp_suffix_none() -> None:
    """Test is_timestamp_suffix returns False for None."""
    assert is_timestamp_suffix(None) is False


# Tests for is_suffix_stale
def test_is_suffix_stale_not_timestamp() -> None:
    """Test is_suffix_stale returns False for non-timestamp suffixes."""
    assert is_suffix_stale(None) is False
    assert is_suffix_stale("!") is False
    assert is_suffix_stale("2a") is False
    assert is_suffix_stale("1b") is False


def test_is_suffix_stale_recent_timestamp() -> None:
    """Test is_suffix_stale returns False for recent timestamps."""
    # Use generate_timestamp() to get a fresh timestamp
    recent = generate_timestamp()
    assert is_suffix_stale(recent) is False


# Tests for generate_timestamp format
def test_generate_timestamp_format() -> None:
    """Test generate_timestamp returns YYmmdd_HHMMSS format (13 chars, with underscore)."""
    ts = generate_timestamp()
    # Should be 13 chars with underscore at position 6
    assert len(ts) == 13
    assert ts[6] == "_"
    assert ts[:6].isdigit()
    assert ts[7:].isdigit()


# Tests for backward compatible timestamp parsing
def testcalculate_duration_from_timestamps_new_format() -> None:
    """Test calculate_duration_from_timestamps handles new format with underscore."""
    # 1 hour apart
    duration = calculate_duration_from_timestamps("241225_120000", "241225_130000")
    assert duration == 3600.0


def testcalculate_duration_from_timestamps_old_format() -> None:
    """Test calculate_duration_from_timestamps handles old format without underscore."""
    # 1 hour apart
    duration = calculate_duration_from_timestamps("241225120000", "241225130000")
    assert duration == 3600.0


def testcalculate_duration_from_timestamps_mixed_formats() -> None:
    """Test calculate_duration_from_timestamps handles mixed formats."""
    # Old start, new end
    duration = calculate_duration_from_timestamps("241225120000", "241225_130000")
    assert duration == 3600.0
    # New start, old end
    duration = calculate_duration_from_timestamps("241225_120000", "241225130000")
    assert duration == 3600.0


# Tests for HookEntry prefix properties
def test_hook_entry_skip_fix_hook_with_exclamation() -> None:
    """Test skip_fix_hook is True when command starts with '!'."""
    hook = HookEntry(command="!some_command")
    assert hook.skip_fix_hook is True
    assert hook.skip_proposal_runs is False


def test_hook_entry_skip_proposal_runs_with_dollar() -> None:
    """Test skip_proposal_runs is True when command has '$' prefix."""
    hook = HookEntry(command="$some_command")
    assert hook.skip_proposal_runs is True
    assert hook.skip_fix_hook is False


def test_hook_entry_combined_prefixes() -> None:
    """Test both prefixes work together as '!$'."""
    hook = HookEntry(command="!$some_command")
    assert hook.skip_fix_hook is True
    assert hook.skip_proposal_runs is True
    assert hook.display_command == "some_command"
    assert hook.run_command == "some_command"


def test_hook_entry_display_command_strips_all_prefixes() -> None:
    """Test display_command strips both '!' and '$' prefixes."""
    assert HookEntry(command="!cmd").display_command == "cmd"
    assert HookEntry(command="$cmd").display_command == "cmd"
    assert HookEntry(command="!$cmd").display_command == "cmd"
    assert HookEntry(command="cmd").display_command == "cmd"


def test_hook_entry_run_command_strips_all_prefixes() -> None:
    """Test run_command strips both '!' and '$' prefixes."""
    assert HookEntry(command="!cmd").run_command == "cmd"
    assert HookEntry(command="$cmd").run_command == "cmd"
    assert HookEntry(command="!$cmd").run_command == "cmd"
    assert HookEntry(command="cmd").run_command == "cmd"


def test_hook_entry_no_prefix() -> None:
    """Test hook without any prefix."""
    hook = HookEntry(command="some_command")
    assert hook.skip_fix_hook is False
    assert hook.skip_proposal_runs is False
    assert hook.display_command == "some_command"
    assert hook.run_command == "some_command"


def test_hook_needs_run_skips_dollar_prefix_for_proposals() -> None:
    """Test that '$' prefixed hooks are skipped for proposal entries."""
    # Hook with $ prefix should be skipped for proposal entries
    hook_with_dollar = HookEntry(command="$some_command")
    assert hook_needs_run(hook_with_dollar, "1a") is False
    # But should run for regular entries
    assert hook_needs_run(hook_with_dollar, "1") is True


def test_hook_needs_run_runs_exclamation_prefix_for_proposals() -> None:
    """Test that '!' prefixed hooks (without $) run for proposal entries."""
    # Hook with only ! prefix should run for proposal entries
    hook_with_exclamation = HookEntry(command="!some_command")
    assert hook_needs_run(hook_with_exclamation, "1a") is True
    assert hook_needs_run(hook_with_exclamation, "1") is True


def test_hook_needs_run_skips_combined_prefix_for_proposals() -> None:
    """Test that '!$' prefixed hooks are skipped for proposal entries."""
    # Hook with !$ prefix should be skipped for proposal entries (due to $)
    hook_with_both = HookEntry(command="!$some_command")
    assert hook_needs_run(hook_with_both, "1a") is False
    # But should run for regular entries
    assert hook_needs_run(hook_with_both, "1") is True
