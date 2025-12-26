"""Tests for accept_workflow module."""

import os
import tempfile

from accept_workflow import (
    _find_proposal_entry,
    _get_changespec_from_file,
    _parse_proposal_id,
    _renumber_history_entries,
)
from work.changespec import HistoryEntry


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
        result = _get_changespec_from_file(temp_path, "test_cl")
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
        result = _get_changespec_from_file(temp_path, "test_cl")
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
        result = _get_changespec_from_file(temp_path, "second_cl")
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
            temp_path, "test_cl", [(1, "a")], extra_msg="fix typo"
        )
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Check that extra_msg was appended
        assert "(2) Original note - fix typo" in content
    finally:
        os.unlink(temp_path)
