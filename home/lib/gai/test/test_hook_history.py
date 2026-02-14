"""Tests for hook history functionality."""

from pathlib import Path
from unittest.mock import patch

from hook_history import (
    HookHistoryEntry,
    _load_hook_history,
    _save_hook_history,
    add_or_update_hook,
    get_hooks_for_display,
)


def test_load_empty_when_no_file(tmp_path: Path) -> None:
    """Test loading returns empty list when no file exists."""
    with patch("hook_history._HOOK_HISTORY_FILE", tmp_path / "nonexistent.json"):
        result = _load_hook_history()
        assert result == []


def test_save_and_load_hook(tmp_path: Path) -> None:
    """Test saving and loading a hook."""
    test_file = tmp_path / "hook_history.json"
    with patch("hook_history._HOOK_HISTORY_FILE", test_file):
        entry = HookHistoryEntry(
            command="make test",
            timestamp="251231_143052",
            last_used="251231_143052",
        )
        assert _save_hook_history([entry])
        result = _load_hook_history()
        assert len(result) == 1
        assert result[0].command == "make test"
        assert result[0].timestamp == "251231_143052"
        assert result[0].last_used == "251231_143052"


def test_save_multiple_hooks(tmp_path: Path) -> None:
    """Test saving multiple hooks."""
    test_file = tmp_path / "hook_history.json"
    with patch("hook_history._HOOK_HISTORY_FILE", test_file):
        entries = [
            HookHistoryEntry(
                command="make test",
                timestamp="251231_143052",
                last_used="251231_143052",
            ),
            HookHistoryEntry(
                command="make build",
                timestamp="251231_143053",
                last_used="251231_143053",
            ),
        ]
        assert _save_hook_history(entries)
        result = _load_hook_history()
        assert len(result) == 2
        assert result[0].command == "make test"
        assert result[1].command == "make build"


def test_add_new_hook(tmp_path: Path) -> None:
    """Test adding a new hook to history."""
    test_file = tmp_path / "hook_history.json"
    with (
        patch("hook_history._HOOK_HISTORY_FILE", test_file),
        patch("hook_history.generate_timestamp", return_value="251231_143052"),
    ):
        add_or_update_hook("make test")
        result = _load_hook_history()
        assert len(result) == 1
        assert result[0].command == "make test"
        assert result[0].timestamp == "251231_143052"
        assert result[0].last_used == "251231_143052"


def test_add_duplicate_updates_timestamp(tmp_path: Path) -> None:
    """Test that adding same command replaces the entry."""
    test_file = tmp_path / "hook_history.json"
    with patch("hook_history._HOOK_HISTORY_FILE", test_file):
        # Add initial hook
        initial_entry = HookHistoryEntry(
            command="make test",
            timestamp="251231_100000",
            last_used="251231_100000",
        )
        _save_hook_history([initial_entry])

        # Add the same hook again
        with patch("hook_history.generate_timestamp", return_value="251231_200000"):
            add_or_update_hook("make test")

        result = _load_hook_history()
        # Should still be only 1 hook (deduplicated)
        assert len(result) == 1
        assert result[0].command == "make test"
        # Both timestamps should be updated (new entry)
        assert result[0].timestamp == "251231_200000"
        assert result[0].last_used == "251231_200000"


def test_different_commands_not_deduplicated(tmp_path: Path) -> None:
    """Test that different commands are not deduplicated."""
    test_file = tmp_path / "hook_history.json"
    with patch("hook_history._HOOK_HISTORY_FILE", test_file):
        # Add initial hook
        initial_entry = HookHistoryEntry(
            command="make test",
            timestamp="251231_100000",
            last_used="251231_100000",
        )
        _save_hook_history([initial_entry])

        # Add a different hook
        with patch("hook_history.generate_timestamp", return_value="251231_200000"):
            add_or_update_hook("make build")

        result = _load_hook_history()
        # Should have 2 entries (different commands)
        assert len(result) == 2


def test_get_hooks_for_display_empty(tmp_path: Path) -> None:
    """Test get_hooks_for_display returns empty list when no history."""
    test_file = tmp_path / "hook_history.json"
    with patch("hook_history._HOOK_HISTORY_FILE", test_file):
        result = get_hooks_for_display()
        assert result == []


def test_get_hooks_for_display_sorted_by_recency(tmp_path: Path) -> None:
    """Test that hooks are sorted by last_used descending."""
    test_file = tmp_path / "hook_history.json"
    with patch("hook_history._HOOK_HISTORY_FILE", test_file):
        entries = [
            HookHistoryEntry(
                command="older command",
                timestamp="251231_100000",
                last_used="251231_100000",
            ),
            HookHistoryEntry(
                command="newer command",
                timestamp="251231_200000",
                last_used="251231_200000",
            ),
        ]
        _save_hook_history(entries)

        result = get_hooks_for_display()
        assert len(result) == 2
        # Newer command should be first
        assert result[0].command == "newer command"
        assert result[1].command == "older command"


def test_handles_corrupt_json(tmp_path: Path) -> None:
    """Test that corrupt JSON files are handled gracefully."""
    test_file = tmp_path / "hook_history.json"
    test_file.write_text("not valid json {")
    with patch("hook_history._HOOK_HISTORY_FILE", test_file):
        result = _load_hook_history()
        assert result == []


def test_handles_missing_fields_in_json(tmp_path: Path) -> None:
    """Test that JSON entries with missing fields are filtered out."""
    test_file = tmp_path / "hook_history.json"
    test_file.write_text(
        '{"hooks": [{"command": "valid", '
        '"timestamp": "251231_143052", "last_used": "251231_143052"}, '
        '{"command": "missing_fields"}]}'
    )
    with patch("hook_history._HOOK_HISTORY_FILE", test_file):
        result = _load_hook_history()
        assert len(result) == 1
        assert result[0].command == "valid"


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    """Test that save_hook_history creates parent directory if needed."""
    test_file = tmp_path / "subdir" / "hook_history.json"
    with patch("hook_history._HOOK_HISTORY_FILE", test_file):
        entry = HookHistoryEntry(
            command="make test",
            timestamp="251231_143052",
            last_used="251231_143052",
        )
        assert _save_hook_history([entry])
        assert test_file.exists()
