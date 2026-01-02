"""Tests for saved queries functionality."""

from pathlib import Path
from unittest.mock import patch

from ace.saved_queries import (
    KEY_ORDER,
    _write_queries,
    delete_query,
    get_next_available_slot,
    load_saved_queries,
    save_query,
)


def test_key_order() -> None:
    """Test that key order is 0-9."""
    assert KEY_ORDER == ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]


def test_load_empty_when_no_file(tmp_path: Path) -> None:
    """Test loading returns empty dict when no file exists."""
    with patch("ace.saved_queries._SAVED_QUERIES_FILE", tmp_path / "nonexistent.json"):
        result = load_saved_queries()
        assert result == {}


def test_save_and_load_query(tmp_path: Path) -> None:
    """Test saving and loading a query."""
    test_file = tmp_path / "saved_queries.json"
    with patch("ace.saved_queries._SAVED_QUERIES_FILE", test_file):
        assert save_query("1", '"test"')
        result = load_saved_queries()
        assert result == {"1": '"test"'}


def test_save_multiple_queries(tmp_path: Path) -> None:
    """Test saving multiple queries to different slots."""
    test_file = tmp_path / "saved_queries.json"
    with patch("ace.saved_queries._SAVED_QUERIES_FILE", test_file):
        assert save_query("1", '"query1"')
        assert save_query("3", '"query3"')
        assert save_query("0", '"query0"')
        result = load_saved_queries()
        assert result == {"1": '"query1"', "3": '"query3"', "0": '"query0"'}


def test_overwrite_existing_slot(tmp_path: Path) -> None:
    """Test that saving to an existing slot overwrites the query."""
    test_file = tmp_path / "saved_queries.json"
    with patch("ace.saved_queries._SAVED_QUERIES_FILE", test_file):
        assert save_query("1", '"original"')
        assert save_query("1", '"updated"')
        result = load_saved_queries()
        assert result == {"1": '"updated"'}


def test_delete_query(tmp_path: Path) -> None:
    """Test deleting a query from a slot."""
    test_file = tmp_path / "saved_queries.json"
    with patch("ace.saved_queries._SAVED_QUERIES_FILE", test_file):
        assert save_query("1", '"test"')
        assert save_query("2", '"test2"')
        assert delete_query("1")
        result = load_saved_queries()
        assert result == {"2": '"test2"'}


def test_delete_nonexistent_query(tmp_path: Path) -> None:
    """Test deleting from an empty slot returns True."""
    test_file = tmp_path / "saved_queries.json"
    with patch("ace.saved_queries._SAVED_QUERIES_FILE", test_file):
        # Should return True even when slot doesn't exist
        assert delete_query("5")


def test_get_next_available_slot_empty() -> None:
    """Test getting next slot when empty."""
    result = get_next_available_slot({})
    assert result == "0"


def test_get_next_available_slot_partial() -> None:
    """Test getting next slot with some used."""
    result = get_next_available_slot({"0": "a", "1": "b"})
    assert result == "2"


def test_get_next_available_slot_gaps() -> None:
    """Test getting next slot when there are gaps."""
    # Slots 0 and 2 are used, 1 should be next
    result = get_next_available_slot({"0": "a", "2": "c"})
    assert result == "1"


def test_get_next_available_slot_full() -> None:
    """Test getting next slot when all full."""
    full = dict.fromkeys(KEY_ORDER, "q")
    result = get_next_available_slot(full)
    assert result is None


def test_invalid_slot_rejected(tmp_path: Path) -> None:
    """Test that invalid slots are rejected."""
    test_file = tmp_path / "saved_queries.json"
    with patch("ace.saved_queries._SAVED_QUERIES_FILE", test_file):
        result = save_query("X", '"test"')
        assert result is False


def test_invalid_slot_not_stored(tmp_path: Path) -> None:
    """Test that invalid slots in JSON are filtered out on load."""
    test_file = tmp_path / "saved_queries.json"
    test_file.write_text('{"1": "valid", "X": "invalid", "11": "also_invalid"}')
    with patch("ace.saved_queries._SAVED_QUERIES_FILE", test_file):
        result = load_saved_queries()
        assert result == {"1": "valid"}


def test_handles_corrupt_json(tmp_path: Path) -> None:
    """Test that corrupt JSON files are handled gracefully."""
    test_file = tmp_path / "saved_queries.json"
    test_file.write_text("not valid json {")
    with patch("ace.saved_queries._SAVED_QUERIES_FILE", test_file):
        result = load_saved_queries()
        assert result == {}


def test_write_creates_parent_directory(tmp_path: Path) -> None:
    """Test that _write_queries creates parent directory if needed."""
    test_file = tmp_path / "subdir" / "saved_queries.json"
    with patch("ace.saved_queries._SAVED_QUERIES_FILE", test_file):
        assert _write_queries({"1": "test"})
        assert test_file.exists()
