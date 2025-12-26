"""Tests for the loop workflow."""

from unittest.mock import MagicMock, patch

from work.changespec import ChangeSpec, HookEntry, HookStatusLine
from work.loop import LoopWorkflow


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


def _make_changespec(
    name: str = "test_cs",
    status: str = "Drafted",
    file_path: str = "/path/to/project.gp",
    hooks: list[HookEntry] | None = None,
) -> ChangeSpec:
    """Create a ChangeSpec for testing."""
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
        history=None,
        hooks=hooks,
    )


def test_loop_workflow_init_default_interval() -> None:
    """Test LoopWorkflow initializes with default interval."""
    workflow = LoopWorkflow()
    assert workflow.interval_seconds == 300


def test_loop_workflow_init_custom_interval() -> None:
    """Test LoopWorkflow initializes with custom interval."""
    workflow = LoopWorkflow(interval_seconds=60)
    assert workflow.interval_seconds == 60


def test_loop_workflow_init_default_hook_interval() -> None:
    """Test LoopWorkflow initializes with default hook interval."""
    workflow = LoopWorkflow()
    assert workflow.hook_interval_seconds == 10


def test_loop_workflow_init_custom_hook_interval() -> None:
    """Test LoopWorkflow initializes with custom hook interval."""
    workflow = LoopWorkflow(hook_interval_seconds=30)
    assert workflow.hook_interval_seconds == 30


