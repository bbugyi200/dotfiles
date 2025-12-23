"""Tests for the monitor workflow."""

from unittest.mock import MagicMock, patch

from work.changespec import ChangeSpec, HookEntry
from work.monitor import MonitorWorkflow


def _make_changespec(
    name: str = "test_cs",
    status: str = "Drafted",
    presubmit: str | None = None,
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
        presubmit=presubmit,
        history=None,
        hooks=hooks,
    )


def test_monitor_workflow_init_default_interval() -> None:
    """Test MonitorWorkflow initializes with default interval."""
    workflow = MonitorWorkflow()
    assert workflow.interval_seconds == 300


def test_monitor_workflow_init_custom_interval() -> None:
    """Test MonitorWorkflow initializes with custom interval."""
    workflow = MonitorWorkflow(interval_seconds=60)
    assert workflow.interval_seconds == 60


def test_monitor_workflow_init_default_hook_interval() -> None:
    """Test MonitorWorkflow initializes with default hook interval."""
    workflow = MonitorWorkflow()
    assert workflow.hook_interval_seconds == 10


def test_monitor_workflow_init_custom_hook_interval() -> None:
    """Test MonitorWorkflow initializes with custom hook interval."""
    workflow = MonitorWorkflow(hook_interval_seconds=30)
    assert workflow.hook_interval_seconds == 30


