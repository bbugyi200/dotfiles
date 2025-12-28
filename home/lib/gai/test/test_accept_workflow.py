"""Tests for accept_workflow module."""

import os
import tempfile
from typing import Any

from accept_workflow import (
    _build_entry_id_mapping,
    _find_proposal_entry,
    _get_entry_id,
    _parse_proposal_id,
    _renumber_history_entries,
    _sort_hook_status_lines,
    _update_hooks_with_id_mapping,
    parse_proposal_entries,
)
from search.changespec import HistoryEntry
from workflow_utils import get_changespec_from_file


# Tests for _parse_proposal_id
def test_parse_proposal_id_valid() -> None:
    """Test parsing valid proposal ID."""
    result = _parse_proposal_id("2a")
    assert result == (2, "a")


def test_parse_proposal_id_valid_larger_number() -> None:
    """Test parsing proposal ID with larger base number."""
    result = _parse_proposal_id("15b")
    assert result == (15, "b")


def test_parse_proposal_id_invalid_no_letter() -> None:
    """Test parsing invalid proposal ID without letter."""
    result = _parse_proposal_id("2")
    assert result is None


def test_parse_proposal_id_invalid_uppercase() -> None:
    """Test parsing invalid proposal ID with uppercase letter."""
    result = _parse_proposal_id("2A")
    assert result is None


def test_parse_proposal_id_invalid_empty() -> None:
    """Test parsing empty proposal ID."""
    result = _parse_proposal_id("")
    assert result is None


def test_parse_proposal_id_invalid_letters_only() -> None:
    """Test parsing proposal ID with letters only."""
    result = _parse_proposal_id("abc")
    assert result is None


# Tests for parse_proposal_entries
def test_parse_proposal_entries_single_with_message() -> None:
    """Test parsing single entry with message in parentheses."""
    result = parse_proposal_entries(["2a(Add foobar)"])
    assert result == [("2a", "Add foobar")]


def test_parse_proposal_entries_single_without_message() -> None:
    """Test parsing single entry without message."""
    result = parse_proposal_entries(["2a"])
    assert result == [("2a", None)]


def test_parse_proposal_entries_multiple() -> None:
    """Test parsing multiple entries with mixed messages."""
    result = parse_proposal_entries(["2b(Add foobar)", "2a", "2c(Fix typo)"])
    assert result == [("2b", "Add foobar"), ("2a", None), ("2c", "Fix typo")]


def test_parse_proposal_entries_legacy_syntax() -> None:
    """Test parsing legacy syntax with separate message argument."""
    result = parse_proposal_entries(["2a", "some message"])
    assert result == [("2a", "some message")]


def test_parse_proposal_entries_legacy_syntax_multi() -> None:
    """Test that legacy syntax only applies to single entry."""
    # When multiple proposal IDs exist, message shouldn't consume next ID
    result = parse_proposal_entries(["2a", "2b"])
    assert result == [("2a", None), ("2b", None)]


def test_parse_proposal_entries_invalid_format() -> None:
    """Test that invalid format returns None."""
    result = parse_proposal_entries(["invalid"])
    assert result is None


def test_parse_proposal_entries_empty_list() -> None:
    """Test that empty list returns None."""
    result = parse_proposal_entries([])
    assert result is None


def test_parse_proposal_entries_message_with_spaces() -> None:
    """Test parsing message with spaces in parentheses."""
    result = parse_proposal_entries(["2a(Add the foobar field)"])
    assert result == [("2a", "Add the foobar field")]


def test_parse_proposal_entries_complex_mix() -> None:
    """Test complex mix of entries."""
    result = parse_proposal_entries(["1a(First)", "1b", "2a(Second change)"])
    assert result == [("1a", "First"), ("1b", None), ("2a", "Second change")]


# Tests for _find_proposal_entry
def test_find_proposal_entry_found() -> None:
    """Test finding proposal entry that exists."""
    history = [
        HistoryEntry(number=1, note="First commit"),
        HistoryEntry(number=2, note="Second commit"),
        HistoryEntry(number=2, note="First proposal", proposal_letter="a"),
        HistoryEntry(number=2, note="Second proposal", proposal_letter="b"),
    ]
    result = _find_proposal_entry(history, 2, "a")
    assert result is not None
    assert result.note == "First proposal"


