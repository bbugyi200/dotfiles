"""Tests for conflict checking in accept workflow."""

from unittest.mock import MagicMock, patch

from accept_workflow.conflict_check import (
    ConflictCheckResult,
    ConflictPair,
    _apply_all_proposals,
    _find_conflicting_pairs,
    _format_proposal_id,
    run_conflict_check,
)
from ace.changespec import CommitEntry


def _make_entry(number: int, letter: str, diff: str) -> CommitEntry:
    """Create a CommitEntry for testing."""
    return CommitEntry(
        number=number,
        note=f"Test proposal {number}{letter}",
        diff=diff,
        proposal_letter=letter,
    )


def test_format_proposal_id_formats_correctly() -> None:
    """Test that _format_proposal_id formats IDs correctly."""
    assert _format_proposal_id(2, "a") == "(2a)"
    assert _format_proposal_id(1, "b") == "(1b)"
    assert _format_proposal_id(10, "c") == "(10c)"


def test_run_conflict_check_empty_proposals_returns_success() -> None:
    """Test that empty proposals returns success."""
    result = run_conflict_check("/workspace", [], verbose=False)
    assert result.success is True
    assert result.failed_proposal is None
    assert result.conflicting_pairs == []


def test_run_conflict_check_single_proposal_returns_success() -> None:
    """Test that single proposal returns success without checking."""
    entry = _make_entry(2, "a", "~/.gai/diffs/test.diff")
    validated: list[tuple[int, str, str | None, CommitEntry]] = [(2, "a", None, entry)]
    result = run_conflict_check("/workspace", validated, verbose=False)
    assert result.success is True
    assert result.failed_proposal is None
    assert result.conflicting_pairs == []


@patch("accept_workflow.conflict_check.clean_workspace")
@patch("accept_workflow.conflict_check.apply_diffs_to_workspace")
def test_run_conflict_check_two_proposals_no_conflict(
    mock_apply: MagicMock,
    mock_clean: MagicMock,
) -> None:
    """Test two proposals that don't conflict."""
    mock_apply.return_value = (True, "")
    mock_clean.return_value = True

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    validated = [(2, "a", None, entry_a), (2, "b", "extra msg", entry_b)]

    result = run_conflict_check("/workspace", validated, verbose=False)

    assert result.success is True
    assert result.failed_proposal is None
    assert result.conflicting_pairs == []
    # Should have applied both proposals together in single call
    assert mock_apply.call_count == 1


@patch("accept_workflow.conflict_check.clean_workspace")
@patch("accept_workflow.conflict_check.apply_diffs_to_workspace")
def test_run_conflict_check_two_proposals_with_conflict(
    mock_apply: MagicMock,
    mock_clean: MagicMock,
) -> None:
    """Test two proposals that conflict (no pair detection for 2 proposals)."""
    # Both proposals fail when applied together
    mock_apply.return_value = (False, "patch failed")
    mock_clean.return_value = True

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    validated: list[tuple[int, str, str | None, CommitEntry]] = [
        (2, "a", None, entry_a),
        (2, "b", None, entry_b),
    ]

    result = run_conflict_check("/workspace", validated, verbose=False)

    assert result.success is False
    # Can't determine which proposal failed when applying together
    assert result.failed_proposal is None
    # No pair detection for 2 proposals
    assert result.conflicting_pairs == []


@patch("accept_workflow.conflict_check.clean_workspace")
@patch("accept_workflow.conflict_check.apply_diffs_to_workspace")
def test_run_conflict_check_three_proposals_triggers_pair_detection(
    mock_apply: MagicMock,
    mock_clean: MagicMock,
) -> None:
    """Test three proposals triggers pair detection when conflict found."""
    # All three together fails, then pair testing shows A+B conflicts
    mock_clean.return_value = True

    call_count = 0

    def apply_side_effect(
        _workspace_dir: str, diff_paths: list[str]
    ) -> tuple[bool, str]:
        nonlocal call_count
        call_count += 1

        # Initial phase: all 3 together (fails)
        if call_count == 1:
            return (False, "patch conflict")

        # Pair testing phase (each pair tested with single hg import):
        # Pair (A,B): conflicts
        if call_count == 2:
            return (False, "patch conflict")

        # Pair (A,C): succeeds
        if call_count == 3:
            return (True, "")

        # Pair (B,C): succeeds
        if call_count == 4:
            return (True, "")

        return (True, "")

    mock_apply.side_effect = apply_side_effect

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    entry_c = _make_entry(2, "c", "~/.gai/diffs/c.diff")
    validated: list[tuple[int, str, str | None, CommitEntry]] = [
        (2, "a", None, entry_a),
        (2, "b", None, entry_b),
        (2, "c", None, entry_c),
    ]

    result = run_conflict_check("/workspace", validated, verbose=False)

    assert result.success is False
    # Can't determine which proposal failed when applying together
    assert result.failed_proposal is None
    assert len(result.conflicting_pairs) == 1
    assert result.conflicting_pairs[0].proposal_a == (2, "a")
    assert result.conflicting_pairs[0].proposal_b == (2, "b")


