"""Tests for query selection persistence."""

from pathlib import Path
from unittest.mock import patch

from ace.query_selection import (
    MAX_SELECTIONS,
    load_query_selections,
    save_query_selections,
)


def test_load_empty_when_no_file(tmp_path: Path) -> None:
    """Test loading returns empty dict when no file exists."""
    with patch(
        "ace.query_selection._QUERY_SELECTION_FILE", tmp_path / "nonexistent.json"
    ):
        result = load_query_selections()
        assert result == {}


def test_save_and_load(tmp_path: Path) -> None:
    """Test saving and loading selections."""
    test_file = tmp_path / "query_selections.json"
    with patch("ace.query_selection._QUERY_SELECTION_FILE", test_file):
        selections = {"query_a": "cl_1", "query_b": "cl_2"}
        assert save_query_selections(selections)
        result = load_query_selections()
        assert result == {"query_a": "cl_1", "query_b": "cl_2"}


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    """Test that save creates parent directory if needed."""
    test_file = tmp_path / "subdir" / "query_selections.json"
    with patch("ace.query_selection._QUERY_SELECTION_FILE", test_file):
        selections = {"query": "cl"}
        assert save_query_selections(selections)
        assert test_file.exists()


def test_max_selections_trimming(tmp_path: Path) -> None:
    """Test that saving >MAX_SELECTIONS trims to MAX_SELECTIONS."""
    test_file = tmp_path / "query_selections.json"
    with patch("ace.query_selection._QUERY_SELECTION_FILE", test_file):
        selections = {f"q{i}": f"cl{i}" for i in range(MAX_SELECTIONS + 20)}
        save_query_selections(selections)
        result = load_query_selections()
        assert len(result) == MAX_SELECTIONS


def test_trimming_keeps_most_recent(tmp_path: Path) -> None:
    """Test that trimming keeps the most recently inserted entries."""
    test_file = tmp_path / "query_selections.json"
    with patch("ace.query_selection._QUERY_SELECTION_FILE", test_file):
        selections: dict[str, str] = {}
        for i in range(MAX_SELECTIONS + 5):
            selections[f"q{i}"] = f"cl{i}"
        save_query_selections(selections)
        result = load_query_selections()
        # Oldest 5 entries (q0..q4) should be trimmed
        for i in range(5):
            assert f"q{i}" not in result
        # Most recent entries should remain
        assert f"q{MAX_SELECTIONS + 4}" in result
        assert result[f"q{MAX_SELECTIONS + 4}"] == f"cl{MAX_SELECTIONS + 4}"


def test_handles_corrupt_json(tmp_path: Path) -> None:
    """Test that corrupt JSON files are handled gracefully."""
    test_file = tmp_path / "query_selections.json"
    test_file.write_text("not valid json {")
    with patch("ace.query_selection._QUERY_SELECTION_FILE", test_file):
        result = load_query_selections()
        assert result == {}


def test_handles_non_dict_json(tmp_path: Path) -> None:
    """Test that non-dict JSON is handled gracefully."""
    test_file = tmp_path / "query_selections.json"
    test_file.write_text('["a", "b"]')
    with patch("ace.query_selection._QUERY_SELECTION_FILE", test_file):
        result = load_query_selections()
        assert result == {}