def test_find_proposal_entry_not_found_wrong_number() -> None:
    """Test finding proposal entry with wrong base number."""
    history = [
        HistoryEntry(number=2, note="First proposal", proposal_letter="a"),
    ]
    result = _find_proposal_entry(history, 3, "a")
    assert result is None


def test_find_proposal_entry_not_found_wrong_letter() -> None:
    """Test finding proposal entry with wrong letter."""
    history = [
        HistoryEntry(number=2, note="First proposal", proposal_letter="a"),
    ]
    result = _find_proposal_entry(history, 2, "b")
    assert result is None


def test_find_proposal_entry_empty_history() -> None:
    """Test finding proposal entry in empty history."""
    result = _find_proposal_entry([], 2, "a")
    assert result is None


def test_find_proposal_entry_none_history() -> None:
    """Test finding proposal entry with None history."""
    result = _find_proposal_entry(None, 2, "a")
    assert result is None


# Tests for _get_changespec_from_file
def test_get_changespec_from_file_found() -> None:
    """Test getting changespec that exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("DESCRIPTION:\n")
        f.write("  Test description\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = get_changespec_from_file(temp_path, "test_cl")
        assert result is not None
        assert result.name == "test_cl"
    finally:
        os.unlink(temp_path)


def test_get_changespec_from_file_not_found() -> None:
    """Test getting changespec that doesn't exist."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: other_cl\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = get_changespec_from_file(temp_path, "test_cl")
        assert result is None
    finally:
        os.unlink(temp_path)


