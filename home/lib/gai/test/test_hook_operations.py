"""Tests for hook operations and ID mapping functions in accept_workflow module."""

from typing import Any

from accept_workflow.renumber import (
    _build_entry_id_mapping,
    _get_entry_id,
    _sort_hook_status_lines,
    _update_hooks_with_id_mapping,
)


# Tests for _get_entry_id
def test_get_entry_id_regular() -> None:
    """Test getting entry ID for regular entry."""
    entry = {"number": 2, "letter": None}
    assert _get_entry_id(entry) == "2"


def test_get_entry_id_proposal() -> None:
    """Test getting entry ID for proposal entry."""
    entry = {"number": 2, "letter": "a"}
    assert _get_entry_id(entry) == "2a"


# Tests for _build_entry_id_mapping
def test_build_entry_id_mapping_simple() -> None:
    """Test building ID mapping for simple case (single proposal)."""
    entries: list[dict[str, Any]] = [
        {"number": 1, "letter": None, "note": "First"},
        {"number": 1, "letter": "a", "note": "Proposal A"},
    ]
    new_entries: list[dict[str, Any]] = [
        {"number": 1, "letter": None, "note": "First"},
        {"number": 2, "letter": None, "note": "Proposal A"},
    ]
    accepted_proposals = [(1, "a")]
    next_regular = 3
    remaining_proposals: list[dict[str, str | int | None]] = []

    promote_mapping, archive_mapping = _build_entry_id_mapping(
        entries, new_entries, accepted_proposals, next_regular, remaining_proposals
    )

    # Single proposal: promoted, no archiving
    assert promote_mapping == {"1": "1", "1a": "2"}
    assert archive_mapping == {}


def test_build_entry_id_mapping_with_remaining() -> None:
    """Test building ID mapping with remaining proposals."""
    entries: list[dict[str, Any]] = [
        {"number": 1, "letter": None, "note": "First"},
        {"number": 1, "letter": "a", "note": "Proposal A"},
        {"number": 1, "letter": "b", "note": "Proposal B"},
    ]
    new_entries: list[dict[str, Any]] = [
        {"number": 1, "letter": None, "note": "First"},
        {"number": 2, "letter": None, "note": "Proposal A"},
        {"number": 1, "letter": "b", "note": "Proposal B"},
    ]
    accepted_proposals = [(1, "a")]
    next_regular = 3
    remaining_proposals: list[dict[str, Any]] = [
        {"number": 1, "letter": "b", "note": "Proposal B"}
    ]

    promote_mapping, archive_mapping = _build_entry_id_mapping(
        entries, new_entries, accepted_proposals, next_regular, remaining_proposals
    )

    # Single proposal: promoted, no archiving
    # Remaining proposal keeps original ID unchanged
    assert promote_mapping == {"1": "1", "1a": "2", "1b": "1b"}
    assert archive_mapping == {}


def test_build_entry_id_mapping_multi_accept_first_promoted_others_archived() -> None:
    """Test that first accepted proposal is promoted, others are archived."""
    entries: list[dict[str, Any]] = [
        {"number": 1, "letter": None, "note": "First"},
        {"number": 1, "letter": "a", "note": "Proposal A"},
        {"number": 1, "letter": "b", "note": "Proposal B"},
        {"number": 1, "letter": "c", "note": "Proposal C"},
    ]
    new_entries: list[dict[str, Any]] = []  # Not used for this test
    # Accept c first, then a -> c becomes 2, a becomes 3
    accepted_proposals = [(1, "c"), (1, "a")]
    next_regular = 4  # After accepting 2 proposals: 2, 3
    remaining_proposals: list[dict[str, Any]] = [
        {"number": 1, "letter": "b", "note": "Proposal B"}
    ]

    promote_mapping, archive_mapping = _build_entry_id_mapping(
        entries, new_entries, accepted_proposals, next_regular, remaining_proposals
    )

    # First accepted (1c) promoted to 2, second (1a) also in promote for suffix updates
    assert promote_mapping["1c"] == "2"
    assert promote_mapping["1a"] == "3"
    # Remaining proposal keeps original ID unchanged
    assert promote_mapping["1b"] == "1b"
    # Second accepted (1a) has archive mapping
    assert archive_mapping == {"1a": "1a-3"}


# Tests for _update_hooks_with_id_mapping
def test_update_hooks_with_id_mapping() -> None:
    """Test updating hooks with ID mapping."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  make lint\n",
        "    (1a) [251224_120100] PASSED (30s)\n",
    ]
    promote_mapping = {"1a": "2"}

    result = _update_hooks_with_id_mapping(lines, "test_cl", promote_mapping)

    assert "    (2) [251224_120100] PASSED (30s)\n" in result


def test_update_hooks_with_id_mapping_preserves_other_changespecs() -> None:
    """Test that updating hooks doesn't affect other changespecs."""
    lines = [
        "NAME: other_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  make lint\n",
        "    (1a) [251224_120100] PASSED (30s)\n",
        "\n",
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  make lint\n",
        "    (1a) [251224_120200] PASSED (30s)\n",
    ]
    promote_mapping = {"1a": "2"}

    result = _update_hooks_with_id_mapping(lines, "test_cl", promote_mapping)

    # other_cl should be unchanged
    assert "    (1a) [251224_120100] PASSED (30s)\n" in result
    # test_cl should be updated
    assert "    (2) [251224_120200] PASSED (30s)\n" in result