def test_log_without_style() -> None:
    """Test _log outputs timestamped message without style."""
    workflow = LoopWorkflow()
    workflow.console = MagicMock()

    with patch("work.loop.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "2025-01-15 12:30:00"
        workflow._log("Test message")

    workflow.console.print.assert_called_once()
    call_arg = workflow.console.print.call_args[0][0]
    assert "[2025-01-15 12:30:00] Test message" in call_arg


def test_log_with_style() -> None:
    """Test _log outputs timestamped message with style."""
    workflow = LoopWorkflow()
    workflow.console = MagicMock()

    with patch("work.loop.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "2025-01-15 12:30:00"
        workflow._log("Test message", style="green")

    workflow.console.print.assert_called_once()
    call_arg = workflow.console.print.call_args[0][0]
    assert "[green]" in call_arg
    assert "Test message" in call_arg


def test_count_projects_single_project() -> None:
    """Test _count_projects with single project."""
    workflow = LoopWorkflow()
    changespecs = [
        _make_changespec(name="cs1", file_path="/path/to/project1.gp"),
        _make_changespec(name="cs2", file_path="/path/to/project1.gp"),
    ]
    assert workflow._count_projects(changespecs) == 1


def test_count_projects_multiple_projects() -> None:
    """Test _count_projects with multiple projects."""
    workflow = LoopWorkflow()
    changespecs = [
        _make_changespec(name="cs1", file_path="/path/to/project1.gp"),
        _make_changespec(name="cs2", file_path="/path/to/project2.gp"),
        _make_changespec(name="cs3", file_path="/path/to/project1.gp"),
    ]
    assert workflow._count_projects(changespecs) == 2


def test_count_projects_empty_list() -> None:
    """Test _count_projects with empty list."""
    workflow = LoopWorkflow()
    assert workflow._count_projects([]) == 0


def test_check_status_skips_non_syncable_status() -> None:
    """Test _check_status returns None for non-syncable statuses."""
    workflow = LoopWorkflow()
    cs = _make_changespec(status="Drafted")  # Not in SYNCABLE_STATUSES

    result = workflow._check_status(cs)
    assert result is None


def test_check_status_skips_recently_checked() -> None:
    """Test _check_status returns None when recently checked."""
    workflow = LoopWorkflow()
    cs = _make_changespec(status="Mailed")

    with patch("work.loop.should_check", return_value=False):
        result = workflow._check_status(cs)
    assert result is None


@patch("work.loop.update_last_checked")
@patch("work.loop.should_check", return_value=True)
@patch("work.loop.is_parent_submitted", return_value=True)
@patch("work.loop.is_cl_submitted", return_value=True)
@patch("work.loop.transition_changespec_status")
@patch("work.loop.clear_cache_entry")
def test_check_status_detects_submitted(
    mock_clear_cache: MagicMock,
    mock_transition: MagicMock,
    mock_is_submitted: MagicMock,
    mock_is_parent: MagicMock,
    mock_should_check: MagicMock,
    mock_update: MagicMock,
) -> None:
    """Test _check_status detects submitted CL."""
    mock_transition.return_value = (True, "Mailed", None)

    workflow = LoopWorkflow()
    cs = _make_changespec(status="Mailed")

    result = workflow._check_status(cs)

    assert result == "Status changed Mailed -> Submitted"
    mock_clear_cache.assert_called_once_with(cs.name)


@patch("work.loop.update_last_checked")
@patch("work.loop.should_check", return_value=True)
@patch("work.loop.is_parent_submitted", return_value=True)
@patch("work.loop.is_cl_submitted", return_value=False)
@patch("work.loop.has_pending_comments", return_value=True)
@patch("work.loop.transition_changespec_status")
def test_check_status_detects_pending_comments(
    mock_transition: MagicMock,
    mock_has_comments: MagicMock,
    mock_is_submitted: MagicMock,
    mock_is_parent: MagicMock,
    mock_should_check: MagicMock,
    mock_update: MagicMock,
) -> None:
    """Test _check_status detects pending comments on Mailed CL."""
    mock_transition.return_value = (True, "Mailed", None)

    workflow = LoopWorkflow()
    cs = _make_changespec(status="Mailed")

    result = workflow._check_status(cs)

    assert result == "Status changed Mailed -> Changes Requested"


def test_check_single_changespec_runs_status_check() -> None:
    """Test _check_single_changespec runs status check."""
    workflow = LoopWorkflow()
    cs = _make_changespec(status="Mailed")

    with (
        patch.object(workflow, "_should_check_status", return_value=(True, None)),
        patch.object(
            workflow, "_check_status", return_value="Status changed Mailed -> Submitted"
        ),
    ):
        updates, checked_types, skip_reasons = workflow._check_single_changespec(cs)

    assert len(updates) == 1
    assert "Status changed Mailed -> Submitted" in updates
    assert "status" in checked_types
    assert skip_reasons == []


def test_check_single_changespec_no_updates() -> None:
    """Test _check_single_changespec returns empty updates when nothing checked."""
    workflow = LoopWorkflow()
    cs = _make_changespec()  # status="Drafted" which is not syncable

    # With default Drafted status, status check is skipped (not syncable)
    updates, checked_types, skip_reasons = workflow._check_single_changespec(cs)

    assert updates == []
    assert checked_types == []
    assert len(skip_reasons) == 1  # Status skipped


def test_check_hooks_skips_reverted() -> None:
    """Test _check_hooks skips starting new hooks for Reverted status.

    For terminal statuses like Reverted, we still check if RUNNING hooks
    have completed (to update status and release workspaces), but we
    don't start new stale hooks.
    """
    workflow = LoopWorkflow()
    cs = _make_changespec(
        status="Reverted",
        hooks=[
            # Use PASSED status - no completion check needed, no stale hooks
            _make_hook(command="test_cmd", status="PASSED", timestamp="240101120000")
        ],
    )

    result = workflow._check_hooks(cs)

    # No updates since hook is already PASSED (not RUNNING, not stale)
    assert result == []


def test_check_hooks_skips_submitted() -> None:
    """Test _check_hooks skips starting new hooks for Submitted status.

    For terminal statuses like Submitted, we still check if RUNNING hooks
    have completed (to update status and release workspaces), but we
    don't start new stale hooks.
    """
    workflow = LoopWorkflow()
    cs = _make_changespec(
        status="Submitted",
        hooks=[
            # Use PASSED status - no completion check needed, no stale hooks
            _make_hook(command="test_cmd", status="PASSED", timestamp="240101120000")
        ],
    )

    result = workflow._check_hooks(cs)

    # No updates since hook is already PASSED (not RUNNING, not stale)
    assert result == []


def test_check_hooks_no_hooks() -> None:
    """Test _check_hooks returns empty when no hooks."""
    workflow = LoopWorkflow()
    cs = _make_changespec(hooks=None)

    result = workflow._check_hooks(cs)

    assert result == []


def test_check_hooks_empty_hooks() -> None:
    """Test _check_hooks returns empty when hooks list is empty."""
    workflow = LoopWorkflow()
    cs = _make_changespec(hooks=[])

    result = workflow._check_hooks(cs)

    assert result == []


def test_run_hooks_cycle_no_updates() -> None:
    """Test _run_hooks_cycle returns 0 when no changespecs have hooks."""
    workflow = LoopWorkflow()

    with patch("work.loop.find_all_changespecs", return_value=[]):
        result = workflow._run_hooks_cycle()

    assert result == 0
