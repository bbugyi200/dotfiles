"""Tests for the loop workflow."""

from unittest.mock import MagicMock, patch

from work.changespec import ChangeSpec, CommentEntry, HookEntry, HookStatusLine
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
    comments: list[CommentEntry] | None = None,
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
        comments=comments,
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

    with patch("work.loop.core.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "2025-01-15 12:30:00"
        workflow._log("Test message")

    workflow.console.print.assert_called_once()
    call_arg = workflow.console.print.call_args[0][0]
    assert "[2025-01-15 12:30:00] Test message" in call_arg


def test_log_with_style() -> None:
    """Test _log outputs timestamped message with style."""
    workflow = LoopWorkflow()
    workflow.console = MagicMock()

    with patch("work.loop.core.datetime") as mock_datetime:
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

    with patch("work.loop.core.should_check", return_value=False):
        result = workflow._check_status(cs)
    assert result is None


@patch("work.loop.core.update_last_checked")
@patch("work.loop.core.should_check", return_value=True)
@patch("work.loop.core.is_parent_submitted", return_value=True)
@patch("work.loop.core.is_cl_submitted", return_value=True)
@patch("work.loop.core.transition_changespec_status")
@patch("work.loop.core.clear_cache_entry")
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


@patch("work.loop.core.update_last_checked")
@patch("work.loop.core.should_check", return_value=True)
@patch("work.loop.core.is_parent_submitted", return_value=True)
@patch("work.loop.core.is_cl_submitted", return_value=False)
@patch("work.loop.core.transition_changespec_status")
def test_check_status_mailed_not_submitted(
    mock_transition: MagicMock,
    mock_is_submitted: MagicMock,
    mock_is_parent: MagicMock,
    mock_should_check: MagicMock,
    mock_update: MagicMock,
) -> None:
    """Test _check_status returns None when Mailed CL is not yet submitted."""
    mock_transition.return_value = (True, "Mailed", None)

    workflow = LoopWorkflow()
    cs = _make_changespec(status="Mailed")

    result = workflow._check_status(cs)

    # When CL is not submitted, status stays as Mailed (no change)
    assert result is None


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

    with patch("work.loop.core.find_all_changespecs", return_value=[]):
        result = workflow._run_hooks_cycle()

    assert result == 0


# Tests for _check_author_comments


def test_check_author_comments_skips_non_eligible_status() -> None:
    """Test _check_author_comments skips non-Drafted/Mailed statuses."""
    workflow = LoopWorkflow()
    cs = _make_changespec(status="Submitted")

    result = workflow._check_author_comments(cs)

    assert result == []


def test_check_author_comments_skips_when_reviewer_entry_exists() -> None:
    """Test _check_author_comments skips when [reviewer] entry exists."""
    workflow = LoopWorkflow()
    reviewer_entry = CommentEntry(
        reviewer="reviewer",
        file_path="/path/to/comments.json",
        suffix=None,
    )
    cs = _make_changespec(status="Mailed", comments=[reviewer_entry])

    result = workflow._check_author_comments(cs)

    assert result == []


@patch("work.loop.core.get_workspace_directory")
def test_check_author_comments_runs_for_drafted_status(
    mock_get_workspace: MagicMock,
) -> None:
    """Test _check_author_comments runs for Drafted status."""
    mock_get_workspace.return_value = "/workspace/dir"
    workflow = LoopWorkflow()
    cs = _make_changespec(status="Drafted")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""  # No comments
        mock_run.return_value.returncode = 0
        result = workflow._check_author_comments(cs)

    mock_run.assert_called_once()
    assert result == []


@patch("work.loop.core.get_workspace_directory")
def test_check_author_comments_runs_for_mailed_status(
    mock_get_workspace: MagicMock,
) -> None:
    """Test _check_author_comments runs for Mailed status."""
    mock_get_workspace.return_value = "/workspace/dir"
    workflow = LoopWorkflow()
    cs = _make_changespec(status="Mailed")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""  # No comments
        mock_run.return_value.returncode = 0
        result = workflow._check_author_comments(cs)

    mock_run.assert_called_once()
    assert result == []


@patch("work.loop.core.update_changespec_comments_field")
@patch("work.loop.core.get_comments_file_path")
@patch("work.loop.core.generate_comments_timestamp")
@patch("work.loop.core.get_workspace_directory")
def test_check_author_comments_creates_entry_when_comments_found(
    mock_get_workspace: MagicMock,
    mock_timestamp: MagicMock,
    mock_file_path: MagicMock,
    mock_update_comments: MagicMock,
) -> None:
    """Test _check_author_comments creates [author] entry when #gai comments found."""
    mock_get_workspace.return_value = "/workspace/dir"
    mock_timestamp.return_value = "241226_120000"
    mock_file_path.return_value = (
        "/home/user/.gai/comments/test_cs-author-241226_120000.json"
    )

    workflow = LoopWorkflow()
    cs = _make_changespec(status="Drafted")

    with (
        patch("subprocess.run") as mock_run,
        patch("builtins.open", MagicMock()),
    ):
        mock_run.return_value.stdout = '{"comments": "test"}'  # Has comments
        mock_run.return_value.returncode = 0
        result = workflow._check_author_comments(cs)

    assert result == ["Added [author] comment entry"]
    mock_update_comments.assert_called_once()


@patch("work.loop.core.get_workspace_directory")
def test_check_author_comments_removes_entry_when_no_comments(
    mock_get_workspace: MagicMock,
) -> None:
    """Test _check_author_comments removes [author] entry when no comments found."""
    mock_get_workspace.return_value = "/workspace/dir"
    workflow = LoopWorkflow()
    author_entry = CommentEntry(
        reviewer="author",
        file_path="/path/to/comments.json",
        suffix=None,  # No suffix - can be removed
    )
    cs = _make_changespec(status="Drafted", comments=[author_entry])

    with (
        patch("subprocess.run") as mock_run,
        patch("work.loop.core.remove_comment_entry") as mock_remove,
    ):
        mock_run.return_value.stdout = ""  # No comments
        mock_run.return_value.returncode = 0
        result = workflow._check_author_comments(cs)

    assert result == ["Removed [author] comment entry (no comments)"]
    mock_remove.assert_called_once()


@patch("work.loop.core.get_workspace_directory")
def test_check_author_comments_preserves_entry_with_suffix(
    mock_get_workspace: MagicMock,
) -> None:
    """Test _check_author_comments preserves [author] entry with suffix (CRS running)."""
    mock_get_workspace.return_value = "/workspace/dir"
    workflow = LoopWorkflow()
    author_entry = CommentEntry(
        reviewer="author",
        file_path="/path/to/comments.json",
        suffix="241226_120000",  # Has suffix - CRS is running
    )
    cs = _make_changespec(status="Drafted", comments=[author_entry])

    with (
        patch("subprocess.run") as mock_run,
        patch("work.loop.core.remove_comment_entry") as mock_remove,
    ):
        mock_run.return_value.stdout = ""  # No comments
        mock_run.return_value.returncode = 0
        result = workflow._check_author_comments(cs)

    # Entry should not be removed because it has a suffix
    assert result == []
    mock_remove.assert_not_called()
