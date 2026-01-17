"""Tests for clipboard formatting functions."""

from typing import Any

from ace.changespec import (
    ChangeSpec,
    CommentEntry,
    CommitEntry,
    HookEntry,
    HookStatusLine,
    MentorEntry,
    MentorStatusLine,
)
from ace.tui.actions.clipboard import _format_changespec_for_clipboard


def _make_basic_changespec(
    name: str = "test_cl",
    description: str = "Test description",
    status: str = "Drafted",
    **kwargs: Any,
) -> ChangeSpec:
    """Helper to create a basic ChangeSpec for testing."""
    return ChangeSpec(
        name=name,
        description=description,
        status=status,
        parent=kwargs.get("parent"),
        cl=kwargs.get("cl"),
        test_targets=kwargs.get("test_targets"),
        kickstart=kwargs.get("kickstart"),
        bug=kwargs.get("bug"),
        commits=kwargs.get("commits"),
        hooks=kwargs.get("hooks"),
        comments=kwargs.get("comments"),
        mentors=kwargs.get("mentors"),
        file_path="/tmp/test.gp",
        line_number=1,
    )


def test_format_changespec_basic_fields() -> None:
    """Test formatting basic ChangeSpec fields."""
    cs = _make_basic_changespec(
        name="my_feature",
        description="Add new feature",
        status="Drafted",
    )
    result = _format_changespec_for_clipboard(cs)
    assert "NAME: my_feature" in result
    assert "DESCRIPTION: Add new feature" in result
    assert "STATUS: Drafted" in result


def test_format_changespec_with_parent() -> None:
    """Test formatting ChangeSpec with parent field."""
    cs = _make_basic_changespec(parent="parent_cl")
    result = _format_changespec_for_clipboard(cs)
    assert "PARENT: parent_cl" in result


def test_format_changespec_with_cl() -> None:
    """Test formatting ChangeSpec with CL field."""
    cs = _make_basic_changespec(cl="12345")
    result = _format_changespec_for_clipboard(cs)
    assert "CL: 12345" in result


def test_format_changespec_with_bug() -> None:
    """Test formatting ChangeSpec with bug field."""
    cs = _make_basic_changespec(bug="b/123456")
    result = _format_changespec_for_clipboard(cs)
    assert "BUG: b/123456" in result


def test_format_changespec_with_test_targets() -> None:
    """Test formatting ChangeSpec with test targets."""
    cs = _make_basic_changespec(test_targets=["//foo:test1", "//bar:test2"])
    result = _format_changespec_for_clipboard(cs)
    assert "TEST_TARGETS: //foo:test1, //bar:test2" in result


def test_format_changespec_with_kickstart() -> None:
    """Test formatting ChangeSpec with kickstart field."""
    cs = _make_basic_changespec(kickstart="some kickstart value")
    result = _format_changespec_for_clipboard(cs)
    assert "KICKSTART: some kickstart value" in result


def test_format_changespec_with_commits() -> None:
    """Test formatting ChangeSpec with COMMITS section."""
    commits = [
        CommitEntry(number=1, note="Initial commit"),
        CommitEntry(number=2, note="Follow-up fix"),
    ]
    cs = _make_basic_changespec(commits=commits)
    result = _format_changespec_for_clipboard(cs)
    assert "COMMITS:" in result
    assert "(1) Initial commit" in result
    assert "(2) Follow-up fix" in result


def test_format_changespec_commits_with_suffix() -> None:
    """Test formatting commits with suffix."""
    commits = [
        CommitEntry(
            number=1, note="Commit with error", suffix="Some error", suffix_type="error"
        ),
    ]
    cs = _make_basic_changespec(commits=commits)
    result = _format_changespec_for_clipboard(cs)
    assert "(1) Commit with error - (!: Some error)" in result


def test_format_changespec_commits_with_plain_suffix() -> None:
    """Test formatting commits with plain suffix (no type)."""
    commits = [
        CommitEntry(number=1, note="Commit with note", suffix="Plain note"),
    ]
    cs = _make_basic_changespec(commits=commits)
    result = _format_changespec_for_clipboard(cs)
    assert "(1) Commit with note - (Plain note)" in result


