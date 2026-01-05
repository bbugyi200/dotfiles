"""Tests for mark_hooks_as_killed and kill_running_processes_for_hooks."""

import os

import pytest
from ace.changespec import HookEntry, HookStatusLine
from ace.hooks.processes import kill_running_processes_for_hooks, mark_hooks_as_killed


def _make_hook_with_status_lines(
    command: str,
    status_lines: list[HookStatusLine],
) -> HookEntry:
    """Helper function to create a HookEntry with multiple status lines."""
    return HookEntry(command=command, status_lines=status_lines)


def test_mark_hooks_as_killed_sets_dead_status() -> None:
    """Test that mark_hooks_as_killed sets status to DEAD with description."""
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

    # Call mark_hooks_as_killed with description
    result = mark_hooks_as_killed(
        [hook], killed_processes, "Killed hook running on reverted CL."
    )

    # Verify the result
    assert len(result) == 1
    result_hook = result[0]
    assert result_hook.command == "make test"
    assert result_hook.status_lines is not None
    assert len(result_hook.status_lines) == 1

    result_sl = result_hook.status_lines[0]
    # Status should be changed to DEAD
    assert result_sl.status == "DEAD"
    # suffix_type should be changed to killed_process
    assert result_sl.suffix_type == "killed_process"
    # Other fields should be preserved
    assert result_sl.commit_entry_num == "2"
    assert result_sl.timestamp == "251231_120000"
    # Suffix should now include PID and description with timestamp
    assert result_sl.suffix is not None
    assert result_sl.suffix.startswith("12345 | [")
    assert "Killed hook running on reverted CL." in result_sl.suffix


# Tests for kill_running_processes_for_hooks


def test_kill_running_processes_for_hooks_empty_hooks() -> None:
    """Test kill_running_processes_for_hooks with None hooks."""
    result = kill_running_processes_for_hooks(None, {0})
    assert result == 0


def test_kill_running_processes_for_hooks_empty_indices() -> None:
    """Test kill_running_processes_for_hooks with empty indices set."""
    hook = HookEntry(command="make test")
    result = kill_running_processes_for_hooks([hook], set())
    assert result == 0


def test_kill_running_processes_for_hooks_out_of_range_index() -> None:
    """Test kill_running_processes_for_hooks with out-of-range indices."""
    hook = HookEntry(command="make test")
    result = kill_running_processes_for_hooks([hook], {5, -1, 100})
    assert result == 0


def test_kill_running_processes_for_hooks_no_status_lines() -> None:
    """Test kill_running_processes_for_hooks with hooks that have no status lines."""
    hook = HookEntry(command="make test")
    result = kill_running_processes_for_hooks([hook], {0})
    assert result == 0


def test_kill_running_processes_for_hooks_no_running_suffix() -> None:
    """Test kill_running_processes_for_hooks with non-running status lines."""
    # Hook with PASSED status (not running)
    status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251231_120000",
        status="PASSED",
        duration="1m23s",
        suffix=None,
        suffix_type=None,
    )
    hook = _make_hook_with_status_lines("make test", [status_line])
    result = kill_running_processes_for_hooks([hook], {0})
    assert result == 0


