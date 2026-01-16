"""Tests for hook check functionality in the axe workflow."""

from unittest.mock import MagicMock, patch

from ace.changespec import ChangeSpec, CommentEntry, HookEntry, HookStatusLine
from ace.scheduler.hook_checks import (
    _wait_for_completion_marker,
    check_hooks,
)


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


def _make_changespec(
    name: str = "test_cs",
    status: str = "Drafted",
    file_path: str = "/path/to/project.gp",
    hooks: list[HookEntry] | None = None,
    comments: list[CommentEntry] | None = None,
) -> ChangeSpec:
    """Create a ChangeSpec for axe workflow testing."""
    return ChangeSpec(
        name=name,
        description="Test description",
        parent=None,
        cl="http://cl/12345",
        status=status,
        test_targets=None,
        kickstart=None,
        file_path=file_path,
        line_number=1,
        commits=None,
        hooks=hooks,
        comments=comments,
    )


def test_check_hooks_skips_reverted() -> None:
    """Test check_hooks skips starting new hooks for Reverted status.

    For terminal statuses like Reverted, we still check if RUNNING hooks
    have completed (to update status and release workspaces), but we
    don't start new stale hooks.
    """
    cs = _make_changespec(
        status="Reverted",
        hooks=[
            # Use PASSED status - no completion check needed, no stale hooks
            _make_hook(command="test_cmd", status="PASSED", timestamp="240101120000")
        ],
    )
    log = MagicMock()

    updates, hooks_started = check_hooks(cs, log)

    # No updates since hook is already PASSED (not RUNNING, not stale)
    assert updates == []
    assert hooks_started == 0


def test_check_hooks_skips_submitted() -> None:
    """Test check_hooks skips starting new hooks for Submitted status.

    For terminal statuses like Submitted, we still check if RUNNING hooks
    have completed (to update status and release workspaces), but we
    don't start new stale hooks.
    """
    cs = _make_changespec(
        status="Submitted",
        hooks=[
            # Use PASSED status - no completion check needed, no stale hooks
            _make_hook(command="test_cmd", status="PASSED", timestamp="240101120000")
        ],
    )
    log = MagicMock()

    updates, hooks_started = check_hooks(cs, log)

    # No updates since hook is already PASSED (not RUNNING, not stale)
    assert updates == []
    assert hooks_started == 0


def test_check_hooks_no_hooks() -> None:
    """Test check_hooks returns empty when no hooks."""
    cs = _make_changespec(hooks=None)
    log = MagicMock()

    updates, hooks_started = check_hooks(cs, log)

    assert updates == []
    assert hooks_started == 0


def test_check_hooks_empty_hooks() -> None:
    """Test check_hooks returns empty when hooks list is empty."""
    cs = _make_changespec(hooks=[])
    log = MagicMock()

    updates, hooks_started = check_hooks(cs, log)

    assert updates == []
    assert hooks_started == 0


# Tests for _wait_for_completion_marker race condition handling


def test_wait_for_completion_marker_finds_on_first_retry() -> None:
    """Test that _wait_for_completion_marker returns hook when found on retry."""
    cs = _make_changespec()
    hook = _make_hook(command="test_cmd", status="RUNNING", timestamp="240101120000")
    completed_hook = _make_hook(
        command="test_cmd", status="PASSED", timestamp="240101120000"
    )

    with (
        patch(
            "ace.scheduler.hook_checks.check_hook_completion",
            return_value=completed_hook,
        ) as mock_check,
        patch("ace.scheduler.hook_checks.time.sleep") as mock_sleep,
    ):
        result = _wait_for_completion_marker(cs, hook, max_retries=3, retry_delay=0.1)

    assert result == completed_hook
    # Should have called check once (found on first retry)
    assert mock_check.call_count == 1
    # Should have slept once before the check
    assert mock_sleep.call_count == 1
    mock_sleep.assert_called_with(0.1)


def test_wait_for_completion_marker_finds_on_second_retry() -> None:
    """Test that _wait_for_completion_marker retries until marker found."""
    cs = _make_changespec()
    hook = _make_hook(command="test_cmd", status="RUNNING", timestamp="240101120000")
    completed_hook = _make_hook(
        command="test_cmd", status="PASSED", timestamp="240101120000"
    )

    # First call returns None, second call returns completed hook
    with (
        patch(
            "ace.scheduler.hook_checks.check_hook_completion",
            side_effect=[None, completed_hook],
        ) as mock_check,
        patch("ace.scheduler.hook_checks.time.sleep") as mock_sleep,
    ):
        result = _wait_for_completion_marker(cs, hook, max_retries=3, retry_delay=0.1)

    assert result == completed_hook
    # Should have called check twice
    assert mock_check.call_count == 2
    # Should have slept twice
    assert mock_sleep.call_count == 2


def test_wait_for_completion_marker_returns_none_after_all_retries() -> None:
    """Test that _wait_for_completion_marker returns None if marker never found."""
    cs = _make_changespec()
    hook = _make_hook(command="test_cmd", status="RUNNING", timestamp="240101120000")

    with (
        patch(
            "ace.scheduler.hook_checks.check_hook_completion", return_value=None
        ) as mock_check,
        patch("ace.scheduler.hook_checks.time.sleep") as mock_sleep,
    ):
        result = _wait_for_completion_marker(cs, hook, max_retries=3, retry_delay=0.2)

    assert result is None
    # Should have tried all 3 retries
    assert mock_check.call_count == 3
    assert mock_sleep.call_count == 3
    # Verify correct delay was used
    mock_sleep.assert_called_with(0.2)


def test_check_hooks_logs_warning_on_merge_failure() -> None:
    """Test that check_hooks logs a warning when merge_hook_updates fails."""
    # Create a changespec with a RUNNING hook that has completed
    status_line = HookStatusLine(
        commit_entry_num="1",
        timestamp="240101120000",
        status="RUNNING",
        duration=None,
        suffix="12345",  # PID
    )
    hook = HookEntry(command="test_cmd", status_lines=[status_line])
    cs = _make_changespec(hooks=[hook])
    log = MagicMock()

    # Create a completed hook to return from check_hook_completion
    completed_hook = _make_hook(
        command="test_cmd", status="PASSED", timestamp="240101120000"
    )

    with (
        patch(
            "ace.scheduler.hook_checks.check_hook_completion",
            return_value=completed_hook,
        ),
        patch("ace.scheduler.hook_checks.is_process_running", return_value=True),
        patch("ace.scheduler.hook_checks.merge_hook_updates", return_value=False),
    ):
        updates, hooks_started = check_hooks(cs, log)

    # Verify that the warning was logged
    log.assert_any_call(
        "Warning: Hook update failed for test_cs, will retry",
        "dim",
    )
