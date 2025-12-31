"""Tests for acknowledge_terminal_status_markers in suffix transforms."""

from unittest.mock import patch

from ace.changespec import (
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
    HookStatusLine,
)
from ace.loop.suffix_transforms import acknowledge_terminal_status_markers


def test_acknowledge_terminal_status_markers_skips_non_terminal() -> None:
    """Test acknowledge_terminal_status_markers skips non-terminal status."""
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


def test_acknowledge_terminal_status_markers_processes_history_running_agent() -> None:
    """Test acknowledge_terminal_status_markers processes running_agent suffixes."""
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
                suffix="241226_120000",
                suffix_type="running_agent",
            )
        ],
    )

    with patch(
        "ace.loop.suffix_transforms.update_commit_entry_suffix", return_value=True
    ):
        result = acknowledge_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Cleared HISTORY" in result[0]


def test_acknowledge_terminal_status_markers_processes_hooks_running_agent() -> None:
    """Test acknowledge_terminal_status_markers processes hook running_agent suffixes."""
    hook = HookEntry(
        command="test_cmd",
        status_lines=[
            HookStatusLine(
                commit_entry_num="1",
                timestamp="241226_120000",
                status="RUNNING",
                suffix="241226_120000",
                suffix_type="running_agent",
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


def test_acknowledge_terminal_status_markers_processes_hooks_empty_running_agent() -> (
    None
):
    """Test acknowledge_terminal_status_markers clears empty running_agent '- (@)' markers."""
    hook = HookEntry(
        command="test_cmd",
        status_lines=[
            HookStatusLine(
                commit_entry_num="1",
                timestamp="241226_120000",
                status="RUNNING",
                suffix="",  # Empty suffix renders as "- (@)"
                suffix_type="running_agent",
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


def test_acknowledge_terminal_status_markers_processes_comments_running_agent() -> None:
    """Test acknowledge_terminal_status_markers processes comment running_agent suffixes."""
    comment = CommentEntry(
        reviewer="reviewer",
        file_path="~/.gai/comments/test.json",
        suffix="241226_120000",
        suffix_type="running_agent",
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
