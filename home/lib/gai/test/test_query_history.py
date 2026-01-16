"""Tests for query history stacks functionality."""

from pathlib import Path
from unittest.mock import patch

from ace.query_history import (
    MAX_STACK_SIZE,
    QueryHistoryStacks,
    load_query_history,
    navigate_next,
    navigate_prev,
    push_to_prev_stack,
    save_query_history,
)


def test_load_empty_when_no_file(tmp_path: Path) -> None:
    """Test loading returns empty stacks when no file exists."""
    with patch("ace.query_history._QUERY_HISTORY_FILE", tmp_path / "nonexistent.json"):
        result = load_query_history()
        assert result.prev == []
        assert result.next == []


def test_save_and_load(tmp_path: Path) -> None:
    """Test saving and loading stacks."""
    test_file = tmp_path / "query_history.json"
    with patch("ace.query_history._QUERY_HISTORY_FILE", test_file):
        stacks = QueryHistoryStacks(prev=["a", "b"], next=["c"])
        assert save_query_history(stacks)
        result = load_query_history()
        assert result.prev == ["a", "b"]
        assert result.next == ["c"]


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    """Test that save_query_history creates parent directory if needed."""
    test_file = tmp_path / "subdir" / "query_history.json"
    with patch("ace.query_history._QUERY_HISTORY_FILE", test_file):
        stacks = QueryHistoryStacks(prev=["test"], next=[])
        assert save_query_history(stacks)
        assert test_file.exists()


def test_push_to_prev_clears_next() -> None:
    """Test that pushing to prev clears the next stack."""
    stacks = QueryHistoryStacks(prev=["old"], next=["future"])
    push_to_prev_stack("current", stacks)
    assert stacks.prev == ["old", "current"]
    assert stacks.next == []


def test_push_to_prev_no_duplicates() -> None:
    """Test that pushing query removes existing duplicate anywhere in stack."""
    # Test non-consecutive duplicate - query exists earlier in stack
    stacks = QueryHistoryStacks(prev=["old", "current", "other"], next=[])
    push_to_prev_stack("current", stacks)
    # "current" removed from middle and added to end
    assert stacks.prev == ["old", "other", "current"]


def test_push_to_prev_allows_different() -> None:
    """Test that pushing different query is allowed."""
    stacks = QueryHistoryStacks(prev=["old"], next=[])
    push_to_prev_stack("new", stacks)
    assert stacks.prev == ["old", "new"]


def test_push_to_prev_empty_stack() -> None:
    """Test pushing to empty prev stack."""
    stacks = QueryHistoryStacks(prev=[], next=["future"])
    push_to_prev_stack("current", stacks)
    assert stacks.prev == ["current"]
    assert stacks.next == []


def test_navigate_prev_empty() -> None:
    """Test navigating prev when stack is empty."""
    stacks = QueryHistoryStacks(prev=[], next=[])
    result = navigate_prev("current", stacks)
    assert result is None
    assert stacks.prev == []
    assert stacks.next == []


def test_navigate_prev_success() -> None:
    """Test successful prev navigation."""
    stacks = QueryHistoryStacks(prev=["old1", "old2"], next=[])
    result = navigate_prev("current", stacks)
    assert result == "old2"
    assert stacks.prev == ["old1"]
    assert stacks.next == ["current"]


def test_navigate_prev_single_item() -> None:
    """Test navigating prev with single item in stack."""
    stacks = QueryHistoryStacks(prev=["only"], next=[])
    result = navigate_prev("current", stacks)
    assert result == "only"
    assert stacks.prev == []
    assert stacks.next == ["current"]


def test_navigate_prev_removes_duplicate_from_next() -> None:
    """Test that navigate_prev removes duplicate from next stack."""
    stacks = QueryHistoryStacks(prev=["old"], next=["future", "current", "other"])
    result = navigate_prev("current", stacks)
    assert result == "old"
    assert stacks.prev == []
    # "current" removed from middle of next stack and moved to end
    assert stacks.next == ["future", "other", "current"]


def test_navigate_next_empty() -> None:
    """Test navigating next when stack is empty."""
    stacks = QueryHistoryStacks(prev=[], next=[])
    result = navigate_next("current", stacks)
    assert result is None
    assert stacks.prev == []
    assert stacks.next == []