def test_kill_running_processes_for_hooks_finds_running_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test kill_running_processes_for_hooks kills running_process hooks."""
    # Track killpg calls
    killed_pids: list[int] = []

    def mock_killpg(pid: int, sig: int) -> None:
        killed_pids.append(pid)

    monkeypatch.setattr(os, "killpg", mock_killpg)

    # Hook with running_process suffix_type
    status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251231_120000",
        status="RUNNING",
        duration=None,
        suffix="12345",  # PID
        suffix_type="running_process",
    )
    hook = _make_hook_with_status_lines("make test", [status_line])

    result = kill_running_processes_for_hooks([hook], {0})
    assert result == 1
    assert 12345 in killed_pids


def test_kill_running_processes_for_hooks_finds_running_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test kill_running_processes_for_hooks kills running_agent hooks."""
    # Track killpg calls
    killed_pids: list[int] = []

    def mock_killpg(pid: int, sig: int) -> None:
        killed_pids.append(pid)

    monkeypatch.setattr(os, "killpg", mock_killpg)

    # Hook with running_agent suffix_type (format: <agent>-<PID>-<timestamp>)
    status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251231_120000",
        status="RUNNING",
        duration=None,
        suffix="fix_hook-67890-251231_130000",  # agent-PID-timestamp format
        suffix_type="running_agent",
    )
    hook = _make_hook_with_status_lines("make test", [status_line])

    result = kill_running_processes_for_hooks([hook], {0})
    assert result == 1
    assert 67890 in killed_pids


def test_kill_running_processes_for_hooks_handles_process_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test kill_running_processes_for_hooks handles ProcessLookupError."""

    def mock_killpg(pid: int, sig: int) -> None:
        raise ProcessLookupError("No such process")

    monkeypatch.setattr(os, "killpg", mock_killpg)

    # Hook with running_process suffix_type
    status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="251231_120000",
        status="RUNNING",
        duration=None,
        suffix="12345",  # PID
        suffix_type="running_process",
    )
    hook = _make_hook_with_status_lines("make test", [status_line])

    # Should still count as 1 (handled) even though process is dead
    result = kill_running_processes_for_hooks([hook], {0})
    assert result == 1


def test_kill_running_processes_for_hooks_multiple_hooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test kill_running_processes_for_hooks with multiple hooks."""
    # Track killpg calls
    killed_pids: list[int] = []

    def mock_killpg(pid: int, sig: int) -> None:
        killed_pids.append(pid)

    monkeypatch.setattr(os, "killpg", mock_killpg)

    # Hook 0: running_process
    hook0 = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="1",
                timestamp="251231_120000",
                status="RUNNING",
                suffix="11111",
                suffix_type="running_process",
            )
        ],
    )
    # Hook 1: running_agent
    hook1 = _make_hook_with_status_lines(
        "make lint",
        [
            HookStatusLine(
                commit_entry_num="1",
                timestamp="251231_120000",
                status="RUNNING",
                suffix="fix_hook-22222-251231_130000",
                suffix_type="running_agent",
            )
        ],
    )
    # Hook 2: PASSED (not running)
    hook2 = _make_hook_with_status_lines(
        "make build",
        [
            HookStatusLine(
                commit_entry_num="1",
                timestamp="251231_120000",
                status="PASSED",
                duration="1m0s",
            )
        ],
    )

    hooks = [hook0, hook1, hook2]

    # Kill hooks 0 and 1, not 2
    result = kill_running_processes_for_hooks(hooks, {0, 1})
    assert result == 2
    assert 11111 in killed_pids
    assert 22222 in killed_pids


def test_kill_running_processes_for_hooks_only_specified_indices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that kill_running_processes_for_hooks only kills specified indices."""
    # Track killpg calls
    killed_pids: list[int] = []

    def mock_killpg(pid: int, sig: int) -> None:
        killed_pids.append(pid)

    monkeypatch.setattr(os, "killpg", mock_killpg)

    # Both hooks are running
    hook0 = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="1",
                timestamp="251231_120000",
                status="RUNNING",
                suffix="11111",
                suffix_type="running_process",
            )
        ],
    )
    hook1 = _make_hook_with_status_lines(
        "make lint",
        [
            HookStatusLine(
                commit_entry_num="1",
                timestamp="251231_120000",
                status="RUNNING",
                suffix="22222",
                suffix_type="running_process",
            )
        ],
    )

    hooks = [hook0, hook1]

    # Only kill hook 0, not hook 1
    result = kill_running_processes_for_hooks(hooks, {0})
    assert result == 1
    assert 11111 in killed_pids
    assert 22222 not in killed_pids
