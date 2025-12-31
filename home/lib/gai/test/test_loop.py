"""Tests for the loop workflow."""

from unittest.mock import MagicMock, patch

from ace.changespec import ChangeSpec, CommentEntry, HookEntry, HookStatusLine
from ace.loop import LoopWorkflow
from ace.loop.hook_checks import check_hooks
from ace.loop.suffix_transforms import (
    acknowledge_terminal_status_markers,
    check_ready_to_mail,
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
        commits=None,
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

    with patch("ace.loop.core.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "2025-01-15 12:30:00"
        workflow._log("Test message")

    workflow.console.print.assert_called_once()
    call_arg = workflow.console.print.call_args[0][0]
    assert "[2025-01-15 12:30:00] Test message" in call_arg


def test_log_with_style() -> None:
    """Test _log outputs timestamped message with style."""
    workflow = LoopWorkflow()
    workflow.console = MagicMock()

    with patch("ace.loop.core.datetime") as mock_datetime:
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

    with patch("ace.loop.core.should_check", return_value=False):
        result = workflow._check_status(cs)
    assert result is None


@patch("ace.loop.core.update_last_checked")
@patch("ace.loop.core.should_check", return_value=True)
@patch("ace.loop.core.is_parent_submitted", return_value=True)
@patch("ace.loop.core.is_cl_submitted", return_value=True)
@patch("ace.loop.core.transition_changespec_status")
@patch("ace.loop.core.clear_cache_entry")
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


@patch("ace.loop.core.update_last_checked")
@patch("ace.loop.core.should_check", return_value=True)
@patch("ace.loop.core.is_parent_submitted", return_value=True)
@patch("ace.loop.core.is_cl_submitted", return_value=False)
@patch("ace.loop.core.transition_changespec_status")
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


def test_run_hooks_cycle_no_updates() -> None:
    """Test _run_hooks_cycle returns 0 when no changespecs have hooks."""
    workflow = LoopWorkflow()

    with patch("ace.loop.core.find_all_changespecs", return_value=[]):
        result = workflow._run_hooks_cycle()

    assert result == 0


def test_acknowledge_terminal_status_markers_skips_non_terminal() -> None:
    """Test acknowledge_terminal_status_markers skips non-terminal status."""
    from ace.changespec import CommitEntry

    cs = ChangeSpec(
        name="test",
        description="Test",
        parent=None,
        cl="123",
        status="Mailed",  # Not terminal
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        commits=[
            CommitEntry(
                number=1,
                note="Test",
                suffix="NEW PROPOSAL",
                suffix_type="error",
            )
        ],
    )

    result = acknowledge_terminal_status_markers(cs)

    assert result == []


def test_acknowledge_terminal_status_markers_skips_drafted() -> None:
    """Test acknowledge_terminal_status_markers skips Drafted status."""
    from ace.changespec import CommitEntry

    cs = ChangeSpec(
        name="test",
        description="Test",
        parent=None,
        cl="123",
        status="Drafted",  # Not terminal
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        commits=[
            CommitEntry(
                number=1,
                note="Test",
                suffix="NEW PROPOSAL",
                suffix_type="error",
            )
        ],
    )

    result = acknowledge_terminal_status_markers(cs)

    assert result == []


def test_acknowledge_terminal_status_markers_processes_submitted() -> None:
    """Test acknowledge_terminal_status_markers processes Submitted status."""
    from ace.changespec import CommitEntry

    cs = ChangeSpec(
        name="test",
        description="Test",
        parent=None,
        cl="123",
        status="Submitted",  # Terminal
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        commits=[
            CommitEntry(
                number=1,
                note="Test",
                suffix="NEW PROPOSAL",
                suffix_type="error",
            )
        ],
    )

    with patch(
        "ace.loop.suffix_transforms.update_commit_entry_suffix", return_value=True
    ):
        result = acknowledge_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Cleared HISTORY" in result[0]


def test_acknowledge_terminal_status_markers_processes_reverted() -> None:
    """Test acknowledge_terminal_status_markers processes Reverted status."""
    from ace.changespec import CommitEntry

    cs = ChangeSpec(
        name="test",
        description="Test",
        parent=None,
        cl="123",
        status="Reverted",  # Terminal
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        commits=[
            CommitEntry(
                number=1,
                note="Test",
                suffix="NEW PROPOSAL",
                suffix_type="error",
            )
        ],
    )

    with patch(
        "ace.loop.suffix_transforms.update_commit_entry_suffix", return_value=True
    ):
        result = acknowledge_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Cleared HISTORY" in result[0]


def test_acknowledge_terminal_status_markers_skips_plain_suffix() -> None:
    """Test acknowledge_terminal_status_markers skips plain suffixes (only strips error)."""
    from ace.changespec import CommitEntry

    cs = ChangeSpec(
        name="test",
        description="Test",
        parent=None,
        cl="123",
        status="Submitted",  # Terminal
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        commits=[
            CommitEntry(
                number=1,
                note="Test",
                suffix="NEW PROPOSAL",
                suffix_type=None,  # Plain suffix, not error
            )
        ],
    )

    result = acknowledge_terminal_status_markers(cs)

    assert result == []


def test_acknowledge_terminal_status_markers_processes_hooks() -> None:
    """Test acknowledge_terminal_status_markers processes hook error suffixes."""
    hook = HookEntry(
        command="test_cmd",
        status_lines=[
            HookStatusLine(
                commit_entry_num="1",
                timestamp="241226_120000",
                status="FAILED",
                suffix="Hook Command Failed",
                suffix_type="error",
            )
        ],
    )
    cs = ChangeSpec(
        name="test",
        description="Test",
        parent=None,
        cl="123",
        status="Submitted",  # Terminal
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        hooks=[hook],
    )

    with patch(
        "ace.loop.suffix_transforms.update_changespec_hooks_field",
        return_value=True,
    ):
        result = acknowledge_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Cleared HOOK" in result[0]


def test_acknowledge_terminal_status_markers_processes_comments() -> None:
    """Test acknowledge_terminal_status_markers processes comment error suffixes."""
    comment = CommentEntry(
        reviewer="reviewer",
        file_path="~/.gai/comments/test.json",
        suffix="ZOMBIE",
        suffix_type="error",
    )
    cs = ChangeSpec(
        name="test",
        description="Test",
        parent=None,
        cl="123",
        status="Submitted",  # Terminal
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        comments=[comment],
    )

    with patch("ace.loop.suffix_transforms.clear_comment_suffix", return_value=True):
        result = acknowledge_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Cleared COMMENT" in result[0]


# === READY TO MAIL Tests ===


def test_check_ready_to_mail_adds_suffix_for_drafted_no_errors() -> None:
    """Test check_ready_to_mail adds suffix for Drafted status with no errors."""
    changespec = _make_changespec(status="Drafted")
    all_changespecs = [changespec]

    with patch(
        "ace.loop.suffix_transforms.add_ready_to_mail_suffix", return_value=True
    ):
        result = check_ready_to_mail(changespec, all_changespecs)

    assert len(result) == 1
    assert "Added READY TO MAIL suffix" in result[0]


def test_check_ready_to_mail_skips_non_drafted_status() -> None:
    """Test check_ready_to_mail skips non-Drafted statuses."""
    changespec = _make_changespec(status="Mailed")
    all_changespecs = [changespec]

    result = check_ready_to_mail(changespec, all_changespecs)

    assert len(result) == 0


def test_check_ready_to_mail_skips_already_has_suffix() -> None:
    """Test check_ready_to_mail skips if suffix already present."""
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)")
    all_changespecs = [changespec]

    result = check_ready_to_mail(changespec, all_changespecs)

    assert len(result) == 0


def test_check_ready_to_mail_skips_with_error_suffix_in_hooks() -> None:
    """Test check_ready_to_mail skips if hook has error suffix."""
    hook = HookEntry(
        command="make lint",
        status_lines=[
            HookStatusLine(
                commit_entry_num="1",
                timestamp="241228_120000",
                status="FAILED",
                suffix="Hook Command Failed",
                suffix_type="error",
            )
        ],
    )
    changespec = _make_changespec(status="Drafted", hooks=[hook])
    all_changespecs = [changespec]

    result = check_ready_to_mail(changespec, all_changespecs)

    assert len(result) == 0


def test_check_ready_to_mail_skips_parent_not_ready() -> None:
    """Test check_ready_to_mail skips if parent is not ready."""
    parent = _make_changespec(name="parent_cs", status="Drafted")
    child = ChangeSpec(
        name="child_cs",
        description="Test description",
        parent="parent_cs",
        cl="http://cl/12346",
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=10,
        commits=None,
        hooks=None,
        comments=None,
    )
    all_changespecs = [parent, child]

    result = check_ready_to_mail(child, all_changespecs)

    assert len(result) == 0


def test_check_ready_to_mail_allows_parent_submitted() -> None:
    """Test check_ready_to_mail allows when parent is Submitted."""
    parent = _make_changespec(name="parent_cs", status="Submitted")
    child = ChangeSpec(
        name="child_cs",
        description="Test description",
        parent="parent_cs",
        cl="http://cl/12346",
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=10,
        commits=None,
        hooks=None,
        comments=None,
    )
    all_changespecs = [parent, child]

    with patch(
        "ace.loop.suffix_transforms.add_ready_to_mail_suffix", return_value=True
    ):
        result = check_ready_to_mail(child, all_changespecs)

    assert len(result) == 1
    assert "Added READY TO MAIL suffix" in result[0]


def test_check_ready_to_mail_skips_parent_with_only_suffix() -> None:
    """Test check_ready_to_mail skips when parent only has READY TO MAIL suffix.

    Parent must be Mailed or Submitted, not just have the READY TO MAIL suffix.
    """
    parent = _make_changespec(name="parent_cs", status="Drafted - (!: READY TO MAIL)")
    child = ChangeSpec(
        name="child_cs",
        description="Test description",
        parent="parent_cs",
        cl="http://cl/12346",
        status="Drafted",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=10,
        commits=None,
        hooks=None,
        comments=None,
    )
    all_changespecs = [parent, child]

    result = check_ready_to_mail(child, all_changespecs)

    # Suffix should NOT be added because parent is not Mailed or Submitted
    assert len(result) == 0


def test_check_ready_to_mail_removes_suffix_when_error_appears() -> None:
    """Test check_ready_to_mail removes suffix when error suffix appears."""
    hook = HookEntry(
        command="make lint",
        status_lines=[
            HookStatusLine(
                commit_entry_num="1",
                timestamp="241228_120000",
                status="FAILED",
                suffix="Hook Command Failed",
                suffix_type="error",
            )
        ],
    )
    # ChangeSpec has READY TO MAIL suffix but now has an error
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)", hooks=[hook])
    all_changespecs = [changespec]

    with patch(
        "ace.loop.suffix_transforms.remove_ready_to_mail_suffix", return_value=True
    ):
        result = check_ready_to_mail(changespec, all_changespecs)

    assert len(result) == 1
    assert "Removed READY TO MAIL suffix (error suffix appeared)" in result[0]


