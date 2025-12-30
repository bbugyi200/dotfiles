"""Tests for ready-to-mail helper functions in changespec module."""

from ace.changespec import (
    ChangeSpec,
    CommitEntry,
    HookEntry,
    HookStatusLine,
    all_hooks_passed_for_entries,
    get_current_and_proposal_entry_ids,
)


def _make_changespec(
    commits: list | None = None,
    hooks: list | None = None,
    status: str = "Drafted",
) -> ChangeSpec:
    """Helper function to create a ChangeSpec with required fields for tests."""
    return ChangeSpec(
        name="test",
        description="test",
        parent=None,
        cl=None,
        status=status,
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.gp",
        line_number=1,
        commits=commits,
        hooks=hooks,
    )


# Tests for get_current_and_proposal_entry_ids
def test_get_current_and_proposal_entry_ids_regular_only() -> None:
    """Test returns just current entry when no proposals exist."""
    changespec = _make_changespec(
        commits=[
            CommitEntry(number=1, note="First change"),
            CommitEntry(number=2, note="Second change"),
        ],
    )
    result = get_current_and_proposal_entry_ids(changespec)
    assert result == ["2"]


def test_get_current_and_proposal_entry_ids_with_proposals() -> None:
    """Test returns current + proposals with same number."""
    changespec = _make_changespec(
        commits=[
            CommitEntry(number=1, note="First change"),
            CommitEntry(number=2, note="Second change"),
            CommitEntry(number=2, note="Proposal A", proposal_letter="a"),
            CommitEntry(number=2, note="Proposal B", proposal_letter="b"),
        ],
    )
    result = get_current_and_proposal_entry_ids(changespec)
    assert result == ["2", "2a", "2b"]


def test_get_current_and_proposal_entry_ids_ignores_old_proposals() -> None:
    """Test doesn't include proposals from older entries."""
    changespec = _make_changespec(
        commits=[
            CommitEntry(number=1, note="First change"),
            CommitEntry(number=1, note="Old proposal", proposal_letter="a"),
            CommitEntry(number=2, note="Second change"),
        ],
    )
    result = get_current_and_proposal_entry_ids(changespec)
    # Should NOT include "1a" since current is "2"
    assert result == ["2"]


def test_get_current_and_proposal_entry_ids_empty_history() -> None:
    """Test returns empty list when no history."""
    changespec = _make_changespec(commits=[])
    result = get_current_and_proposal_entry_ids(changespec)
    assert result == []


def test_get_current_and_proposal_entry_ids_all_proposals() -> None:
    """Test returns empty list when all entries are proposals (no current)."""
    changespec = _make_changespec(
        commits=[
            CommitEntry(number=1, note="Only proposal", proposal_letter="a"),
        ],
    )
    result = get_current_and_proposal_entry_ids(changespec)
    assert result == []


# Tests for all_hooks_passed_for_entries
def test_all_hooks_passed_for_entries_all_passed() -> None:
    """Test returns True when all hooks have PASSED for all entries."""
    hooks = [
        HookEntry(
            command="hook1",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2", timestamp="240601_120000", status="PASSED"
                ),
                HookStatusLine(
                    commit_entry_num="2a", timestamp="240601_120100", status="PASSED"
                ),
            ],
        ),
        HookEntry(
            command="hook2",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2", timestamp="240601_120000", status="PASSED"
                ),
                HookStatusLine(
                    commit_entry_num="2a", timestamp="240601_120100", status="PASSED"
                ),
            ],
        ),
    ]
    changespec = _make_changespec(hooks=hooks)
    result = all_hooks_passed_for_entries(changespec, ["2", "2a"])
    assert result is True


def test_all_hooks_passed_for_entries_one_failed() -> None:
    """Test returns False when one hook has FAILED."""
    hooks = [
        HookEntry(
            command="hook1",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2", timestamp="240601_120000", status="PASSED"
                ),
            ],
        ),
        HookEntry(
            command="hook2",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2", timestamp="240601_120000", status="FAILED"
                ),
            ],
        ),
    ]
    changespec = _make_changespec(hooks=hooks)
    result = all_hooks_passed_for_entries(changespec, ["2"])
    assert result is False


def test_all_hooks_passed_for_entries_one_running() -> None:
    """Test returns False when one hook is RUNNING."""
    hooks = [
        HookEntry(
            command="hook1",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2", timestamp="240601_120000", status="RUNNING"
                ),
            ],
        ),
    ]
    changespec = _make_changespec(hooks=hooks)
    result = all_hooks_passed_for_entries(changespec, ["2"])
    assert result is False


def test_all_hooks_passed_for_entries_no_status() -> None:
    """Test returns False when hook has no status line for an entry."""
    hooks = [
        HookEntry(
            command="hook1",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2", timestamp="240601_120000", status="PASSED"
                ),
                # No status line for "2a"
            ],
        ),
    ]
    changespec = _make_changespec(hooks=hooks)
    result = all_hooks_passed_for_entries(changespec, ["2", "2a"])
    assert result is False


def test_all_hooks_passed_for_entries_skip_proposal() -> None:
    """Test that $ prefixed hooks skip proposal entries."""
    hooks = [
        HookEntry(
            command="$hook_skips_proposals",
            status_lines=[
                # Only has status for "2", not "2a" - but that's OK because $ prefix
                HookStatusLine(
                    commit_entry_num="2", timestamp="240601_120000", status="PASSED"
                ),
            ],
        ),
    ]
    changespec = _make_changespec(hooks=hooks)
    # Should pass because hook with $ skips proposal entries
    result = all_hooks_passed_for_entries(changespec, ["2", "2a"])
    assert result is True


def test_all_hooks_passed_for_entries_no_hooks() -> None:
    """Test returns True when no hooks defined."""
    changespec = _make_changespec(hooks=None)
    result = all_hooks_passed_for_entries(changespec, ["2"])
    assert result is True


def test_all_hooks_passed_for_entries_no_entry_ids() -> None:
    """Test returns True when no entry IDs provided."""
    hooks = [
        HookEntry(
            command="hook1",
            status_lines=[
                HookStatusLine(
                    commit_entry_num="2", timestamp="240601_120000", status="FAILED"
                ),
            ],
        ),
    ]
    changespec = _make_changespec(hooks=hooks)
    # Empty entry IDs = nothing to check = True
    result = all_hooks_passed_for_entries(changespec, [])
    assert result is True
