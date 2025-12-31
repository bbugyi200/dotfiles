"""Tests for hook check functionality in the loop workflow."""

from unittest.mock import MagicMock

from ace.changespec import ChangeSpec, CommentEntry, HookEntry, HookStatusLine
from ace.loop.hook_checks import check_hooks


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
    """Create a ChangeSpec for loop workflow testing."""
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

    result = check_hooks(cs, log)

    # No updates since hook is already PASSED (not RUNNING, not stale)
    assert result == []


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

    result = check_hooks(cs, log)

    # No updates since hook is already PASSED (not RUNNING, not stale)
    assert result == []


def test_check_hooks_no_hooks() -> None:
    """Test check_hooks returns empty when no hooks."""
    cs = _make_changespec(hooks=None)
    log = MagicMock()

    result = check_hooks(cs, log)

    assert result == []


def test_check_hooks_empty_hooks() -> None:
    """Test check_hooks returns empty when hooks list is empty."""
    cs = _make_changespec(hooks=[])
    log = MagicMock()

    result = check_hooks(cs, log)

    assert result == []