def test_format_changespec_commits_with_chat_and_diff() -> None:
    """Test formatting commits with chat and diff paths."""
    commits = [
        CommitEntry(
            number=1,
            note="Commit with artifacts",
            chat="/path/to/chat.md",
            diff="/path/to/diff.txt",
        ),
    ]
    cs = _make_basic_changespec(commits=commits)
    result = _format_changespec_for_clipboard(cs)
    assert "[chat: /path/to/chat.md]" in result
    assert "[diff: /path/to/diff.txt]" in result


def test_format_changespec_with_hooks() -> None:
    """Test formatting ChangeSpec with HOOKS section."""
    hooks = [
        HookEntry(command="flake8 src"),
        HookEntry(command="pytest tests"),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    assert "HOOKS:" in result
    assert "  flake8 src" in result
    assert "  pytest tests" in result


def test_format_changespec_hooks_with_status_lines() -> None:
    """Test formatting hooks with status lines."""
    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="PASSED",
                    duration="1m23s",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    assert "  flake8 src" in result
    assert "(1) [240601_123456] PASSED (1m23s)" in result


def test_format_changespec_hooks_with_suffix_types() -> None:
    """Test formatting hooks with various suffix types."""
    hooks = [
        HookEntry(
            command="test_hook",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                    suffix="error_message",
                    suffix_type="error",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    assert "(!: error_message)" in result


def test_format_changespec_hooks_with_running_agent_suffix() -> None:
    """Test formatting hooks with running_agent suffix type."""
    hooks = [
        HookEntry(
            command="test_hook",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                    suffix="agent_id",
                    suffix_type="running_agent",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    assert "(@: agent_id)" in result


def test_format_changespec_hooks_with_summarize_complete_suffix() -> None:
    """Test formatting hooks with summarize_complete suffix type."""
    hooks = [
        HookEntry(
            command="test_hook",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                    suffix="fix_id",
                    suffix_type="summarize_complete",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    assert "(%: fix_id)" in result


def test_format_changespec_hooks_with_summary() -> None:
    """Test formatting hooks with compound suffix (suffix + summary)."""
    hooks = [
        HookEntry(
            command="test_hook",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                    suffix="fix_id",
                    suffix_type="summarize_complete",
                    summary="Brief summary of error",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    assert "(%: fix_id | Brief summary of error)" in result


def test_format_changespec_with_comments() -> None:
    """Test formatting ChangeSpec with COMMENTS section."""
    comments = [
        CommentEntry(reviewer="critique", file_path="/path/to/comments.json"),
    ]
    cs = _make_basic_changespec(comments=comments)
    result = _format_changespec_for_clipboard(cs)
    assert "COMMENTS:" in result
    assert "[critique] /path/to/comments.json" in result


def test_format_changespec_comments_with_suffix() -> None:
    """Test formatting comments with suffix."""
    comments = [
        CommentEntry(
            reviewer="critique",
            file_path="/path/to/comments.json",
            suffix="Unresolved Comments",
            suffix_type="error",
        ),
    ]
    cs = _make_basic_changespec(comments=comments)
    result = _format_changespec_for_clipboard(cs)
    assert "(!: Unresolved Comments)" in result


def test_format_changespec_comments_with_running_agent_suffix() -> None:
    """Test formatting comments with running_agent suffix."""
    comments = [
        CommentEntry(
            reviewer="critique",
            file_path="/path/to/comments.json",
            suffix="agent_240601_123456",
            suffix_type="running_agent",
        ),
    ]
    cs = _make_basic_changespec(comments=comments)
    result = _format_changespec_for_clipboard(cs)
    assert "(@: agent_240601_123456)" in result


def test_format_changespec_with_mentors() -> None:
    """Test formatting ChangeSpec with MENTORS section."""
    mentors = [
        MentorEntry(entry_id="1", profiles=["profile1", "profile2"]),
    ]
    cs = _make_basic_changespec(mentors=mentors)
    result = _format_changespec_for_clipboard(cs)
    assert "MENTORS:" in result
    assert "(1) profile1 profile2" in result


def test_format_changespec_mentors_with_wip() -> None:
    """Test formatting mentors with WIP marker."""
    mentors = [
        MentorEntry(entry_id="1", profiles=["profile1"], is_wip=True),
    ]
    cs = _make_basic_changespec(mentors=mentors)
    result = _format_changespec_for_clipboard(cs)
    assert "(1) profile1 (WIP)" in result


def test_format_changespec_mentors_with_status_lines() -> None:
    """Test formatting mentors with status lines."""
    mentors = [
        MentorEntry(
            entry_id="1",
            profiles=["test_profile"],
            status_lines=[
                MentorStatusLine(
                    profile_name="test_profile",
                    mentor_name="test_mentor",
                    status="PASSED",
                    duration="5m30s",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(mentors=mentors)
    result = _format_changespec_for_clipboard(cs)
    assert "test_profile:test_mentor - PASSED - (5m30s)" in result


def test_format_changespec_mentors_status_with_timestamp() -> None:
    """Test formatting mentor status lines with timestamp."""
    mentors = [
        MentorEntry(
            entry_id="1",
            profiles=["test_profile"],
            status_lines=[
                MentorStatusLine(
                    profile_name="test_profile",
                    mentor_name="test_mentor",
                    status="RUNNING",
                    timestamp="240601_123456",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(mentors=mentors)
    result = _format_changespec_for_clipboard(cs)
    assert "[240601_123456] test_profile:test_mentor - RUNNING" in result


def test_format_changespec_mentors_status_with_suffix() -> None:
    """Test formatting mentor status lines with suffix."""
    mentors = [
        MentorEntry(
            entry_id="1",
            profiles=["test_profile"],
            status_lines=[
                MentorStatusLine(
                    profile_name="test_profile",
                    mentor_name="test_mentor",
                    status="RUNNING",
                    suffix="mentor_process_123",
                    suffix_type="running_agent",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(mentors=mentors)
    result = _format_changespec_for_clipboard(cs)
    assert "(@: mentor_process_123)" in result


def test_format_changespec_empty_optional_fields() -> None:
    """Test that empty optional fields are not included in output."""
    cs = _make_basic_changespec()
    result = _format_changespec_for_clipboard(cs)
    assert "PARENT:" not in result
    assert "CL:" not in result
    assert "BUG:" not in result
    assert "TEST_TARGETS:" not in result
    assert "KICKSTART:" not in result
    assert "COMMITS:" not in result
    assert "HOOKS:" not in result
    assert "COMMENTS:" not in result
    assert "MENTORS:" not in result


def test_format_changespec_full_example() -> None:
    """Test formatting a full ChangeSpec with all sections."""
    commits = [
        CommitEntry(number=1, note="First commit", chat="/path/chat1.md"),
        CommitEntry(number=2, note="Second commit", suffix="NEW PROPOSAL"),
    ]
    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_100000",
                    status="PASSED",
                    duration="30s",
                ),
            ],
        ),
    ]
    comments = [
        CommentEntry(reviewer="critique", file_path="/path/comments.json"),
    ]
    mentors = [
        MentorEntry(entry_id="1", profiles=["code_review"]),
    ]
    cs = _make_basic_changespec(
        name="full_example",
        description="Complete ChangeSpec example",
        status="Pending",
        parent="base_cl",
        cl="67890",
        bug="b/999",
        test_targets=["//test:all"],
        commits=commits,
        hooks=hooks,
        comments=comments,
        mentors=mentors,
    )
    result = _format_changespec_for_clipboard(cs)

    # Verify all sections are present
    assert "NAME: full_example" in result
    assert "DESCRIPTION: Complete ChangeSpec example" in result
    assert "PARENT: base_cl" in result
    assert "CL: 67890" in result
    assert "STATUS: Pending" in result
    assert "BUG: b/999" in result
    assert "TEST_TARGETS: //test:all" in result
    assert "COMMITS:" in result
    assert "HOOKS:" in result
    assert "COMMENTS:" in result
    assert "MENTORS:" in result


def test_format_changespec_hooks_with_killed_agent_suffix() -> None:
    """Test formatting hooks with killed_agent suffix type."""
    hooks = [
        HookEntry(
            command="test_hook",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                    suffix="killed_agent_id",
                    suffix_type="killed_agent",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    assert "(~@: killed_agent_id)" in result


def test_format_changespec_hooks_with_running_process_suffix() -> None:
    """Test formatting hooks with running_process suffix type."""
    hooks = [
        HookEntry(
            command="test_hook",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="RUNNING",
                    suffix="process_123",
                    suffix_type="running_process",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    assert "($: process_123)" in result


def test_format_changespec_hooks_with_pending_dead_process_suffix() -> None:
    """Test formatting hooks with pending_dead_process suffix type."""
    hooks = [
        HookEntry(
            command="test_hook",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="RUNNING",
                    suffix="pending_process",
                    suffix_type="pending_dead_process",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    assert "(?$: pending_process)" in result


def test_format_changespec_hooks_with_killed_process_suffix() -> None:
    """Test formatting hooks with killed_process suffix type."""
    hooks = [
        HookEntry(
            command="test_hook",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="RUNNING",
                    suffix="killed_process",
                    suffix_type="killed_process",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    assert "(~$: killed_process)" in result


def test_format_changespec_hooks_no_duration() -> None:
    """Test formatting hooks status without duration."""
    hooks = [
        HookEntry(
            command="test_hook",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="RUNNING",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    # Should have status without duration parentheses
    assert "(1) [240601_123456] RUNNING" in result
    # Should NOT have duration
    assert "RUNNING (" not in result or "RUNNING - (" in result  # Suffix case


def test_format_changespec_hooks_multiple_status_lines() -> None:
    """Test formatting hooks with multiple status lines."""
    hooks = [
        HookEntry(
            command="flake8 src",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_100000",
                    status="PASSED",
                    duration="30s",
                ),
                HookStatusLine(
                    commit_entry_num="2",
                    timestamp="240601_110000",
                    status="FAILED",
                    duration="45s",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    # Both status lines should be present
    assert "(1) [240601_100000] PASSED (30s)" in result
    assert "(2) [240601_110000] FAILED (45s)" in result


def test_format_changespec_commits_with_proposal_letter() -> None:
    """Test formatting commits with proposal letter."""
    commits = [
        CommitEntry(number=1, note="Original commit"),
        CommitEntry(number=1, note="Proposed change", proposal_letter="a"),
    ]
    cs = _make_basic_changespec(commits=commits)
    result = _format_changespec_for_clipboard(cs)
    # Should use display_number property which includes proposal letter
    assert "(1) Original commit" in result
    assert "(1a) Proposed change" in result


def test_format_changespec_mentors_error_suffix() -> None:
    """Test formatting mentor status lines with error suffix."""
    mentors = [
        MentorEntry(
            entry_id="1",
            profiles=["test_profile"],
            status_lines=[
                MentorStatusLine(
                    profile_name="test_profile",
                    mentor_name="test_mentor",
                    status="FAILED",
                    suffix="mentor failed",
                    suffix_type="error",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(mentors=mentors)
    result = _format_changespec_for_clipboard(cs)
    assert "(!: mentor failed)" in result


def test_format_changespec_multiple_test_targets() -> None:
    """Test formatting with multiple test targets."""
    cs = _make_basic_changespec(
        test_targets=["//foo:test1", "//bar:test2", "//baz:test3"]
    )
    result = _format_changespec_for_clipboard(cs)
    assert "TEST_TARGETS: //foo:test1, //bar:test2, //baz:test3" in result


def test_format_changespec_hooks_unknown_suffix_type() -> None:
    """Test formatting hooks with unknown suffix type (no prefix)."""
    hooks = [
        HookEntry(
            command="test_hook",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="1",
                    timestamp="240601_123456",
                    status="FAILED",
                    suffix="unknown_suffix",
                    suffix_type="some_unknown_type",
                ),
            ],
        ),
    ]
    cs = _make_basic_changespec(hooks=hooks)
    result = _format_changespec_for_clipboard(cs)
    # Unknown suffix types get no prefix
    assert "(unknown_suffix)" in result


def test_format_changespec_empty_commits_list() -> None:
    """Test that empty commits list doesn't add COMMITS section."""
    cs = _make_basic_changespec(commits=[])
    result = _format_changespec_for_clipboard(cs)
    assert "COMMITS:" not in result


def test_format_changespec_empty_hooks_list() -> None:
    """Test that empty hooks list doesn't add HOOKS section."""
    cs = _make_basic_changespec(hooks=[])
    result = _format_changespec_for_clipboard(cs)
    assert "HOOKS:" not in result


def test_format_changespec_empty_comments_list() -> None:
    """Test that empty comments list doesn't add COMMENTS section."""
    cs = _make_basic_changespec(comments=[])
    result = _format_changespec_for_clipboard(cs)
    assert "COMMENTS:" not in result


def test_format_changespec_empty_mentors_list() -> None:
    """Test that empty mentors list doesn't add MENTORS section."""
    cs = _make_basic_changespec(mentors=[])
    result = _format_changespec_for_clipboard(cs)
    assert "MENTORS:" not in result