def test_log_without_style() -> None:
    """Test _log outputs timestamped message without style."""
    workflow = MonitorWorkflow()
    workflow.console = MagicMock()

    with patch("work.monitor.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "2025-01-15 12:30:00"
        workflow._log("Test message")

    workflow.console.print.assert_called_once()
    call_arg = workflow.console.print.call_args[0][0]
    assert "[2025-01-15 12:30:00] Test message" in call_arg


def test_log_with_style() -> None:
    """Test _log outputs timestamped message with style."""
    workflow = MonitorWorkflow()
    workflow.console = MagicMock()

    with patch("work.monitor.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "2025-01-15 12:30:00"
        workflow._log("Test message", style="green")

    workflow.console.print.assert_called_once()
    call_arg = workflow.console.print.call_args[0][0]
    assert "[green]" in call_arg
    assert "Test message" in call_arg


def test_count_projects_single_project() -> None:
    """Test _count_projects with single project."""
    workflow = MonitorWorkflow()
    changespecs = [
        _make_changespec(name="cs1", file_path="/path/to/project1.gp"),
        _make_changespec(name="cs2", file_path="/path/to/project1.gp"),
    ]
    assert workflow._count_projects(changespecs) == 1


def test_count_projects_multiple_projects() -> None:
    """Test _count_projects with multiple projects."""
    workflow = MonitorWorkflow()
    changespecs = [
        _make_changespec(name="cs1", file_path="/path/to/project1.gp"),
        _make_changespec(name="cs2", file_path="/path/to/project2.gp"),
        _make_changespec(name="cs3", file_path="/path/to/project1.gp"),
    ]
    assert workflow._count_projects(changespecs) == 2


def test_count_projects_empty_list() -> None:
    """Test _count_projects with empty list."""
    workflow = MonitorWorkflow()
    assert workflow._count_projects([]) == 0


def test_check_status_skips_non_syncable_status() -> None:
    """Test _check_status returns None for non-syncable statuses."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(status="Drafted")  # Not in SYNCABLE_STATUSES

    result = workflow._check_status(cs)
    assert result is None


def test_check_status_skips_recently_checked() -> None:
    """Test _check_status returns None when recently checked."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(status="Mailed")

    with patch("work.monitor.should_check", return_value=False):
        result = workflow._check_status(cs)
    assert result is None


@patch("work.monitor.update_last_checked")
@patch("work.monitor.should_check", return_value=True)
@patch("work.monitor.is_parent_submitted", return_value=True)
@patch("work.monitor.is_cl_submitted", return_value=True)
@patch("work.monitor.transition_changespec_status")
@patch("work.monitor.clear_cache_entry")
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

    workflow = MonitorWorkflow()
    cs = _make_changespec(status="Mailed")

    result = workflow._check_status(cs)

    assert result == "Status changed Mailed -> Submitted"
    mock_clear_cache.assert_called_once_with(cs.name)


@patch("work.monitor.update_last_checked")
@patch("work.monitor.should_check", return_value=True)
@patch("work.monitor.is_parent_submitted", return_value=True)
@patch("work.monitor.is_cl_submitted", return_value=False)
@patch("work.monitor.has_pending_comments", return_value=True)
@patch("work.monitor.transition_changespec_status")
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

    workflow = MonitorWorkflow()
    cs = _make_changespec(status="Mailed")

    result = workflow._check_status(cs)

    assert result == "Status changed Mailed -> Changes Requested"


def test_check_presubmit_skips_if_not_needed() -> None:
    """Test _check_presubmit returns None when presubmit doesn't need checking."""
    workflow = MonitorWorkflow()
    # No presubmit field
    cs = _make_changespec(presubmit=None)

    result = workflow._check_presubmit(cs)
    assert result is None


def test_check_presubmit_skips_if_already_passed() -> None:
    """Test _check_presubmit returns None when presubmit already passed."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(presubmit="/path/to/log.txt (PASSED)")

    result = workflow._check_presubmit(cs)
    assert result is None


def test_check_presubmit_skips_recently_checked() -> None:
    """Test _check_presubmit returns None when recently checked."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(presubmit="/path/to/log.txt")

    with patch("work.monitor.should_check", return_value=False):
        result = workflow._check_presubmit(cs)
    assert result is None


@patch("work.monitor.update_last_checked")
@patch("work.monitor.should_check", return_value=True)
@patch("work.monitor.get_presubmit_file_path", return_value="/path/to/log.txt")
@patch("work.monitor.get_presubmit_file_age_seconds", return_value=100)
@patch("work.monitor.check_presubmit_status", return_value=0)
@patch("work.monitor.update_changespec_presubmit_tag", return_value=True)
@patch("work.monitor.clear_cache_entry")
def test_check_presubmit_detects_passed(
    mock_clear_cache: MagicMock,
    mock_update_tag: MagicMock,
    mock_check_status: MagicMock,
    mock_age: MagicMock,
    mock_path: MagicMock,
    mock_should_check: MagicMock,
    mock_update: MagicMock,
) -> None:
    """Test _check_presubmit detects passed presubmit."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(presubmit="/path/to/log.txt")

    result = workflow._check_presubmit(cs)

    assert result == "Presubmit completed (PASSED)"
    mock_clear_cache.assert_called_once()


@patch("work.monitor.update_last_checked")
@patch("work.monitor.should_check", return_value=True)
@patch("work.monitor.get_presubmit_file_path", return_value="/path/to/log.txt")
@patch("work.monitor.get_presubmit_file_age_seconds", return_value=100)
@patch("work.monitor.check_presubmit_status", return_value=1)
@patch("work.monitor.update_changespec_presubmit_tag", return_value=True)
def test_check_presubmit_detects_failed(
    mock_update_tag: MagicMock,
    mock_check_status: MagicMock,
    mock_age: MagicMock,
    mock_path: MagicMock,
    mock_should_check: MagicMock,
    mock_update: MagicMock,
) -> None:
    """Test _check_presubmit detects failed presubmit."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(presubmit="/path/to/log.txt")

    result = workflow._check_presubmit(cs)

    assert result == "Presubmit completed (FAILED)"


@patch("work.monitor.update_last_checked")
@patch("work.monitor.should_check", return_value=True)
@patch("work.monitor.get_presubmit_file_path", return_value="/path/to/log.txt")
@patch(
    "work.monitor.get_presubmit_file_age_seconds",
    return_value=25 * 60 * 60,  # 25 hours - over zombie threshold
)
@patch("work.monitor.update_changespec_presubmit_tag", return_value=True)
def test_check_presubmit_detects_zombie(
    mock_update_tag: MagicMock,
    mock_age: MagicMock,
    mock_path: MagicMock,
    mock_should_check: MagicMock,
    mock_update: MagicMock,
) -> None:
    """Test _check_presubmit detects zombie presubmit (running > 24h)."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(presubmit="/path/to/log.txt")

    result = workflow._check_presubmit(cs)

    assert result == "Presubmit marked as ZOMBIE (running > 24h)"


def test_check_single_changespec_combines_checks() -> None:
    """Test _check_single_changespec runs both status and presubmit checks."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(status="Mailed", presubmit="/path/to/log.txt")

    with (
        patch.object(workflow, "_should_check_status", return_value=(True, None)),
        patch.object(workflow, "_should_check_presubmit", return_value=(True, None)),
        patch.object(
            workflow, "_check_status", return_value="Status changed Mailed -> Submitted"
        ),
        patch.object(
            workflow, "_check_presubmit", return_value="Presubmit completed (PASSED)"
        ),
    ):
        updates, checked_types, skip_reasons = workflow._check_single_changespec(cs)

    assert len(updates) == 2
    assert "Status changed Mailed -> Submitted" in updates
    assert "Presubmit completed (PASSED)" in updates
    assert "status" in checked_types
    assert "presubmit" in checked_types
    assert skip_reasons == []


def test_check_single_changespec_no_updates() -> None:
    """Test _check_single_changespec returns empty updates when nothing checked."""
    workflow = MonitorWorkflow()
    cs = _make_changespec()  # status="Drafted" which is not syncable

    # With default Drafted status, status check is skipped (not syncable)
    # With no presubmit, presubmit check is also skipped
    updates, checked_types, skip_reasons = workflow._check_single_changespec(cs)

    assert updates == []
    assert checked_types == []
    assert len(skip_reasons) == 2  # Both status and presubmit skipped


def test_check_hooks_skips_reverted() -> None:
    """Test _check_hooks skips Reverted status."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(
        status="Reverted",
        hooks=[
            HookEntry(command="test_cmd", status="RUNNING", timestamp="240101120000")
        ],
    )

    result = workflow._check_hooks(cs)

    assert result == []


def test_check_hooks_skips_submitted() -> None:
    """Test _check_hooks skips Submitted status."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(
        status="Submitted",
        hooks=[
            HookEntry(command="test_cmd", status="RUNNING", timestamp="240101120000")
        ],
    )

    result = workflow._check_hooks(cs)

    assert result == []


def test_check_hooks_no_hooks() -> None:
    """Test _check_hooks returns empty when no hooks."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(hooks=None)

    result = workflow._check_hooks(cs)

    assert result == []


def test_check_hooks_empty_hooks() -> None:
    """Test _check_hooks returns empty when hooks list is empty."""
    workflow = MonitorWorkflow()
    cs = _make_changespec(hooks=[])

    result = workflow._check_hooks(cs)

    assert result == []


def test_run_hooks_cycle_no_updates() -> None:
    """Test _run_hooks_cycle returns 0 when no changespecs have hooks."""
    workflow = MonitorWorkflow()

    with patch("work.monitor.find_all_changespecs", return_value=[]):
        result = workflow._run_hooks_cycle()

    assert result == 0
