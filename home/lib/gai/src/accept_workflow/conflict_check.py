"""Conflict checking for accept workflow proposals."""

from dataclasses import dataclass
from itertools import combinations

from ace.changespec import CommitEntry
from commit_utils import apply_diffs_to_workspace, clean_workspace
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


def _apply_all_proposals(
    workspace_dir: str,
    proposals: list[tuple[int, str, CommitEntry]],
) -> tuple[bool, str]:
    """Apply all proposals together and check if they succeed.

    Args:
        workspace_dir: The workspace directory.
        proposals: List of (base_num, letter, entry) tuples.

    Returns:
        Tuple of (success, error_message).
    """
    diff_paths = []
    for _base_num, _letter, entry in proposals:
        assert entry.diff is not None
        diff_paths.append(entry.diff)

    return apply_diffs_to_workspace(workspace_dir, diff_paths)


def _find_conflicting_pairs(
    workspace_dir: str,
    proposals: list[tuple[int, str, CommitEntry]],
) -> list[ConflictPair]:
    """Find all unique pairs of proposals that conflict.

    Tests each unique pair by applying both diffs together in a single command.

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

        # Apply both proposals together
        assert entry_a.diff is not None
        assert entry_b.diff is not None
        success, error_msg = apply_diffs_to_workspace(
            workspace_dir, [entry_a.diff, entry_b.diff]
        )
        if not success:
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

    This function tests whether all proposals can be applied together using
    a single hg import command. If they fail and there are >2 proposals,
    it identifies which specific pairs conflict.

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

    # Try applying all proposals together
    success, error_msg = _apply_all_proposals(workspace_dir, proposals)

    # Clean workspace after test
    clean_workspace(workspace_dir)

    if success:
        return ConflictCheckResult(
            success=True,
            failed_proposal=None,
            conflicting_pairs=[],
        )

    # Proposals failed to apply together
    if verbose:
        print_status(
            f"Conflict detected when applying proposals together: {error_msg}",
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
            failed_proposal=None,  # Can't determine which one failed
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
        failed_proposal=None,  # Can't determine which one failed
        conflicting_pairs=conflicting_pairs,
    )


def format_conflict_message(result: ConflictCheckResult) -> str:
    """Format conflict information for display.

    Args:
        result: The conflict check result.

    Returns:
        A formatted message describing the conflicts.
    """
    lines: list[str] = []

    # Add conflicting pair messages (only if there are any)
    for pair in result.conflicting_pairs:
        lines.append(
            f"Conflicting pair: {_format_proposal_id(*pair.proposal_a)} and "
            f"{_format_proposal_id(*pair.proposal_b)}"
        )

    # Always add the abort message
    lines.append("Accept aborted. Try accepting non-conflicting proposals separately.")

    return "\n".join(lines)
