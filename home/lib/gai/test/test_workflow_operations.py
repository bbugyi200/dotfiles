"""Tests for workflow operations and available workflows."""

from ace.changespec import ChangeSpec, CommentEntry, HookEntry, HookStatusLine
from ace.operations import get_available_workflows


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


def test_get_available_workflows_drafted() -> None:
    """Test that Drafted status returns no workflows."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Drafted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_mailed() -> None:
    """Test that Mailed status returns no workflows."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Mailed",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_with_comments_entry() -> None:
    """Test that COMMENTS entry without suffix returns crs workflow."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Mailed",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
        comments=[
            CommentEntry(
                reviewer="critique",
                file_path="~/.gai/comments/test-critique-241226_120000.json",
                suffix=None,  # No suffix = CRS available
            )
        ],
    )
    workflows = get_available_workflows(cs)
    assert workflows == ["crs"]


def test_get_available_workflows_with_failed_test_targets() -> None:
    """Test that failing test target hooks trigger fix-hook and fix-tests workflows."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Drafted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
        hooks=[
            _make_hook(command="bb_rabbit_test //target1", status="FAILED"),
        ],
    )
    workflows = get_available_workflows(cs)
    # fix-hook is available for any failing hook, fix-tests for failing test target hooks
    assert workflows == ["fix-hook", "fix-tests"]


def test_get_available_workflows_with_non_test_target_failed_hook() -> None:
    """Test that failing non-test hooks trigger only fix-hook workflow."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Drafted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
        hooks=[
            _make_hook(command="flake8 src", status="FAILED"),
        ],
    )
    workflows = get_available_workflows(cs)
    # fix-hook is available for any failing hook, but fix-tests only for test targets
    assert workflows == ["fix-hook"]


def test_get_available_workflows_submitted_status() -> None:
    """Test that Submitted status returns no workflows."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Submitted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_no_hooks() -> None:
    """Test that no workflows are returned when hooks is None."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Drafted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
        hooks=None,
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_empty_hooks() -> None:
    """Test that no workflows are returned when hooks list is empty."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Drafted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
        hooks=[],
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_all_hooks_passing() -> None:
    """Test that no fix-hook workflow when all hooks passing."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Drafted",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
        hooks=[
            _make_hook(command="bb_rabbit_test //target1", status="PASSED"),
            _make_hook(command="flake8 src", status="PASSED"),
        ],
    )
    workflows = get_available_workflows(cs)
    assert workflows == []


def test_get_available_workflows_with_comments_and_failing_hook() -> None:
    """Test that both fix-hook and crs workflows are returned."""
    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Mailed",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
        hooks=[
            _make_hook(command="flake8 src", status="FAILED"),
        ],
        comments=[
            CommentEntry(
                reviewer="critique",
                file_path="~/.gai/comments/test-critique-241226_120000.json",
                suffix=None,  # No suffix = CRS available
            )
        ],
    )
    workflows = get_available_workflows(cs)
    # Both fix-hook and crs should be available
    assert workflows == ["fix-hook", "crs"]
