"""Tests for the saved_tag_names module."""

import json
from pathlib import Path
from unittest.mock import patch

from ace.saved_tag_names import load_saved_tag_names, save_tag_name


def test_load_saved_tag_names_no_file(tmp_path: Path) -> None:
    """Return empty list when file does not exist."""
    fake_file = tmp_path / "saved_tag_names.json"
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert load_saved_tag_names() == []


def test_load_saved_tag_names_valid(tmp_path: Path) -> None:
    """Return list of names from valid JSON."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps(["BUG", "FEATURE"]))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert load_saved_tag_names() == ["BUG", "FEATURE"]


def test_load_saved_tag_names_invalid_json(tmp_path: Path) -> None:
    """Return empty list on invalid JSON."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text("not json")
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert load_saved_tag_names() == []


def test_load_saved_tag_names_non_list(tmp_path: Path) -> None:
    """Return empty list when JSON is not a list."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps({"key": "value"}))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert load_saved_tag_names() == []


def test_save_tag_name_new(tmp_path: Path) -> None:
    """Save a new tag name to an empty file."""
    fake_file = tmp_path / "saved_tag_names.json"
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag_name("bug")
        data = json.loads(fake_file.read_text())
        assert data == ["BUG"]


def test_save_tag_name_deduplication(tmp_path: Path) -> None:
    """Do not duplicate an existing tag name."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps(["BUG"]))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag_name("bug")
        data = json.loads(fake_file.read_text())
        assert data == ["BUG"]


def test_save_tag_name_appends(tmp_path: Path) -> None:
    """Append a new name to existing list."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps(["BUG"]))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag_name("feature")
        data = json.loads(fake_file.read_text())
        assert data == ["BUG", "FEATURE"]


def test_save_tag_name_uppercases(tmp_path: Path) -> None:
    """Ensure saved names are uppercased."""
    fake_file = tmp_path / "saved_tag_names.json"
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag_name("My_Tag")
        data = json.loads(fake_file.read_text())
        assert data == ["MY_TAG"]