def test_update_hooks_with_id_mapping_updates_proposal_id_suffix() -> None:
    """Test that proposal ID suffixes are updated in hook status lines."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  make lint\n",
        "    (1a) [251224_120100] PASSED (30s) - (1a)\n",
    ]
    promote_mapping = {"1a": "2"}

    result = _update_hooks_with_id_mapping(lines, "test_cl", promote_mapping)

    # Proposal ID suffix should be updated to the new entry ID
    assert "    (2) [251224_120100] PASSED (30s) - (2)\n" in result
    # Original suffix should NOT be present
    assert "- (1a)" not in "".join(result)


def test_update_hooks_with_id_mapping_archives_non_first_proposals() -> None:
    """Test that non-first accepted proposals are archived, not promoted."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  make lint\n",
        "    (1c) [251224_120100] PASSED (30s)\n",
        "    (1a) [251224_120200] PASSED (45s)\n",
    ]
    promote_mapping = {"1c": "2", "1a": "3"}
    archive_mapping = {"1a": "1a-3"}

    result = _update_hooks_with_id_mapping(
        lines, "test_cl", promote_mapping, archive_mapping
    )

    # First proposal promoted: (1c) -> (2)
    assert "    (2) [251224_120100] PASSED (30s)\n" in result
    # Second proposal archived: (1a) -> (1a-3)
    assert "    (1a-3) [251224_120200] PASSED (45s)\n" in result
    # Original IDs should not appear
    assert "(1c)" not in "".join(result)


def test_update_hooks_with_id_mapping_suffix_updated_for_archived() -> None:
    """Test that suffixes are updated to new ID even for archived proposals."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  make lint\n",
        "    (1a) [251224_120100] FAILED (30s) - (1a)\n",
    ]
    promote_mapping = {"1a": "3"}
    archive_mapping = {"1a": "1a-3"}

    result = _update_hooks_with_id_mapping(
        lines, "test_cl", promote_mapping, archive_mapping
    )

    # Prefix archived: (1a) -> (1a-3)
    # Suffix promoted: - (1a) -> - (3)
    assert "    (1a-3) [251224_120100] FAILED (30s) - (3)\n" in result


def test_update_hooks_with_id_mapping_suffix_with_summary() -> None:
    """Test that proposal ID suffixes with summaries are updated correctly."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  bb_hg_lint\n",
        "    (1) [260101_141242] FAILED (5s) - (1a | Lint failed: Missing Javadoc)\n",
    ]
    promote_mapping = {"1a": "3"}

    result = _update_hooks_with_id_mapping(lines, "test_cl", promote_mapping)

    # Proposal ID suffix should be updated, summary preserved
    assert (
        "    (1) [260101_141242] FAILED (5s) - (3 | Lint failed: Missing Javadoc)\n"
        in result
    )
    # Original suffix should NOT be present
    assert "- (1a |" not in "".join(result)


def test_update_hooks_single_proposal_no_archive() -> None:
    """Test that single proposal acceptance works as before (no archiving)."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  make lint\n",
        "    (1a) [251224_120100] PASSED (30s)\n",
    ]
    promote_mapping = {"1a": "2"}
    archive_mapping: dict[str, str] = {}  # Empty - no archiving for single proposal

    result = _update_hooks_with_id_mapping(
        lines, "test_cl", promote_mapping, archive_mapping
    )

    # Promoted normally: (1a) -> (2)
    assert "    (2) [251224_120100] PASSED (30s)\n" in result


# Tests for _sort_hook_status_lines
def test_sort_hook_status_lines() -> None:
    """Test sorting hook status lines."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  make lint\n",
        "    (2) [251224_120100] PASSED (30s)\n",
        "    (1) [251224_120000] PASSED (1m23s)\n",
        "    (1a) [251224_120050] RUNNING\n",
    ]

    result = _sort_hook_status_lines(lines, "test_cl")

    # Find status line indices
    status_lines = [line for line in result if line.strip().startswith("(")]
    assert "(1)" in status_lines[0]
    assert "(1a)" in status_lines[1]
    assert "(2)" in status_lines[2]


def test_sort_hook_status_lines_multiple_hooks() -> None:
    """Test sorting status lines across multiple hooks."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  make lint\n",
        "    (2) [251224_120100] PASSED (30s)\n",
        "    (1) [251224_120000] PASSED (1m23s)\n",
        "  make test\n",
        "    (2) [251224_120100] FAILED (2m0s)\n",
        "    (1) [251224_120000] PASSED (5m0s)\n",
    ]

    result = _sort_hook_status_lines(lines, "test_cl")

    # Both hooks should have sorted status lines
    hooks_section = "".join(result)
    # First hook's (1) should come before (2)
    lint_idx_1 = hooks_section.find("(1) [251224_120000] PASSED (1m23s)")
    lint_idx_2 = hooks_section.find("(2) [251224_120100] PASSED (30s)")
    assert lint_idx_1 < lint_idx_2

    # Second hook's (1) should come before (2)
    test_idx_1 = hooks_section.find("(1) [251224_120000] PASSED (5m0s)")
    test_idx_2 = hooks_section.find("(2) [251224_120100] FAILED (2m0s)")
    assert test_idx_1 < test_idx_2


def test_sort_hook_status_lines_with_archived_format() -> None:
    """Test sorting handles (1a-3) archive format correctly."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "HOOKS:\n",
        "  make lint\n",
        "    (2) [251224_120100] PASSED (30s)\n",
        "    (1a-3) [251224_120200] PASSED (45s)\n",
        "    (1b) [251224_120300] RUNNING\n",
    ]

    result = _sort_hook_status_lines(lines, "test_cl")

    status_lines = [line for line in result if line.strip().startswith("(")]
    # Should be sorted by original base+letter: (1a-3), (1b), (2)
    assert "(1a-3)" in status_lines[0]
    assert "(1b)" in status_lines[1]
    assert "(2)" in status_lines[2]
