"""Tests for HookEntry dataclass, HOOKS field parsing, and utility functions."""

import os

from ace.changespec import (
    HookEntry,
    HookStatusLine,
    parse_commit_entry_id,
)
from ace.changespec.parser import _parse_changespec_from_lines
from ace.hooks import (
    calculate_duration_from_timestamps,
    format_duration,
)
from gai_utils import get_gai_directory


def _make_hook(
    command: str,
    commit_entry_num: str = "1",
    timestamp: str | None = None,
    status: str | None = None,
    duration: str | None = None,
) -> HookEntry:
    """Helper function to create a HookEntry with a status line."""
    if timestamp is None and status is None:
        return HookEntry(command=command)
    status_line = HookStatusLine(
        commit_entry_num=commit_entry_num,
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
        "    (1) [240601_123456] PASSED (1m23s)\n",
        "  mypy src\n",
        "    (1) [240601_123456] RUNNING\n",
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
        "    (1) [240601_123456] FAILED (5m30s)\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.hooks is not None
    assert len(changespec.hooks) == 1
    assert changespec.hooks[0].command == "pytest src"
    assert changespec.hooks[0].status == "FAILED"
    assert changespec.hooks[0].duration == "5m30s"


def test_parse_changespec_hooks_with_killed_status() -> None:
    """Test parsing HOOKS with KILLED status."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  pytest src\n",
        "    (1) [240601_123456] KILLED (24h0m)\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.hooks is not None
    assert len(changespec.hooks) == 1
    assert changespec.hooks[0].command == "pytest src"
    assert changespec.hooks[0].status == "KILLED"
    assert changespec.hooks[0].duration == "24h0m"


# Tests for hook utility functions
def test_get_hooks_directory() -> None:
    """Test getting hooks directory path."""
    expected = os.path.expanduser("~/.gai/hooks")
    assert get_gai_directory("hooks") == expected


def test_format_duration_seconds_only() -> None:
    """Test formatting duration with only seconds."""
    assert format_duration(45) == "45s"
    assert format_duration(0) == "0s"
    assert format_duration(59) == "59s"


def test_format_duration_with_minutes() -> None:
    """Test formatting duration with minutes and seconds."""
    assert format_duration(60) == "1m0s"
    assert format_duration(83) == "1m23s"


def test_format_duration_with_hours() -> None:
    """Test formatting duration with hours, minutes, and seconds."""
    assert format_duration(3600) == "1h0m0s"
    assert format_duration(3661) == "1h1m1s"
    assert format_duration(7323) == "2h2m3s"
    assert format_duration(86400) == "24h0m0s"  # 24 hours


def test_format_duration_fractional() -> None:
    """Test formatting duration with fractional seconds (truncated)."""
    assert format_duration(45.9) == "45s"
    assert format_duration(83.7) == "1m23s"


# Tests for calculate_duration_from_timestamps
def test_calculate_duration_from_timestamps_basic() -> None:
    """Test calculating duration between two timestamps."""
    # 1 minute apart
    start = "240601120000"  # 12:00:00
    end = "240601120100"  # 12:01:00
    assert calculate_duration_from_timestamps(start, end) == 60.0


def test_calculate_duration_from_timestamps_hours() -> None:
    """Test calculating duration with hours difference."""
    start = "240601120000"  # 12:00:00
    end = "240601140000"  # 14:00:00
    assert calculate_duration_from_timestamps(start, end) == 7200.0  # 2 hours


def test_calculate_duration_from_timestamps_complex() -> None:
    """Test calculating duration with hours, minutes, and seconds."""
    start = "240601120000"  # 12:00:00
    end = "240601132345"  # 13:23:45
    # 1h 23m 45s = 3600 + 1380 + 45 = 5025 seconds
    assert calculate_duration_from_timestamps(start, end) == 5025.0


def test_calculate_duration_from_timestamps_same() -> None:
    """Test calculating duration when timestamps are the same."""
    timestamp = "240601120000"
    assert calculate_duration_from_timestamps(timestamp, timestamp) == 0.0


def test_calculate_duration_from_timestamps_invalid() -> None:
    """Test that invalid timestamps return None."""
    assert calculate_duration_from_timestamps("invalid", "240601120000") is None
    assert calculate_duration_from_timestamps("240601120000", "invalid") is None
    assert calculate_duration_from_timestamps("", "") is None


# Tests for parse_commit_entry_id
def test_parse_commit_entry_id_regular() -> None:
    """Test parsing regular commit entry IDs (no letter)."""
    assert parse_commit_entry_id("1") == (1, "")
    assert parse_commit_entry_id("2") == (2, "")
    assert parse_commit_entry_id("10") == (10, "")


def test_parse_commit_entry_id_proposal() -> None:
    """Test parsing proposal commit entry IDs (with letter)."""
    assert parse_commit_entry_id("1a") == (1, "a")
    assert parse_commit_entry_id("1b") == (1, "b")
    assert parse_commit_entry_id("2a") == (2, "a")
    assert parse_commit_entry_id("10z") == (10, "z")


def test_parse_commit_entry_id_invalid() -> None:
    """Test parsing invalid commit entry IDs."""
    # Fallback returns (0, original_string)
    assert parse_commit_entry_id("abc") == (0, "abc")
    assert parse_commit_entry_id("") == (0, "")


def test_parse_commit_entry_id_sorting() -> None:
    """Test that parse_commit_entry_id enables proper sorting."""
    # Sorting by tuple (number, letter) gives correct order
    ids = ["1a", "2", "1", "1b", "10", "2a"]
    sorted_ids = sorted(ids, key=parse_commit_entry_id)
    assert sorted_ids == ["1", "1a", "1b", "2", "2a", "10"]


# Tests for parent-passed check for proposals
def _make_hook_with_status_lines(
    command: str,
    status_lines: list[HookStatusLine],
) -> HookEntry:
    """Helper function to create a HookEntry with multiple status lines."""
    return HookEntry(command=command, status_lines=status_lines)


def test_hook_needs_run_proposal_waits_no_parent_status() -> None:
    """Test that proposal waits when parent has no status line."""
    from ace.hooks import hook_needs_run

    # Hook with no status lines at all
    hook = HookEntry(command="make test")
    # Proposal "2a" should wait - parent "2" has no status
    assert hook_needs_run(hook, "2a") is False
    # But regular entry "1" can still run
    assert hook_needs_run(hook, "1") is True


def test_hook_needs_run_proposal_waits_parent_running() -> None:
    """Test that proposal waits when parent is RUNNING."""
    from ace.hooks import hook_needs_run

    hook = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="2", timestamp="251231_120000", status="RUNNING"
            )
        ],
    )
    # Proposal "2a" should wait - parent "2" is RUNNING
    assert hook_needs_run(hook, "2a") is False


def test_hook_needs_run_proposal_waits_parent_failed() -> None:
    """Test that proposal waits when parent FAILED without fix-hook suffix."""
    from ace.hooks import hook_needs_run

    hook = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="2", timestamp="251231_120000", status="FAILED"
            )
        ],
    )
    # Proposal "2a" should wait - parent "2" FAILED but no fix-hook suffix
    assert hook_needs_run(hook, "2a") is False


def test_hook_needs_run_proposal_runs_parent_passed() -> None:
    """Test that proposal runs when parent PASSED."""
    from ace.hooks import hook_needs_run

    hook = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="2", timestamp="251231_120000", status="PASSED"
            )
        ],
    )
    # Proposal "2a" can run - parent "2" PASSED
    assert hook_needs_run(hook, "2a") is True


def test_hook_needs_run_fix_hook_exception() -> None:
    """Test that fix-hook proposal runs immediately (parent suffix matches)."""
    from ace.hooks import hook_needs_run

    hook = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="2",
                timestamp="251231_120000",
                status="FAILED",
                suffix="2a",  # Fix-hook created proposal "2a"
            )
        ],
    )
    # Proposal "2a" can run - it's the fix-hook proposal for this hook
    assert hook_needs_run(hook, "2a") is True
    # But proposal "2b" still waits - it's not the fix-hook proposal
    assert hook_needs_run(hook, "2b") is False


def test_hook_needs_run_regular_entry_unaffected() -> None:
    """Test that regular (non-proposal) entries are unaffected by parent check."""
    from ace.hooks import hook_needs_run

    # Even with no status lines, regular entries can run
    hook = HookEntry(command="make test")
    assert hook_needs_run(hook, "1") is True
    assert hook_needs_run(hook, "2") is True
    assert hook_needs_run(hook, "10") is True


def test_get_entries_needing_hook_run_parent_passed() -> None:
    """Test get_entries_needing_hook_run respects parent-passed for proposals."""
    from ace.hooks import get_entries_needing_hook_run

    # Parent "2" passed
    hook = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="2", timestamp="251231_120000", status="PASSED"
            )
        ],
    )
    # Should return both regular "3" and proposal "2a" (parent passed)
    result = get_entries_needing_hook_run(hook, ["2", "2a", "3"])
    assert "3" in result  # Regular entry needs to run
    assert "2a" in result  # Proposal can run - parent passed
    assert "2" not in result  # Already has status


def test_get_entries_needing_hook_run_parent_not_passed() -> None:
    """Test get_entries_needing_hook_run skips proposals when parent not passed."""
    from ace.hooks import get_entries_needing_hook_run

    # Parent "2" is running
    hook = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="2", timestamp="251231_120000", status="RUNNING"
            )
        ],
    )
    # Should only return regular "3", not proposal "2a"
    result = get_entries_needing_hook_run(hook, ["2", "2a", "3"])
    assert "3" in result  # Regular entry needs to run
    assert "2a" not in result  # Proposal waits - parent not passed
    assert "2" not in result  # Already has status


def test_get_entries_needing_hook_run_fix_hook_exception() -> None:
    """Test get_entries_needing_hook_run allows fix-hook proposals."""
    from ace.hooks import get_entries_needing_hook_run

    # Parent "2" failed but created fix-hook proposal "2a"
    hook = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="2",
                timestamp="251231_120000",
                status="FAILED",
                suffix="2a",
            )
        ],
    )
    result = get_entries_needing_hook_run(hook, ["2", "2a", "2b", "3"])
    assert "3" in result  # Regular entry
    assert "2a" in result  # Fix-hook proposal - can run
    assert "2b" not in result  # Not the fix-hook proposal - waits
    assert "2" not in result  # Already has status


def test_mark_hooks_as_killed_sets_killed_status() -> None:
    """Test that mark_hooks_as_killed sets status to KILLED."""
    from ace.hooks.core import mark_hooks_as_killed

    # Create a hook with RUNNING status and running_process suffix_type
    status_line = HookStatusLine(
        commit_entry_num="2",
        timestamp="251231_120000",
        status="RUNNING",
        duration=None,
        suffix="12345",  # PID
        suffix_type="running_process",
    )
    hook = _make_hook_with_status_lines("make test", [status_line])

    # Build killed_processes list matching what kill_running_hook_processes returns
    killed_processes = [(hook, status_line, 12345)]

    # Call mark_hooks_as_killed
    result = mark_hooks_as_killed([hook], killed_processes)

    # Verify the result
    assert len(result) == 1
    result_hook = result[0]
    assert result_hook.command == "make test"
    assert result_hook.status_lines is not None
    assert len(result_hook.status_lines) == 1

    result_sl = result_hook.status_lines[0]
    # Status should be changed to KILLED
    assert result_sl.status == "KILLED"
    # suffix_type should be changed to killed_process
    assert result_sl.suffix_type == "killed_process"
    # Other fields should be preserved
    assert result_sl.commit_entry_num == "2"
    assert result_sl.timestamp == "251231_120000"
    assert result_sl.suffix == "12345"
