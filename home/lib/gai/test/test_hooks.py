"""Tests for HOOKS field parsing and hooks module."""

import os

from work.changespec import HookEntry, _parse_changespec_from_lines
from work.hooks import (
    _format_duration,
    _get_hooks_directory,
    get_failing_hooks,
    get_failing_test_target_hooks,
    get_hook_output_path,
    get_last_history_diff_timestamp,
    get_test_target_from_hook,
    has_failing_hooks,
    has_failing_test_target_hooks,
    has_running_hooks,
    hook_needs_run,
)


# Tests for HookEntry dataclass
def test_hook_entry_all_fields() -> None:
    """Test HookEntry with all fields."""
    entry = HookEntry(
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
    entry = HookEntry(
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
        "    | [240601_123456] PASSED (1m23s)\n",
        "  mypy src\n",
        "    | [240601_123456] RUNNING\n",
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
        "    | [240601_123456] FAILED (5m30s)\n",
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
        "    | [240601_123456] ZOMBIE (24h0m)\n",
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
    assert _format_duration(3600) == "60m0s"


def test_format_duration_fractional() -> None:
    """Test formatting duration with fractional seconds (truncated)."""
    assert _format_duration(45.9) == "45s"
    assert _format_duration(83.7) == "1m23s"


# Tests for hook_needs_run
def test_hook_needs_run_never_run() -> None:
    """Test that hook needs run if never run before."""
    hook = HookEntry(command="flake8 src")
    assert hook_needs_run(hook, "240601123456") is True


def test_hook_needs_run_no_diff_timestamp() -> None:
    """Test that hook doesn't need run if no diff timestamp."""
    hook = HookEntry(command="flake8 src")
    assert hook_needs_run(hook, None) is True  # Never run -> needs run

    hook2 = HookEntry(
        command="flake8 src",
        timestamp="240601123456",
        status="PASSED",
    )
    assert hook_needs_run(hook2, None) is False  # Already run, no new diff


def test_hook_needs_run_stale() -> None:
    """Test that hook needs run if stale (older than diff timestamp)."""
    hook = HookEntry(
        command="flake8 src",
        timestamp="240601100000",  # Older
        status="PASSED",
    )
    assert hook_needs_run(hook, "240601123456") is True  # Stale


def test_hook_needs_run_up_to_date() -> None:
    """Test that hook doesn't need run if up to date."""
    hook = HookEntry(
        command="flake8 src",
        timestamp="240601130000",  # Newer than diff
        status="PASSED",
    )
    assert hook_needs_run(hook, "240601123456") is False


def test_hook_needs_run_same_timestamp() -> None:
    """Test that hook doesn't need run if same timestamp."""
    hook = HookEntry(
        command="flake8 src",
        timestamp="240601123456",
        status="PASSED",
    )
    assert hook_needs_run(hook, "240601123456") is False


# Tests for get_last_history_diff_timestamp
def test_get_last_history_diff_timestamp_with_diff() -> None:
    """Test extracting timestamp from DIFF path."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
        "HISTORY:\n",
        "  (1) Initial\n",
        "      | DIFF: ~/.gai/diffs/test_cl_240601123456.diff\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    timestamp = get_last_history_diff_timestamp(changespec)
    assert timestamp == "240601123456"


def test_get_last_history_diff_timestamp_multiple_entries() -> None:
    """Test extracting timestamp from last DIFF path."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
        "HISTORY:\n",
        "  (1) First\n",
        "      | DIFF: ~/.gai/diffs/test_cl_240601100000.diff\n",
        "  (2) Second\n",
        "      | DIFF: ~/.gai/diffs/test_cl_240601123456.diff\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    timestamp = get_last_history_diff_timestamp(changespec)
    # Should get timestamp from last entry
    assert timestamp == "240601123456"


def test_get_last_history_diff_timestamp_no_history() -> None:
    """Test that None is returned when no history."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    timestamp = get_last_history_diff_timestamp(changespec)
    assert timestamp is None


def test_get_last_history_diff_timestamp_no_diff_in_entry() -> None:
    """Test that None is returned when last entry has no DIFF."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
        "HISTORY:\n",
        "  (1) Manual\n",
        "      | CHAT: ~/.gai/chats/test.md\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    timestamp = get_last_history_diff_timestamp(changespec)
    assert timestamp is None


# Tests for test target hook functions
def test_get_test_target_from_hook_valid() -> None:
    """Test extracting test target from a valid test target hook."""
    hook = HookEntry(command="bb_rabbit_test //foo/bar:test1", status="PASSED")
    assert get_test_target_from_hook(hook) == "//foo/bar:test1"


def test_get_test_target_from_hook_with_spaces() -> None:
    """Test extracting test target from hook with extra spaces."""
    hook = HookEntry(command="bb_rabbit_test  //foo/bar:test1 ", status="PASSED")
    assert get_test_target_from_hook(hook) == "//foo/bar:test1"


def test_get_test_target_from_hook_not_test_target() -> None:
    """Test that non-test target hook returns None."""
    hook = HookEntry(command="flake8 src", status="PASSED")
    assert get_test_target_from_hook(hook) is None


def test_get_failing_test_target_hooks_mixed() -> None:
    """Test getting failing test target hooks from mixed list."""
    hooks = [
        HookEntry(command="bb_rabbit_test //foo:test1", status="FAILED"),
        HookEntry(command="bb_rabbit_test //foo:test2", status="PASSED"),
        HookEntry(command="flake8 src", status="FAILED"),
        HookEntry(command="bb_rabbit_test //bar:test3", status="FAILED"),
    ]
    failing = get_failing_test_target_hooks(hooks)
    assert len(failing) == 2
    assert failing[0].command == "bb_rabbit_test //foo:test1"
    assert failing[1].command == "bb_rabbit_test //bar:test3"


def test_get_failing_test_target_hooks_none_failing() -> None:
    """Test that empty list is returned when no failing test target hooks."""
    hooks = [
        HookEntry(command="bb_rabbit_test //foo:test1", status="PASSED"),
        HookEntry(command="flake8 src", status="FAILED"),
    ]
    failing = get_failing_test_target_hooks(hooks)
    assert failing == []


def test_has_failing_test_target_hooks_true() -> None:
    """Test has_failing_test_target_hooks returns True when failing hooks exist."""
    hooks = [
        HookEntry(command="bb_rabbit_test //foo:test1", status="FAILED"),
        HookEntry(command="bb_rabbit_test //foo:test2", status="PASSED"),
    ]
    assert has_failing_test_target_hooks(hooks) is True


def test_has_failing_test_target_hooks_false() -> None:
    """Test has_failing_test_target_hooks returns False when no failing hooks."""
    hooks = [
        HookEntry(command="bb_rabbit_test //foo:test1", status="PASSED"),
        HookEntry(command="flake8 src", status="FAILED"),
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
        HookEntry(command="bb_rabbit_test //foo:test1", status="FAILED"),
        HookEntry(command="bb_rabbit_test //foo:test2", status="PASSED"),
        HookEntry(command="flake8 src", status="FAILED"),
        HookEntry(command="mypy src", status="PASSED"),
        HookEntry(command="bb_rabbit_test //bar:test3", status="FAILED"),
    ]
    failing = get_failing_hooks(hooks)
    assert len(failing) == 3
    assert failing[0].command == "bb_rabbit_test //foo:test1"
    assert failing[1].command == "flake8 src"
    assert failing[2].command == "bb_rabbit_test //bar:test3"


def test_get_failing_hooks_none_failing() -> None:
    """Test that empty list is returned when no failing hooks."""
    hooks = [
        HookEntry(command="bb_rabbit_test //foo:test1", status="PASSED"),
        HookEntry(command="flake8 src", status="PASSED"),
    ]
    failing = get_failing_hooks(hooks)
    assert failing == []


def test_get_failing_hooks_empty_list() -> None:
    """Test that empty list is returned for empty input."""
    assert get_failing_hooks([]) == []


def test_has_failing_hooks_true() -> None:
    """Test has_failing_hooks returns True when failing hooks exist."""
    hooks = [
        HookEntry(command="flake8 src", status="FAILED"),
        HookEntry(command="mypy src", status="PASSED"),
    ]
    assert has_failing_hooks(hooks) is True


def test_has_failing_hooks_false() -> None:
    """Test has_failing_hooks returns False when no failing hooks."""
    hooks = [
        HookEntry(command="bb_rabbit_test //foo:test1", status="PASSED"),
        HookEntry(command="flake8 src", status="PASSED"),
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
        HookEntry(command="flake8 src", status="RUNNING", timestamp="240601123456"),
        HookEntry(command="mypy src", status="PASSED"),
    ]
    assert has_running_hooks(hooks) is True


def test_has_running_hooks_false() -> None:
    """Test has_running_hooks returns False when no running hooks."""
    hooks = [
        HookEntry(command="flake8 src", status="PASSED"),
        HookEntry(command="mypy src", status="FAILED"),
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
        HookEntry(command="hook1", status="FAILED"),
        HookEntry(command="hook2", status="PASSED"),
        HookEntry(command="hook3", status="RUNNING"),
        HookEntry(command="hook4", status="ZOMBIE"),
        HookEntry(command="hook5", status="FAILED"),
        HookEntry(command="hook6", status=None),  # Never run
    ]
    failing = get_failing_hooks(hooks)
    # Only FAILED status hooks should be returned
    assert len(failing) == 2
    assert failing[0].command == "hook1"
    assert failing[1].command == "hook5"


def test_get_failing_test_target_hooks_with_zombie() -> None:
    """Test that only FAILED test targets are returned, not ZOMBIE."""
    hooks = [
        HookEntry(command="bb_rabbit_test //foo:test1", status="FAILED"),
        HookEntry(command="bb_rabbit_test //foo:test2", status="ZOMBIE"),
        HookEntry(command="bb_rabbit_test //foo:test3", status="RUNNING"),
    ]
    failing = get_failing_test_target_hooks(hooks)
    # Only FAILED test target hooks should be returned
    assert len(failing) == 1
    assert failing[0].command == "bb_rabbit_test //foo:test1"
