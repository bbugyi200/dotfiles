"""Conflict checking for accept workflow proposals."""

from dataclasses import dataclass
from itertools import combinations

from ace.changespec import CommitEntry
from commit_utils import apply_diff_to_workspace, clean_workspace
from rich_utils import print_status


@dataclass
class ConflictPair:
    """A pair of proposals that conflict with each other."""

    proposal_a: tuple[int, str]  # (base_num, letter)
    proposal_b: tuple[int, str]
    error_message: str


@dataclass
class ConflictCheckResult:
    """Result of a conflict check."""

    success: bool
    failed_proposal: tuple[int, str] | None
    conflicting_pairs: list[ConflictPair]


def _format_proposal_id(base_num: int, letter: str) -> str:
    """Format a proposal ID for display.

    Args:
        base_num: The base number of the proposal.
        letter: The proposal letter.

    Returns:
        Formatted proposal ID like "(2a)".
    """
    return f"({base_num}{letter})"


def _apply_proposals_sequentially(
    workspace_dir: str,
    proposals: list[tuple[int, str, CommitEntry]],
) -> tuple[int, str, str] | None:
    """Apply proposals sequentially and return the first failure.

    Args:
        workspace_dir: The workspace directory.
        proposals: List of (base_num, letter, entry) tuples.

    Returns:
        Tuple of (base_num, letter, error_message) for the first failed proposal,
        or None if all succeeded.
    """
    for base_num, letter, entry in proposals:
        assert entry.diff is not None
        success, error_msg = apply_diff_to_workspace(workspace_dir, entry.diff)
        if not success:
            return (base_num, letter, error_msg)
    return None


def _find_conflicting_pairs(
    workspace_dir: str,
    proposals: list[tuple[int, str, CommitEntry]],
) -> list[ConflictPair]:
    """Find all unique pairs of proposals that conflict.

    Tests each unique pair by applying them in order (A then B).

    Args:
        workspace_dir: The workspace directory.
        proposals: List of (base_num, letter, entry) tuples.

    Returns:
        List of ConflictPair for each pair that conflicts.
    """
    conflicting_pairs: list[ConflictPair] = []

    for (num_a, letter_a, entry_a), (num_b, letter_b, entry_b) in combinations(
        proposals, 2
    ):
        # Clean workspace before each pair test
        clean_workspace(workspace_dir)

        # Apply first proposal
        assert entry_a.diff is not None
        success_a, _ = apply_diff_to_workspace(workspace_dir, entry_a.diff)
        if not success_a:
            # First proposal of pair can't even apply alone - skip this pair
            continue

        # Apply second proposal on top of first
        assert entry_b.diff is not None
        success_b, error_msg = apply_diff_to_workspace(workspace_dir, entry_b.diff)
        if not success_b:
            conflicting_pairs.append(
                ConflictPair(
                    proposal_a=(num_a, letter_a),
                    proposal_b=(num_b, letter_b),
                    error_message=error_msg,
                )
            )

    return conflicting_pairs


def run_conflict_check(
    workspace_dir: str,
    validated_proposals: list[tuple[int, str, str | None, CommitEntry]],
    verbose: bool = True,
) -> ConflictCheckResult:
    """Run conflict check on a set of proposals.

    This function tests whether all proposals can be applied sequentially.
    If any fails and there are >2 proposals, it identifies which specific
    pairs conflict.

    Args:
        workspace_dir: The workspace directory to test in.
        validated_proposals: List of (base_num, letter, msg, entry) tuples.
            The msg field is ignored for conflict checking.
        verbose: If True, print progress messages.

    Returns:
        ConflictCheckResult indicating success or failure details.
    """
    # Edge case: 0-1 proposals can't conflict
    if len(validated_proposals) <= 1:
        return ConflictCheckResult(
            success=True,
            failed_proposal=None,
            conflicting_pairs=[],
        )

    # Extract just what we need for conflict checking
    proposals = [
        (base_num, letter, entry)
        for base_num, letter, _msg, entry in validated_proposals
    ]

    if verbose:
        print_status(
            f"Running conflict check on {len(proposals)} proposals...",
            "progress",
        )

    # Try applying all proposals sequentially
    failure = _apply_proposals_sequentially(workspace_dir, proposals)

    # Clean workspace after sequential test
    clean_workspace(workspace_dir)

    if failure is None:
        # All proposals applied successfully
        return ConflictCheckResult(
            success=True,
            failed_proposal=None,
            conflicting_pairs=[],
        )

    # A proposal failed to apply
    base_num, letter, _error_msg = failure

    if verbose:
        print_status(
            f"Conflict detected: proposal {_format_proposal_id(base_num, letter)} "
            f"failed to apply",
            "error",
        )

    # For 2 proposals, no need to check pairs - we know they conflict
    if len(proposals) == 2:
        if verbose:
            print_status(
                "Accept aborted. Try accepting non-conflicting proposals separately.",
                "error",
            )
        return ConflictCheckResult(
            success=False,
            failed_proposal=(base_num, letter),
            conflicting_pairs=[],
        )

    # For >2 proposals, find which specific pairs conflict
    if verbose:
        print_status("Checking which proposals conflict...", "progress")

    conflicting_pairs = _find_conflicting_pairs(workspace_dir, proposals)

    # Clean workspace after pair testing
    clean_workspace(workspace_dir)

    if verbose:
        for pair in conflicting_pairs:
            print_status(
                f"Conflicting pair: {_format_proposal_id(*pair.proposal_a)} and "
                f"{_format_proposal_id(*pair.proposal_b)}",
                "error",
            )
        print_status(
            "Accept aborted. Try accepting non-conflicting proposals separately.",
            "error",
        )

    return ConflictCheckResult(
        success=False,
        failed_proposal=(base_num, letter),
        conflicting_pairs=conflicting_pairs,
    )
