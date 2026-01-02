"""Tests for proposal parsing and lookup functions in accept_workflow module."""

import os
import tempfile

from accept_workflow import (
    expand_shorthand_proposals,
    find_proposal_entry,
    parse_proposal_entries,
    parse_proposal_entries_with_shorthand,
    parse_proposal_id,
)
from ace.changespec import CommitEntry
from workflow_utils import get_changespec_from_file


# Tests for parse_proposal_id
def testparse_proposal_id_valid() -> None:
    """Test parsing valid proposal ID."""
    result = parse_proposal_id("2a")
    assert result == (2, "a")


def testparse_proposal_id_valid_larger_number() -> None:
    """Test parsing proposal ID with larger base number."""
    result = parse_proposal_id("15b")
    assert result == (15, "b")


def testparse_proposal_id_invalid_no_letter() -> None:
    """Test parsing invalid proposal ID without letter."""
    result = parse_proposal_id("2")
    assert result is None


def testparse_proposal_id_invalid_uppercase() -> None:
    """Test parsing invalid proposal ID with uppercase letter."""
    result = parse_proposal_id("2A")
    assert result is None


def testparse_proposal_id_invalid_empty() -> None:
    """Test parsing empty proposal ID."""
    result = parse_proposal_id("")
    assert result is None


def testparse_proposal_id_invalid_letters_only() -> None:
    """Test parsing proposal ID with letters only."""
    result = parse_proposal_id("abc")
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


# Tests for expand_shorthand_proposals
def test_expand_shorthand_proposals_bare_letters() -> None:
    """Test expanding bare letter shortcuts."""
    result = expand_shorthand_proposals(["a", "b", "c"], "2")
    assert result == ["2a", "2b", "2c"]


def test_expand_shorthand_proposals_letters_with_messages() -> None:
    """Test expanding letter shortcuts with messages."""
    result = expand_shorthand_proposals(["a(fix typo)", "b(add test)"], "3")
    assert result == ["3a(fix typo)", "3b(add test)"]


def test_expand_shorthand_proposals_full_ids_passthrough() -> None:
    """Test that full IDs are passed through unchanged."""
    result = expand_shorthand_proposals(["2a", "2b(msg)"], "3")
    assert result == ["2a", "2b(msg)"]


def test_expand_shorthand_proposals_mixed() -> None:
    """Test mixing shorthand and full IDs."""
    result = expand_shorthand_proposals(["a", "2b(msg)", "c(fix)"], "3")
    assert result == ["3a", "2b(msg)", "3c(fix)"]


def test_expand_shorthand_proposals_no_base_with_shorthand() -> None:
    """Test that shorthand without base returns None."""
    result = expand_shorthand_proposals(["a", "b"], None)
    assert result is None


def test_expand_shorthand_proposals_no_base_with_full_ids() -> None:
    """Test that full IDs work without base."""
    result = expand_shorthand_proposals(["2a", "2b"], None)
    assert result == ["2a", "2b"]


def test_expand_shorthand_proposals_invalid_format() -> None:
    """Test that invalid format returns None."""
    result = expand_shorthand_proposals(["invalid"], "2")
    assert result is None


def test_expand_shorthand_proposals_empty_list() -> None:
    """Test that empty list returns empty list."""
    result = expand_shorthand_proposals([], "2")
    assert result == []


# Tests for parse_proposal_entries_with_shorthand
def test_parse_proposal_entries_with_shorthand_bare_letters() -> None:
    """Test parsing bare letter shortcuts."""
    result = parse_proposal_entries_with_shorthand(["a", "b"], "2")
    assert result == [("2a", None), ("2b", None)]


def test_parse_proposal_entries_with_shorthand_letters_with_messages() -> None:
    """Test parsing letter shortcuts with messages."""
    result = parse_proposal_entries_with_shorthand(["a(fix)", "b(test)"], "2")
    assert result == [("2a", "fix"), ("2b", "test")]


def test_parse_proposal_entries_with_shorthand_mixed() -> None:
    """Test parsing mixed shorthand and full IDs."""
    result = parse_proposal_entries_with_shorthand(["a", "3b(msg)", "c(fix)"], "2")
    assert result == [("2a", None), ("3b", "msg"), ("2c", "fix")]


def test_parse_proposal_entries_with_shorthand_no_base() -> None:
    """Test that shorthand without base returns None."""
    result = parse_proposal_entries_with_shorthand(["a", "b"], None)
    assert result is None


# Tests for find_proposal_entry
def testfind_proposal_entry_found() -> None:
    """Test finding proposal entry that exists."""
    history = [
        CommitEntry(number=1, note="First commit"),
        CommitEntry(number=2, note="Second commit"),
        CommitEntry(number=2, note="First proposal", proposal_letter="a"),
        CommitEntry(number=2, note="Second proposal", proposal_letter="b"),
    ]
    result = find_proposal_entry(history, 2, "a")
    assert result is not None
    assert result.note == "First proposal"


def testfind_proposal_entry_not_found_wrong_number() -> None:
    """Test finding proposal entry with wrong base number."""
    history = [
        CommitEntry(number=2, note="First proposal", proposal_letter="a"),
    ]
    result = find_proposal_entry(history, 3, "a")
    assert result is None


def testfind_proposal_entry_not_found_wrong_letter() -> None:
    """Test finding proposal entry with wrong letter."""
    history = [
        CommitEntry(number=2, note="First proposal", proposal_letter="a"),
    ]
    result = find_proposal_entry(history, 2, "b")
    assert result is None


def testfind_proposal_entry_empty_history() -> None:
    """Test finding proposal entry in empty history."""
    result = find_proposal_entry([], 2, "a")
    assert result is None


def testfind_proposal_entry_none_history() -> None:
    """Test finding proposal entry with None history."""
    result = find_proposal_entry(None, 2, "a")
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
