"""Tests for the saved_tag_names module."""

import json
from pathlib import Path
from unittest.mock import patch

from ace.saved_tag_names import load_saved_tags, save_tag

# --- load_saved_tags tests ---


def test_load_saved_tags_no_file(tmp_path: Path) -> None:
    """Return empty dict when file does not exist."""
    fake_file = tmp_path / "saved_tag_names.json"
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert load_saved_tags() == {}


def test_load_saved_tags_dict_format(tmp_path: Path) -> None:
    """Return dict from new dict format."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps({"BUG": "12345", "FEATURE": "v2"}))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert load_saved_tags() == {"BUG": "12345", "FEATURE": "v2"}


def test_load_saved_tags_legacy_list_format(tmp_path: Path) -> None:
    """Convert legacy list format to dict with empty values."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps(["BUG", "FEATURE"]))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert load_saved_tags() == {"BUG": "", "FEATURE": ""}


def test_load_saved_tags_invalid_json(tmp_path: Path) -> None:
    """Return empty dict on invalid JSON."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text("not json")
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert load_saved_tags() == {}


def test_load_saved_tags_non_dict_non_list(tmp_path: Path) -> None:
    """Return empty dict when JSON is neither dict nor list."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps(42))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert load_saved_tags() == {}


# --- load_saved_tags returns keys usable as tag name list ---


def test_load_saved_tags_keys_no_file(tmp_path: Path) -> None:
    """Return empty keys when file does not exist."""
    fake_file = tmp_path / "saved_tag_names.json"
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert list(load_saved_tags().keys()) == []


def test_load_saved_tags_keys_from_legacy_list(tmp_path: Path) -> None:
    """Return tag names from legacy list format."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps(["BUG", "FEATURE"]))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert list(load_saved_tags().keys()) == ["BUG", "FEATURE"]


def test_load_saved_tags_keys_from_dict_format(tmp_path: Path) -> None:
    """Return keys from dict format."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps({"BUG": "12345", "FEATURE": "v2"}))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert list(load_saved_tags().keys()) == ["BUG", "FEATURE"]


def test_load_saved_tags_keys_invalid_json(tmp_path: Path) -> None:
    """Return empty keys on invalid JSON."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text("not json")
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert list(load_saved_tags().keys()) == []


def test_load_saved_tags_keys_from_dict(tmp_path: Path) -> None:
    """Return keys when JSON is a dict (new format)."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps({"key": "value"}))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        assert list(load_saved_tags().keys()) == ["key"]


# --- save_tag tests ---


def test_save_tag_new(tmp_path: Path) -> None:
    """Save a new tag with value to an empty file."""
    fake_file = tmp_path / "saved_tag_names.json"
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag("bug", "12345")
        data = json.loads(fake_file.read_text())
        assert data == {"BUG": "12345"}


def test_save_tag_update_value(tmp_path: Path) -> None:
    """Update value of an existing tag."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps({"BUG": "12345"}))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag("bug", "67890")
        data = json.loads(fake_file.read_text())
        assert data == {"BUG": "67890"}


def test_save_tag_preserves_other_tags(tmp_path: Path) -> None:
    """Preserve other tags when saving a new one."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps({"BUG": "12345"}))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag("feature", "v2")
        data = json.loads(fake_file.read_text())
        assert data == {"BUG": "12345", "FEATURE": "v2"}


def test_save_tag_default_empty_value(tmp_path: Path) -> None:
    """Save a tag with default empty value."""
    fake_file = tmp_path / "saved_tag_names.json"
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag("bug")
        data = json.loads(fake_file.read_text())
        assert data == {"BUG": ""}


def test_save_tag_migrates_legacy_format(tmp_path: Path) -> None:
    """Migrate legacy list format when saving a new tag."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps(["BUG", "FEATURE"]))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag("test", "abc")
        data = json.loads(fake_file.read_text())
        assert data == {"BUG": "", "FEATURE": "", "TEST": "abc"}


def test_save_tag_uppercases(tmp_path: Path) -> None:
    """Ensure saved tag names are uppercased."""
    fake_file = tmp_path / "saved_tag_names.json"
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag("My_Tag")
        data = json.loads(fake_file.read_text())
        assert data == {"MY_TAG": ""}


def test_save_tag_deduplication_preserves_value(tmp_path: Path) -> None:
    """Saving an existing tag updates its value."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps({"BUG": "12345"}))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag("bug", "67890")
        data = json.loads(fake_file.read_text())
        assert data == {"BUG": "67890"}


def test_save_tag_appends_new(tmp_path: Path) -> None:
    """Append a new tag to existing tags."""
    fake_file = tmp_path / "saved_tag_names.json"
    fake_file.write_text(json.dumps({"BUG": "12345"}))
    with patch("ace.saved_tag_names._SAVED_TAG_NAMES_FILE", fake_file):
        save_tag("feature")
        data = json.loads(fake_file.read_text())
        assert data == {"BUG": "12345", "FEATURE": ""}