def test_navigate_next_success() -> None:
    """Test successful next navigation."""
    stacks = QueryHistoryStacks(prev=[], next=["future1", "future2"])
    result = navigate_next("current", stacks)
    assert result == "future2"
    assert stacks.prev == ["current"]
    assert stacks.next == ["future1"]


def test_navigate_next_single_item() -> None:
    """Test navigating next with single item in stack."""
    stacks = QueryHistoryStacks(prev=[], next=["only"])
    result = navigate_next("current", stacks)
    assert result == "only"
    assert stacks.prev == ["current"]
    assert stacks.next == []


def test_navigate_next_removes_duplicate_from_prev() -> None:
    """Test that navigate_next removes duplicate from prev stack."""
    stacks = QueryHistoryStacks(prev=["old", "current", "other"], next=["future"])
    result = navigate_next("current", stacks)
    assert result == "future"
    # "current" removed from middle of prev stack and moved to end
    assert stacks.prev == ["old", "other", "current"]
    assert stacks.next == []


def test_max_stack_size_on_save(tmp_path: Path) -> None:
    """Test that stacks are truncated to max size on save."""
    test_file = tmp_path / "query_history.json"
    with patch("ace.query_history._QUERY_HISTORY_FILE", test_file):
        # Create oversized stacks
        oversized_prev = [f"q{i}" for i in range(MAX_STACK_SIZE + 10)]
        stacks = QueryHistoryStacks(prev=oversized_prev, next=[])
        save_query_history(stacks)
        result = load_query_history()
        assert len(result.prev) == MAX_STACK_SIZE
        # Should keep the most recent (last) entries
        assert result.prev[-1] == f"q{MAX_STACK_SIZE + 9}"
        assert result.prev[0] == "q10"


def test_max_stack_size_on_push() -> None:
    """Test that push enforces max size."""
    stacks = QueryHistoryStacks(prev=[f"q{i}" for i in range(MAX_STACK_SIZE)], next=[])
    push_to_prev_stack("new", stacks)
    assert len(stacks.prev) == MAX_STACK_SIZE
    # Should keep most recent entries (including the new one)
    assert stacks.prev[-1] == "new"
    assert stacks.prev[0] == "q1"  # q0 dropped


def test_handles_corrupt_json(tmp_path: Path) -> None:
    """Test that corrupt JSON files are handled gracefully."""
    test_file = tmp_path / "query_history.json"
    test_file.write_text("not valid json {")
    with patch("ace.query_history._QUERY_HISTORY_FILE", test_file):
        result = load_query_history()
        assert result.prev == []
        assert result.next == []


def test_handles_missing_keys_in_json(tmp_path: Path) -> None:
    """Test that missing keys in JSON are handled gracefully."""
    test_file = tmp_path / "query_history.json"
    test_file.write_text('{"prev": ["a", "b"]}')  # missing "next"
    with patch("ace.query_history._QUERY_HISTORY_FILE", test_file):
        result = load_query_history()
        assert result.prev == ["a", "b"]
        assert result.next == []


def test_round_trip_navigation() -> None:
    """Test navigating back and forth preserves queries."""
    stacks = QueryHistoryStacks(prev=["q1", "q2"], next=[])

    # Navigate back twice
    r1 = navigate_prev("q3", stacks)
    assert r1 == "q2"
    r2 = navigate_prev("q2", stacks)
    assert r2 == "q1"

    # Navigate forward twice
    r3 = navigate_next("q1", stacks)
    assert r3 == "q2"
    r4 = navigate_next("q2", stacks)
    assert r4 == "q3"

    # Final state: back where we started
    assert stacks.prev == ["q1", "q2"]
    assert stacks.next == []


def test_new_query_clears_forward_history() -> None:
    """Test that entering a new query clears the forward history."""
    stacks = QueryHistoryStacks(prev=["q1", "q2"], next=[])

    # Navigate back
    result = navigate_prev("q3", stacks)
    assert result == "q2"
    assert stacks.next == ["q3"]

    # Enter new query (simulates user typing a new query after going back)
    push_to_prev_stack("q2", stacks)
    assert stacks.prev == ["q1", "q2"]
    assert stacks.next == []  # Forward history cleared


def test_empty_stacks_dataclass() -> None:
    """Test that empty QueryHistoryStacks can be created."""
    stacks = QueryHistoryStacks(prev=[], next=[])
    assert stacks.prev == []
    assert stacks.next == []
