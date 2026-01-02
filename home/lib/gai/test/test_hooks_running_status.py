"""Tests for hook_has_any_running_status function."""

from ace.changespec import HookEntry, HookStatusLine
from ace.hooks import hook_has_any_running_status


def _make_hook_with_status_lines(
    command: str,
    status_lines: list[HookStatusLine],
) -> HookEntry:
    """Helper function to create a HookEntry with multiple status lines."""
    return HookEntry(command=command, status_lines=status_lines)


def test_hook_has_any_running_status_no_status_lines() -> None:
    """Test hook_has_any_running_status with no status lines returns False."""
    hook = HookEntry(command="make test")
    assert hook_has_any_running_status(hook) is False


def test_hook_has_any_running_status_running() -> None:
    """Test hook_has_any_running_status returns True for RUNNING status."""
    hook = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="1",
                timestamp="251231_120000",
                status="RUNNING",
            )
        ],
    )
    assert hook_has_any_running_status(hook) is True


def test_hook_has_any_running_status_passed() -> None:
    """Test hook_has_any_running_status returns False for PASSED status."""
    hook = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="1",
                timestamp="251231_120000",
                status="PASSED",
                duration="1m0s",
            )
        ],
    )
    assert hook_has_any_running_status(hook) is False


def test_hook_has_any_running_status_failed_with_running_agent() -> None:
    """Test hook_has_any_running_status returns True for FAILED with running_agent.

    This is the key test for the race condition fix: when a summarize-hook or
    fix-hook workflow is running, the status is still FAILED but the suffix_type
    is "running_agent". We must return True to prevent the hook from being rerun.
    """
    hook = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="1",
                timestamp="251231_120000",
                status="FAILED",
                duration="4m4s",
                suffix="summarize_hook-12345-251231_130000",
                suffix_type="running_agent",
            )
        ],
    )
    assert hook_has_any_running_status(hook) is True


def test_hook_has_any_running_status_failed_without_running_agent() -> None:
    """Test hook_has_any_running_status returns False for FAILED without running_agent."""
    hook = _make_hook_with_status_lines(
        "make test",
        [
            HookStatusLine(
                commit_entry_num="1",
                timestamp="251231_120000",
                status="FAILED",
                duration="4m4s",
            )
        ],
    )
    assert hook_has_any_running_status(hook) is False
