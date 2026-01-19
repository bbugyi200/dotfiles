"""Tests for conflict checking in accept workflow."""

from unittest.mock import MagicMock, patch

from accept_workflow.conflict_check import (
    ConflictCheckResult,
    ConflictPair,
    _apply_proposals_sequentially,
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
@patch("accept_workflow.conflict_check.apply_diff_to_workspace")
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
    # Should have applied both proposals
    assert mock_apply.call_count == 2


@patch("accept_workflow.conflict_check.clean_workspace")
@patch("accept_workflow.conflict_check.apply_diff_to_workspace")
def test_run_conflict_check_two_proposals_with_conflict(
    mock_apply: MagicMock,
    mock_clean: MagicMock,
) -> None:
    """Test two proposals that conflict (no pair detection for 2 proposals)."""
    # First proposal succeeds, second fails
    mock_apply.side_effect = [(True, ""), (False, "patch failed")]
    mock_clean.return_value = True

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    validated: list[tuple[int, str, str | None, CommitEntry]] = [
        (2, "a", None, entry_a),
        (2, "b", None, entry_b),
    ]

    result = run_conflict_check("/workspace", validated, verbose=False)

    assert result.success is False
    assert result.failed_proposal == (2, "b")
    # No pair detection for 2 proposals
    assert result.conflicting_pairs == []


@patch("accept_workflow.conflict_check.clean_workspace")
@patch("accept_workflow.conflict_check.apply_diff_to_workspace")
def test_run_conflict_check_three_proposals_triggers_pair_detection(
    mock_apply: MagicMock,
    mock_clean: MagicMock,
) -> None:
    """Test three proposals triggers pair detection when conflict found."""
    # Sequential: A succeeds, B fails on top of A
    # Pair testing will show A+B conflicts
    mock_clean.return_value = True

    call_count = 0

    def apply_side_effect(_workspace_dir: str, _diff_path: str) -> tuple[bool, str]:
        nonlocal call_count
        call_count += 1

        # Sequential phase: A, B (B fails)
        if call_count == 1:  # A
            return (True, "")
        if call_count == 2:  # B on top of A
            return (False, "patch conflict")

        # Pair testing phase:
        # Pair (A,B): A succeeds, B fails
        if call_count == 3:  # A alone
            return (True, "")
        if call_count == 4:  # B on A
            return (False, "patch conflict")

        # Pair (A,C): both succeed
        if call_count == 5:  # A alone
            return (True, "")
        if call_count == 6:  # C on A
            return (True, "")

        # Pair (B,C): both succeed
        if call_count == 7:  # B alone
            return (True, "")
        if call_count == 8:  # C on B
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
    assert result.failed_proposal == (2, "b")
    assert len(result.conflicting_pairs) == 1
    assert result.conflicting_pairs[0].proposal_a == (2, "a")
    assert result.conflicting_pairs[0].proposal_b == (2, "b")


@patch("accept_workflow.conflict_check.apply_diff_to_workspace")
def test_apply_proposals_sequentially_all_succeed(
    mock_apply: MagicMock,
) -> None:
    """Test sequential application when all succeed."""
    mock_apply.return_value = (True, "")

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    proposals = [(2, "a", entry_a), (2, "b", entry_b)]

    result = _apply_proposals_sequentially("/workspace", proposals)

    assert result is None
    assert mock_apply.call_count == 2


@patch("accept_workflow.conflict_check.apply_diff_to_workspace")
def test_apply_proposals_sequentially_returns_first_failure(
    mock_apply: MagicMock,
) -> None:
    """Test sequential application returns on first failure."""
    mock_apply.side_effect = [(True, ""), (False, "conflict error")]

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    proposals = [(2, "a", entry_a), (2, "b", entry_b)]

    result = _apply_proposals_sequentially("/workspace", proposals)

    assert result == (2, "b", "conflict error")
    # Should stop after first failure
    assert mock_apply.call_count == 2


@patch("accept_workflow.conflict_check.clean_workspace")
@patch("accept_workflow.conflict_check.apply_diff_to_workspace")
def test_find_conflicting_pairs_finds_conflicts(
    mock_apply: MagicMock,
    mock_clean: MagicMock,
) -> None:
    """Test pair detection finds all conflicting pairs."""
    mock_clean.return_value = True

    # A+B: A succeeds, B fails
    # A+C: both succeed
    # B+C: both succeed
    mock_apply.side_effect = [
        (True, ""),  # A
        (False, "B conflicts with A"),  # B on A
        (True, ""),  # A
        (True, ""),  # C on A
        (True, ""),  # B
        (True, ""),  # C on B
    ]

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    entry_c = _make_entry(2, "c", "~/.gai/diffs/c.diff")
    proposals = [(2, "a", entry_a), (2, "b", entry_b), (2, "c", entry_c)]

    pairs = _find_conflicting_pairs("/workspace", proposals)

    assert len(pairs) == 1
    assert pairs[0].proposal_a == (2, "a")
    assert pairs[0].proposal_b == (2, "b")
    assert pairs[0].error_message == "B conflicts with A"


@patch("accept_workflow.conflict_check.clean_workspace")
@patch("accept_workflow.conflict_check.apply_diff_to_workspace")
def test_find_conflicting_pairs_skips_when_first_fails(
    mock_apply: MagicMock,
    mock_clean: MagicMock,
) -> None:
    """Test pair detection skips pair when first proposal can't apply."""
    mock_clean.return_value = True

    # For each pair, we apply the first proposal fresh (after clean_workspace)
    # Pairs: (A,B), (A,C), (B,C)
    # A fails alone (corrupted diff), so A+B and A+C pairs are skipped
    mock_apply.side_effect = [
        (False, "A corrupted"),  # A alone for (A,B) - fails, skip pair
        (False, "A corrupted"),  # A alone for (A,C) - fails, skip pair
        (True, ""),  # B alone for (B,C) - succeeds
        (True, ""),  # C on B for (B,C) - succeeds
    ]

    entry_a = _make_entry(2, "a", "~/.gai/diffs/a.diff")
    entry_b = _make_entry(2, "b", "~/.gai/diffs/b.diff")
    entry_c = _make_entry(2, "c", "~/.gai/diffs/c.diff")
    proposals = [(2, "a", entry_a), (2, "b", entry_b), (2, "c", entry_c)]

    pairs = _find_conflicting_pairs("/workspace", proposals)

    # A+B and A+C skipped because A fails, B+C succeeds
    assert len(pairs) == 0


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
