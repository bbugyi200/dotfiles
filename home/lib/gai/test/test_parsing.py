"""Tests for proposal parsing and lookup functions in accept_workflow module."""

import os
import tempfile

from accept_workflow import (
    _find_proposal_entry,
    _parse_proposal_id,
    parse_proposal_entries,
)
from ace.changespec import CommitEntry
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
        CommitEntry(number=1, note="First commit"),
        CommitEntry(number=2, note="Second commit"),
        CommitEntry(number=2, note="First proposal", proposal_letter="a"),
        CommitEntry(number=2, note="Second proposal", proposal_letter="b"),
    ]
    result = _find_proposal_entry(history, 2, "a")
    assert result is not None
    assert result.note == "First proposal"


def test_find_proposal_entry_not_found_wrong_number() -> None:
    """Test finding proposal entry with wrong base number."""
    history = [
        CommitEntry(number=2, note="First proposal", proposal_letter="a"),
    ]
    result = _find_proposal_entry(history, 3, "a")
    assert result is None


def test_find_proposal_entry_not_found_wrong_letter() -> None:
    """Test finding proposal entry with wrong letter."""
    history = [
        CommitEntry(number=2, note="First proposal", proposal_letter="a"),
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


# Tests for get_changespec_from_file
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
