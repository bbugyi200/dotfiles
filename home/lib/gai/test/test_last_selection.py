"""Tests for ace/last_selection.py module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from ace.last_selection import load_last_selection, save_last_selection


def test_load_last_selection_file_not_exists() -> None:
    """Test load_last_selection returns None when file doesn't exist."""
    with patch(
        "ace.last_selection._LAST_SELECTION_FILE", Path("/nonexistent/file.txt")
    ):
        result = load_last_selection()
        assert result is None


def test_load_last_selection_with_content() -> None:
    """Test load_last_selection returns content when file exists."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("my_changespec")
        temp_path = Path(f.name)

    try:
        with patch("ace.last_selection._LAST_SELECTION_FILE", temp_path):
            result = load_last_selection()
            assert result == "my_changespec"
    finally:
        temp_path.unlink()


def test_load_last_selection_empty_file() -> None:
    """Test load_last_selection returns None for empty file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("")
        temp_path = Path(f.name)

    try:
        with patch("ace.last_selection._LAST_SELECTION_FILE", temp_path):
            result = load_last_selection()
            assert result is None
    finally:
        temp_path.unlink()


def test_save_last_selection_success() -> None:
    """Test save_last_selection writes content to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "last_selection.txt"

        with patch("ace.last_selection._LAST_SELECTION_FILE", temp_path):
            result = save_last_selection("test_changespec")
            assert result is True
            assert temp_path.read_text() == "test_changespec"


def test_save_last_selection_creates_parent_dirs() -> None:
    """Test save_last_selection creates parent directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "subdir" / "last_selection.txt"

        with patch("ace.last_selection._LAST_SELECTION_FILE", temp_path):
            result = save_last_selection("test_changespec")
            assert result is True
            assert temp_path.exists()


def test_load_last_selection_oserror() -> None:
    """Test load_last_selection returns None on OSError."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("content")
        temp_path = Path(f.name)

    try:
        with (
            patch("ace.last_selection._LAST_SELECTION_FILE", temp_path),
            patch.object(Path, "read_text", side_effect=OSError("Simulated error")),
        ):
            result = load_last_selection()
            assert result is None
    finally:
        temp_path.unlink()


def test_save_last_selection_oserror() -> None:
    """Test save_last_selection returns False on OSError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "last_selection.txt"

        with (
            patch("ace.last_selection._LAST_SELECTION_FILE", temp_path),
            patch.object(Path, "write_text", side_effect=OSError("Simulated error")),
        ):
            result = save_last_selection("test_changespec")
            assert result is False
