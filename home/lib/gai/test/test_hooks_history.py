"""Tests for ace/hooks/history.py - history entry utilities."""

from typing import Any

from ace.changespec import CommitEntry
from ace.hooks.history import (
    get_history_entry_by_id,
    get_last_accepted_history_entry_id,
    get_last_history_entry,
    get_last_history_entry_id,
    is_proposal_entry,
)


# Tests for get_last_history_entry_id
def test_get_last_history_entry_id_empty_commits(make_changespec: Any) -> None:
    """Test get_last_history_entry_id returns None for empty commits."""
    cs = make_changespec.create(commits=[])
    assert get_last_history_entry_id(cs) is None


def test_get_last_history_entry_id_none_commits(make_changespec: Any) -> None:
    """Test get_last_history_entry_id returns None when commits is None."""
    cs = make_changespec.create(commits=None)
    assert get_last_history_entry_id(cs) is None


def test_get_last_history_entry_id_single_commit(make_changespec: Any) -> None:
    """Test get_last_history_entry_id returns ID of single commit."""
    commit = CommitEntry(number=1, note="First commit")
    cs = make_changespec.create(commits=[commit])
    assert get_last_history_entry_id(cs) == "1"


def test_get_last_history_entry_id_multiple_commits(make_changespec: Any) -> None:
    """Test get_last_history_entry_id returns ID of last commit."""
    commits = [
        CommitEntry(number=1, note="First commit"),
        CommitEntry(number=2, note="Second commit"),
        CommitEntry(number=3, note="Third commit"),
    ]
    cs = make_changespec.create(commits=commits)
    assert get_last_history_entry_id(cs) == "3"


def test_get_last_history_entry_id_proposal_commit(make_changespec: Any) -> None:
    """Test get_last_history_entry_id returns proposal ID like '2a'."""
    commits = [
        CommitEntry(number=1, note="First commit"),
        CommitEntry(number=2, note="Proposal", proposal_letter="a"),
    ]
    cs = make_changespec.create(commits=commits)
    assert get_last_history_entry_id(cs) == "2a"


# Tests for get_last_history_entry
def test_get_last_history_entry_empty_commits(make_changespec: Any) -> None:
    """Test get_last_history_entry returns None for empty commits."""
    cs = make_changespec.create(commits=[])
    assert get_last_history_entry(cs) is None


def test_get_last_history_entry_none_commits(make_changespec: Any) -> None:
    """Test get_last_history_entry returns None when commits is None."""
    cs = make_changespec.create(commits=None)
    assert get_last_history_entry(cs) is None


def test_get_last_history_entry_single_commit(make_changespec: Any) -> None:
    """Test get_last_history_entry returns single commit."""
    commit = CommitEntry(number=1, note="First commit")
    cs = make_changespec.create(commits=[commit])
    result = get_last_history_entry(cs)
    assert result is commit


def test_get_last_history_entry_multiple_commits(make_changespec: Any) -> None:
    """Test get_last_history_entry returns last commit."""
    commits = [
        CommitEntry(number=1, note="First commit"),
        CommitEntry(number=2, note="Second commit"),
        CommitEntry(number=3, note="Third commit"),
    ]
    cs = make_changespec.create(commits=commits)
    result = get_last_history_entry(cs)
    assert result is commits[-1]
    assert result.note == "Third commit"


# Tests for get_last_accepted_history_entry_id
def test_get_last_accepted_history_entry_id_empty_commits(make_changespec: Any) -> None:
    """Test get_last_accepted_history_entry_id returns None for empty commits."""
    cs = make_changespec.create(commits=[])
    assert get_last_accepted_history_entry_id(cs) is None


def test_get_last_accepted_history_entry_id_none_commits(make_changespec: Any) -> None:
    """Test get_last_accepted_history_entry_id returns None when commits is None."""
    cs = make_changespec.create(commits=None)
    assert get_last_accepted_history_entry_id(cs) is None


def test_get_last_accepted_history_entry_id_all_numeric(make_changespec: Any) -> None:
    """Test get_last_accepted_history_entry_id returns last numeric ID."""
    commits = [
        CommitEntry(number=1, note="First commit"),
        CommitEntry(number=2, note="Second commit"),
        CommitEntry(number=3, note="Third commit"),
    ]
    cs = make_changespec.create(commits=commits)
    assert get_last_accepted_history_entry_id(cs) == "3"


def test_get_last_accepted_history_entry_id_skips_proposals(
    make_changespec: Any,
) -> None:
    """Test get_last_accepted_history_entry_id skips proposal entries."""
    commits = [
        CommitEntry(number=1, note="First commit"),
        CommitEntry(number=2, note="Second commit"),
        CommitEntry(number=2, note="Proposal A", proposal_letter="a"),
        CommitEntry(number=2, note="Proposal B", proposal_letter="b"),
    ]
    cs = make_changespec.create(commits=commits)
    # Should return "2" (the last all-numeric), not "2b"
    assert get_last_accepted_history_entry_id(cs) == "2"