def test_get_changespec_from_file_multiple_specs() -> None:
    """Test getting changespec from file with multiple specs."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: first_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("\n")
        f.write("NAME: second_cl\n")
        f.write("STATUS: Mailed\n")
        temp_path = f.name

    try:
        result = get_changespec_from_file(temp_path, "second_cl")
        assert result is not None
        assert result.name == "second_cl"
    finally:
        os.unlink(temp_path)


# Tests for _renumber_history_entries
def test_renumber_history_entries_accept_single_proposal() -> None:
    """Test renumbering after accepting a single proposal."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("  (1) First commit\n")
        f.write("      | DIFF: ~/.gai/diffs/first.diff\n")
        f.write("  (2) Second commit\n")
        f.write("      | DIFF: ~/.gai/diffs/second.diff\n")
        f.write("  (2a) First proposal\n")
        f.write("      | DIFF: ~/.gai/diffs/proposal_a.diff\n")
        f.write("  (2b) Second proposal\n")
        f.write("      | DIFF: ~/.gai/diffs/proposal_b.diff\n")
        temp_path = f.name

    try:
        result = _renumber_history_entries(temp_path, "test_cl", [(2, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # (2a) became (3)
        assert "(3) First proposal" in content
        # (2b) became (3a) - renumbered to new base
        assert "(3a) Second proposal" in content
        # Original entries unchanged
        assert "(1) First commit" in content
        assert "(2) Second commit" in content
    finally:
        os.unlink(temp_path)


def test_renumber_history_entries_accept_multiple_proposals() -> None:
    """Test renumbering after accepting multiple proposals."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal A\n")
        f.write("  (1b) Proposal B\n")
        f.write("  (1c) Proposal C\n")
        temp_path = f.name

    try:
        # Accept a and c, leaving b as a proposal
        result = _renumber_history_entries(temp_path, "test_cl", [(1, "a"), (1, "c")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # (1) unchanged
        assert "(1) First commit" in content
        # (1a) became (2) - first accepted
        assert "(2) Proposal A" in content
        # (1c) became (3) - second accepted
        assert "(3) Proposal C" in content
        # (1b) became (3a) - remaining proposal renumbered
        assert "(3a) Proposal B" in content
    finally:
        os.unlink(temp_path)


def test_renumber_history_entries_no_remaining_proposals() -> None:
    """Test renumbering when all proposals are accepted."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Only proposal\n")
        temp_path = f.name

    try:
        result = _renumber_history_entries(temp_path, "test_cl", [(1, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        assert "(1) First commit" in content
        assert "(2) Only proposal" in content
        # No proposal letters should remain
        assert "(2a)" not in content
    finally:
        os.unlink(temp_path)


def test_renumber_history_entries_nonexistent_file() -> None:
    """Test renumbering with non-existent file."""
    result = _renumber_history_entries("/nonexistent/file.gp", "test_cl", [(1, "a")])
    assert result is False


def test_renumber_history_entries_no_history_section() -> None:
    """Test renumbering when no HISTORY section exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = _renumber_history_entries(temp_path, "test_cl", [(1, "a")])
        assert result is False
    finally:
        os.unlink(temp_path)


def test_renumber_history_entries_preserves_diffs() -> None:
    """Test that renumbering preserves DIFF paths."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("  (1) First commit\n")
        f.write("      | DIFF: ~/.gai/diffs/first.diff\n")
        f.write("  (1a) Proposal\n")
        f.write("      | CHAT: ~/.gai/chats/proposal.md\n")
        f.write("      | DIFF: ~/.gai/diffs/proposal.diff\n")
        temp_path = f.name

    try:
        result = _renumber_history_entries(temp_path, "test_cl", [(1, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Original diffs preserved
        assert "| DIFF: ~/.gai/diffs/first.diff" in content
        # Proposal diffs preserved
        assert "| CHAT: ~/.gai/chats/proposal.md" in content
        assert "| DIFF: ~/.gai/diffs/proposal.diff" in content
    finally:
        os.unlink(temp_path)


def test_renumber_history_entries_with_extra_msg() -> None:
    """Test that extra_msg is appended to accepted entry note."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Original note\n")
        temp_path = f.name

    try:
        result = _renumber_history_entries(
            temp_path, "test_cl", [(1, "a")], extra_msgs=["fix typo"]
        )
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Check that extra_msg was appended
        assert "(2) Original note - fix typo" in content
    finally:
        os.unlink(temp_path)


def test_renumber_history_entries_with_per_proposal_messages() -> None:
    """Test that per-proposal messages are appended to each accepted entry."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal A\n")
        f.write("  (1b) Proposal B\n")
        f.write("  (1c) Proposal C\n")
        temp_path = f.name

    try:
        # Accept a and c with messages, b stays as proposal
        result = _renumber_history_entries(
            temp_path,
            "test_cl",
            [(1, "a"), (1, "c")],
            extra_msgs=["Add foobar field", "Fix the baz"],
        )
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # (1a) became (2) with message
        assert "(2) Proposal A - Add foobar field" in content
        # (1c) became (3) with message
        assert "(3) Proposal C - Fix the baz" in content
        # (1b) became (3a) - no message
        assert "(3a) Proposal B" in content
        # Make sure "Proposal B" doesn't have an extra message
        assert "Proposal B - " not in content
    finally:
        os.unlink(temp_path)


def test_renumber_history_entries_with_mixed_none_messages() -> None:
    """Test that None messages in extra_msgs don't append anything."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal A\n")
        f.write("  (1b) Proposal B\n")
        temp_path = f.name

    try:
        # Accept both, but only first has a message
        result = _renumber_history_entries(
            temp_path,
            "test_cl",
            [(1, "a"), (1, "b")],
            extra_msgs=["Has message", None],
        )
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # (1a) became (2) with message
        assert "(2) Proposal A - Has message" in content
        # (1b) became (3) without message
        assert "(3) Proposal B\n" in content or "(3) Proposal B" in content
        # Make sure "Proposal B" doesn't have an extra message
        assert "Proposal B - " not in content
    finally:
        os.unlink(temp_path)


def test_renumber_history_entries_updates_hook_status_lines() -> None:
    """Test that hook status lines are updated with new entry IDs."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("  (1) First commit\n")
        f.write("  (2) Second commit\n")
        f.write("  (2a) First proposal\n")
        f.write("  (2b) Second proposal\n")
        f.write("HOOKS:\n")
        f.write("  make lint\n")
        f.write("    (1) [251224_120000] PASSED (1m23s)\n")
        f.write("    (2) [251224_120100] PASSED (2m45s)\n")
        f.write("    (2a) [251224_120200] PASSED (30s)\n")
        f.write("    (2b) [251224_120300] RUNNING\n")
        temp_path = f.name

    try:
        result = _renumber_history_entries(temp_path, "test_cl", [(2, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # History entries renumbered
        assert "(3) First proposal" in content
        assert "(3a) Second proposal" in content

        # Hook status lines should be updated
        # (1) unchanged
        assert "(1) [251224_120000] PASSED (1m23s)" in content
        # (2) unchanged
        assert "(2) [251224_120100] PASSED (2m45s)" in content
        # (2a) became (3)
        assert "(3) [251224_120200] PASSED (30s)" in content
        # (2b) became (3a)
        assert "(3a) [251224_120300] RUNNING" in content
    finally:
        os.unlink(temp_path)


def test_renumber_history_entries_sorts_hook_status_lines() -> None:
    """Test that hook status lines are sorted by entry ID after renumbering."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal A\n")
        f.write("  (1b) Proposal B\n")
        f.write("HOOKS:\n")
        f.write("  make lint\n")
        # Status lines in non-sorted order
        f.write("    (1b) [251224_120200] RUNNING\n")
        f.write("    (1) [251224_120000] PASSED (1m23s)\n")
        f.write("    (1a) [251224_120100] PASSED (30s)\n")
        temp_path = f.name

    try:
        # Accept 1a, so 1b becomes 2a
        result = _renumber_history_entries(temp_path, "test_cl", [(1, "a")])
        assert result is True

        with open(temp_path) as f:
            lines = f.readlines()

        # Find the hook status lines
        status_lines = [line for line in lines if line.strip().startswith("(")]

        # Should be sorted: (1), (2), (2a)
        assert "(1)" in status_lines[0]
        assert "(2)" in status_lines[1]
        assert "(2a)" in status_lines[2]
    finally:
        os.unlink(temp_path)


def test_renumber_history_entries_preserves_hook_suffix() -> None:
    """Test that hook status line suffixes are preserved during renumbering."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal\n")
        f.write("HOOKS:\n")
        f.write("  make lint\n")
        f.write("    (1) [251224_120000] PASSED (1m23s)\n")
        f.write("    (1a) [251224_120100] FAILED (30s) - (!)\n")
        temp_path = f.name

    try:
        result = _renumber_history_entries(temp_path, "test_cl", [(1, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # The suffix "- (!)" should be preserved
        assert "(2) [251224_120100] FAILED (30s) - (!)" in content
    finally:
        os.unlink(temp_path)


def test_renumber_history_entries_multiple_hooks() -> None:
    """Test renumbering with multiple hooks."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("  (1) First commit\n")
        f.write("  (1a) Proposal\n")
        f.write("HOOKS:\n")
        f.write("  make lint\n")
        f.write("    (1) [251224_120000] PASSED (1m23s)\n")
        f.write("    (1a) [251224_120100] PASSED (30s)\n")
        f.write("  make test\n")
        f.write("    (1) [251224_120000] PASSED (5m0s)\n")
        f.write("    (1a) [251224_120100] FAILED (2m30s)\n")
        temp_path = f.name

    try:
        result = _renumber_history_entries(temp_path, "test_cl", [(1, "a")])
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Both hooks should have their status lines updated
        # make lint: (1a) -> (2)
        assert "make lint" in content
        assert "(2) [251224_120100] PASSED (30s)" in content

        # make test: (1a) -> (2)
        assert "make test" in content
        assert "(2) [251224_120100] FAILED (2m30s)" in content
    finally:
        os.unlink(temp_path)


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
    """Test building ID mapping for simple case."""
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

    mapping = _build_entry_id_mapping(
        entries, new_entries, accepted_proposals, next_regular, remaining_proposals
    )

    assert mapping == {"1": "1", "1a": "2"}


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
        {"number": 2, "letter": "a", "note": "Proposal B"},
    ]
    accepted_proposals = [(1, "a")]
    next_regular = 3
    remaining_proposals: list[dict[str, Any]] = [
        {"number": 1, "letter": "b", "note": "Proposal B"}
    ]

    mapping = _build_entry_id_mapping(
        entries, new_entries, accepted_proposals, next_regular, remaining_proposals
    )

    assert mapping == {"1": "1", "1a": "2", "1b": "2a"}


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
    id_mapping = {"1a": "2"}

    result = _update_hooks_with_id_mapping(lines, "test_cl", id_mapping)

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
    id_mapping = {"1a": "2"}

    result = _update_hooks_with_id_mapping(lines, "test_cl", id_mapping)

    # other_cl should be unchanged
    assert "    (1a) [251224_120100] PASSED (30s)\n" in result
    # test_cl should be updated
    assert "    (2) [251224_120200] PASSED (30s)\n" in result


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