@patch("accept_workflow.conflict_check.apply_diffs_to_workspace")
def test_apply_all_proposals_succeeds(
    mock_apply: MagicMock,
) -> None:
    """Test applying all proposals together when they succeed."""
    mock_apply.return_value = (True, "")

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    proposals = [(2, "a", entry_a), (2, "b", entry_b)]

    success, error_msg = _apply_all_proposals("/workspace", proposals)

    assert success is True
    assert error_msg == ""
    # All proposals applied together in single call
    assert mock_apply.call_count == 1
    # Verify correct diff paths were passed
    mock_apply.assert_called_once_with(
        "/workspace", ["~/.gai/diffs/a.diff", "~/.gai/diffs/b.diff"]
    )


@patch("accept_workflow.conflict_check.apply_diffs_to_workspace")
def test_apply_all_proposals_fails(
    mock_apply: MagicMock,
) -> None:
    """Test applying all proposals together when they fail."""
    mock_apply.return_value = (False, "conflict error")

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    proposals = [(2, "a", entry_a), (2, "b", entry_b)]

    success, error_msg = _apply_all_proposals("/workspace", proposals)

    assert success is False
    assert error_msg == "conflict error"
    assert mock_apply.call_count == 1


@patch("accept_workflow.conflict_check.clean_workspace")
@patch("accept_workflow.conflict_check.apply_diffs_to_workspace")
def test_find_conflicting_pairs_finds_conflicts(
    mock_apply: MagicMock,
    mock_clean: MagicMock,
) -> None:
    """Test pair detection finds all conflicting pairs."""
    mock_clean.return_value = True

    # Each pair is applied together in a single hg import call
    # Pairs: (A,B), (A,C), (B,C)
    # A+B: conflict
    # A+C: succeeds
    # B+C: succeeds
    mock_apply.side_effect = [
        (False, "A+B conflicts"),  # (A,B) together
        (True, ""),  # (A,C) together
        (True, ""),  # (B,C) together
    ]

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    entry_c = _make_entry(2, "c", "~/.gai/diffs/c.diff")
    proposals = [(2, "a", entry_a), (2, "b", entry_b), (2, "c", entry_c)]

    pairs = _find_conflicting_pairs("/workspace", proposals)

    assert len(pairs) == 1
    assert pairs[0].proposal_a == (2, "a")
    assert pairs[0].proposal_b == (2, "b")
    assert pairs[0].error_message == "A+B conflicts"


@patch("accept_workflow.conflict_check.clean_workspace")
@patch("accept_workflow.conflict_check.apply_diffs_to_workspace")
def test_find_conflicting_pairs_multiple_conflicts(
    mock_apply: MagicMock,
    mock_clean: MagicMock,
) -> None:
    """Test pair detection finds multiple conflicting pairs."""
    mock_clean.return_value = True

    # Each pair is applied together in a single hg import call
    # Pairs: (A,B), (A,C), (B,C)
    # A+B: conflict
    # A+C: conflict
    # B+C: succeeds
    mock_apply.side_effect = [
        (False, "A+B conflicts"),  # (A,B) together
        (False, "A+C conflicts"),  # (A,C) together
        (True, ""),  # (B,C) together
    ]

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    entry_c = _make_entry(2, "c", "~/.gai/diffs/c.diff")
    proposals = [(2, "a", entry_a), (2, "b", entry_b), (2, "c", entry_c)]

    pairs = _find_conflicting_pairs("/workspace", proposals)

    # Both A+B and A+C conflict
    assert len(pairs) == 2
    assert pairs[0].proposal_a == (2, "a")
    assert pairs[0].proposal_b == (2, "b")
    assert pairs[1].proposal_a == (2, "a")
    assert pairs[1].proposal_b == (2, "c")


def test_conflict_check_result_dataclass() -> None:
    """Test ConflictCheckResult dataclass fields."""
    result = ConflictCheckResult(
        success=False,
        failed_proposal=(2, "b"),
        conflicting_pairs=[
            ConflictPair(
                proposal_a=(2, "a"),
                proposal_b=(2, "b"),
                error_message="conflict",
            )
        ],
    )
    assert result.success is False
    assert result.failed_proposal == (2, "b")
    assert len(result.conflicting_pairs) == 1


def test_conflict_pair_dataclass() -> None:
    """Test ConflictPair dataclass fields."""
    pair = ConflictPair(
        proposal_a=(1, "a"),
        proposal_b=(1, "b"),
        error_message="test error",
    )
    assert pair.proposal_a == (1, "a")
    assert pair.proposal_b == (1, "b")
    assert pair.error_message == "test error"