def test_get_last_accepted_history_entry_id_all_proposals(make_changespec: Any) -> None:
    """Test get_last_accepted_history_entry_id returns None when all are proposals."""
    commits = [
        CommitEntry(number=1, note="Proposal A", proposal_letter="a"),
        CommitEntry(number=1, note="Proposal B", proposal_letter="b"),
    ]
    cs = make_changespec.create(commits=commits)
    assert get_last_accepted_history_entry_id(cs) is None


def test_get_last_accepted_history_entry_id_mixed_order(make_changespec: Any) -> None:
    """Test get_last_accepted_history_entry_id with mixed numeric and proposal entries."""
    commits = [
        CommitEntry(number=1, note="First commit"),
        CommitEntry(number=1, note="Amendment", proposal_letter="a"),
        CommitEntry(number=2, note="Second commit"),
        CommitEntry(number=3, note="Third commit"),
        CommitEntry(number=3, note="Amendment", proposal_letter="a"),
    ]
    cs = make_changespec.create(commits=commits)
    # Should return "3" as it's the last all-numeric entry
    assert get_last_accepted_history_entry_id(cs) == "3"


# Tests for is_proposal_entry
def test_is_proposal_entry_numeric() -> None:
    """Test is_proposal_entry returns False for numeric IDs."""
    assert is_proposal_entry("1") is False
    assert is_proposal_entry("2") is False
    assert is_proposal_entry("10") is False
    assert is_proposal_entry("123") is False


def test_is_proposal_entry_with_letter() -> None:
    """Test is_proposal_entry returns True for IDs ending with letter."""
    assert is_proposal_entry("1a") is True
    assert is_proposal_entry("2b") is True
    assert is_proposal_entry("10c") is True
    assert is_proposal_entry("123z") is True


def test_is_proposal_entry_empty_string() -> None:
    """Test is_proposal_entry returns False for empty string."""
    assert is_proposal_entry("") is False


def test_is_proposal_entry_letter_only() -> None:
    """Test is_proposal_entry returns True for single letter."""
    assert is_proposal_entry("a") is True
    assert is_proposal_entry("z") is True


# Tests for get_history_entry_by_id
def test_get_history_entry_by_id_empty_commits(make_changespec: Any) -> None:
    """Test get_history_entry_by_id returns None for empty commits."""
    cs = make_changespec.create(commits=[])
    assert get_history_entry_by_id(cs, "1") is None


def test_get_history_entry_by_id_none_commits(make_changespec: Any) -> None:
    """Test get_history_entry_by_id returns None when commits is None."""
    cs = make_changespec.create(commits=None)
    assert get_history_entry_by_id(cs, "1") is None


def test_get_history_entry_by_id_found(make_changespec: Any) -> None:
    """Test get_history_entry_by_id returns matching entry."""
    commits = [
        CommitEntry(number=1, note="First commit"),
        CommitEntry(number=2, note="Second commit"),
        CommitEntry(number=3, note="Third commit"),
    ]
    cs = make_changespec.create(commits=commits)
    result = get_history_entry_by_id(cs, "2")
    assert result is commits[1]
    assert result.note == "Second commit"


def test_get_history_entry_by_id_not_found(make_changespec: Any) -> None:
    """Test get_history_entry_by_id returns None when ID not found."""
    commits = [
        CommitEntry(number=1, note="First commit"),
        CommitEntry(number=2, note="Second commit"),
    ]
    cs = make_changespec.create(commits=commits)
    assert get_history_entry_by_id(cs, "3") is None
    assert get_history_entry_by_id(cs, "99") is None


def test_get_history_entry_by_id_proposal(make_changespec: Any) -> None:
    """Test get_history_entry_by_id finds proposal entries."""
    commits = [
        CommitEntry(number=1, note="First commit"),
        CommitEntry(number=2, note="Second commit"),
        CommitEntry(number=2, note="Proposal A", proposal_letter="a"),
    ]
    cs = make_changespec.create(commits=commits)
    result = get_history_entry_by_id(cs, "2a")
    assert result is commits[2]
    assert result.note == "Proposal A"


def test_get_history_entry_by_id_distinguishes_numeric_from_proposal(
    make_changespec: Any,
) -> None:
    """Test get_history_entry_by_id distinguishes '2' from '2a'."""
    commits = [
        CommitEntry(number=2, note="Accepted commit"),
        CommitEntry(number=2, note="Proposal", proposal_letter="a"),
    ]
    cs = make_changespec.create(commits=commits)

    result_numeric = get_history_entry_by_id(cs, "2")
    assert result_numeric is not None
    assert result_numeric.note == "Accepted commit"

    result_proposal = get_history_entry_by_id(cs, "2a")
    assert result_proposal is not None
    assert result_proposal.note == "Proposal"