def test_check_ready_to_mail_removes_suffix_when_parent_not_ready() -> None:
    """Test check_ready_to_mail removes suffix when parent is no longer ready."""
    # Parent no longer has READY TO MAIL suffix and is still Drafted
    parent = _make_changespec(name="parent_cs", status="Drafted")
    # Child has the suffix but parent is not ready anymore
    child = ChangeSpec(
        name="child_cs",
        description="Test description",
        parent="parent_cs",
        cl="http://cl/12346",
        status="Drafted - (!: READY TO MAIL)",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=10,
        commits=None,
        hooks=None,
        comments=None,
    )
    all_changespecs = [parent, child]

    with patch(
        "ace.loop.suffix_transforms.remove_ready_to_mail_suffix", return_value=True
    ):
        result = check_ready_to_mail(child, all_changespecs)

    assert len(result) == 1
    assert "Removed READY TO MAIL suffix (parent no longer ready)" in result[0]


def test_check_ready_to_mail_keeps_suffix_when_conditions_still_met() -> None:
    """Test check_ready_to_mail keeps suffix when conditions are still met."""
    # ChangeSpec has suffix and conditions are still met (no parent, no errors)
    changespec = _make_changespec(status="Drafted - (!: READY TO MAIL)")
    all_changespecs = [changespec]

    result = check_ready_to_mail(changespec, all_changespecs)

    # No updates - suffix should remain
    assert len(result) == 0
