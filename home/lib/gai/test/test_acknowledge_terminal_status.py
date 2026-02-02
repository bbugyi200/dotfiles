"""Tests for strip_terminal_status_markers in suffix transforms."""

from unittest.mock import patch

from ace.changespec import (
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
    HookStatusLine,
    MentorEntry,
    MentorStatusLine,
)
from ace.scheduler.suffix_transforms import strip_terminal_status_markers


def test_strip_terminal_status_markers_skips_non_terminal() -> None:
    """Test strip_terminal_status_markers skips non-terminal status."""
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

    result = strip_terminal_status_markers(cs)

    assert result == []


def test_strip_terminal_status_markers_skips_drafted() -> None:
    """Test strip_terminal_status_markers skips Drafted status."""
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

    result = strip_terminal_status_markers(cs)

    assert result == []


def test_strip_terminal_status_markers_processes_submitted() -> None:
    """Test strip_terminal_status_markers processes Submitted status."""
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
        "ace.scheduler.suffix_transforms.update_commit_entry_suffix", return_value=True
    ):
        result = strip_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Cleared HISTORY" in result[0]


def test_strip_terminal_status_markers_processes_reverted() -> None:
    """Test strip_terminal_status_markers processes Reverted status."""
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
        "ace.scheduler.suffix_transforms.update_commit_entry_suffix", return_value=True
    ):
        result = strip_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Cleared HISTORY" in result[0]


def test_strip_terminal_status_markers_skips_plain_suffix() -> None:
    """Test strip_terminal_status_markers skips plain suffixes (only strips error)."""
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

    result = strip_terminal_status_markers(cs)

    assert result == []


def test_strip_terminal_status_markers_processes_hooks() -> None:
    """Test strip_terminal_status_markers converts hook error suffixes to plain."""
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
        "ace.scheduler.suffix_transforms.update_changespec_hooks_field",
        return_value=True,
    ):
        result = strip_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Stripped error marker from HOOK" in result[0]


def test_strip_terminal_status_markers_processes_comments() -> None:
    """Test strip_terminal_status_markers processes comment error suffixes."""
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

    with patch(
        "ace.scheduler.suffix_transforms.clear_comment_suffix", return_value=True
    ):
        result = strip_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Cleared COMMENT" in result[0]


def test_strip_terminal_status_markers_processes_history_running_agent() -> None:
    """Test strip_terminal_status_markers processes running_agent suffixes."""
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
        "ace.scheduler.suffix_transforms.update_commit_entry_suffix", return_value=True
    ):
        result = strip_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Cleared HISTORY" in result[0]


def test_strip_terminal_status_markers_processes_hooks_running_agent() -> None:
    """Test strip_terminal_status_markers converts running_agent to killed_agent."""
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
        "ace.scheduler.suffix_transforms.update_changespec_hooks_field",
        return_value=True,
    ):
        result = strip_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Converted HOOK" in result[0]
    assert "to killed_agent" in result[0]


def test_strip_terminal_status_markers_processes_hooks_empty_running_agent() -> None:
    """Test strip_terminal_status_markers converts empty running_agent to killed_agent."""
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
        "ace.scheduler.suffix_transforms.update_changespec_hooks_field",
        return_value=True,
    ):
        result = strip_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Converted HOOK" in result[0]
    assert "to killed_agent" in result[0]


def test_strip_terminal_status_markers_processes_comments_running_agent() -> None:
    """Test strip_terminal_status_markers processes comment running_agent suffixes."""
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

    with patch(
        "ace.scheduler.suffix_transforms.clear_comment_suffix", return_value=True
    ):
        result = strip_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Cleared COMMENT" in result[0]


def test_strip_terminal_status_markers_processes_mentors_running_agent() -> None:
    """Test strip_terminal_status_markers converts mentor running_agent to killed_agent."""
    mentor = MentorEntry(
        entry_id="1",
        profiles=["default"],
        status_lines=[
            MentorStatusLine(
                profile_name="default",
                mentor_name="test_mentor",
                status="RUNNING",
                timestamp="241226_120000",
                suffix="mentor_test-12345-241226_120000",
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
        mentors=[mentor],
    )

    with patch(
        "ace.scheduler.suffix_transforms.update_changespec_mentors_field",
        return_value=True,
    ):
        result = strip_terminal_status_markers(cs)

    assert len(result) == 1
    assert "Converted MENTOR" in result[0]
    assert "to killed_agent" in result[0]


def test_strip_terminal_status_markers_skips_mentors_without_running_agent() -> None:
    """Test strip_terminal_status_markers skips mentor entries without running_agent."""
    mentor = MentorEntry(
        entry_id="1",
        profiles=["default"],
        status_lines=[
            MentorStatusLine(
                profile_name="default",
                mentor_name="test_mentor",
                status="PASSED",
                timestamp="241226_120000",
                duration="0h5m30s",
                suffix=None,
                suffix_type=None,
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
        mentors=[mentor],
    )

    result = strip_terminal_status_markers(cs)

    assert result == []
