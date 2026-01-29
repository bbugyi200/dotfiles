"""Tests for command history functionality."""

from pathlib import Path
from unittest.mock import patch

from command_history import (
    CommandEntry,
    _format_command_for_display,
    _load_command_history,
    _save_command_history,
    add_or_update_command,
    get_commands_for_display,
)


def test_load_empty_when_no_file(tmp_path: Path) -> None:
    """Test loading returns empty list when no file exists."""
    with patch("command_history._COMMAND_HISTORY_FILE", tmp_path / "nonexistent.json"):
        result = _load_command_history()
        assert result == []


def test_save_and_load_command(tmp_path: Path) -> None:
    """Test saving and loading a command."""
    test_file = tmp_path / "command_history.json"
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        entry = CommandEntry(
            command="make test",
            project="myproject",
            cl_name="feature-branch",
            timestamp="251231_143052",
            last_used="251231_143052",
        )
        assert _save_command_history([entry])
        result = _load_command_history()
        assert len(result) == 1
        assert result[0].command == "make test"
        assert result[0].project == "myproject"
        assert result[0].cl_name == "feature-branch"


def test_save_command_without_cl_name(tmp_path: Path) -> None:
    """Test saving a command without CL name."""
    test_file = tmp_path / "command_history.json"
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        entry = CommandEntry(
            command="make build",
            project="myproject",
            cl_name=None,
            timestamp="251231_143052",
            last_used="251231_143052",
        )
        assert _save_command_history([entry])
        result = _load_command_history()
        assert len(result) == 1
        assert result[0].command == "make build"
        assert result[0].cl_name is None


def test_save_multiple_commands(tmp_path: Path) -> None:
    """Test saving multiple commands."""
    test_file = tmp_path / "command_history.json"
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        entries = [
            CommandEntry(
                command="make test",
                project="project1",
                cl_name=None,
                timestamp="251231_143052",
                last_used="251231_143052",
            ),
            CommandEntry(
                command="make build",
                project="project2",
                cl_name="feature",
                timestamp="251231_143053",
                last_used="251231_143053",
            ),
        ]
        assert _save_command_history(entries)
        result = _load_command_history()
        assert len(result) == 2
        assert result[0].command == "make test"
        assert result[1].command == "make build"


def test_add_new_command(tmp_path: Path) -> None:
    """Test adding a new command to history."""
    test_file = tmp_path / "command_history.json"
    with (
        patch("command_history._COMMAND_HISTORY_FILE", test_file),
        patch("command_history.generate_timestamp", return_value="251231_143052"),
    ):
        add_or_update_command("make test", "myproject", "feature-branch")
        result = _load_command_history()
        assert len(result) == 1
        assert result[0].command == "make test"
        assert result[0].project == "myproject"
        assert result[0].cl_name == "feature-branch"
        assert result[0].timestamp == "251231_143052"
        assert result[0].last_used == "251231_143052"


def test_add_duplicate_replaces_entry(tmp_path: Path) -> None:
    """Test that adding same (command, project, cl_name) replaces the entry."""
    test_file = tmp_path / "command_history.json"
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        # Add initial command
        initial_entry = CommandEntry(
            command="make test",
            project="myproject",
            cl_name="feature",
            timestamp="251231_100000",
            last_used="251231_100000",
        )
        _save_command_history([initial_entry])

        # Add the same command again
        with patch("command_history.generate_timestamp", return_value="251231_200000"):
            add_or_update_command("make test", "myproject", "feature")

        result = _load_command_history()
        # Should still be only 1 command (deduplicated)
        assert len(result) == 1
        assert result[0].command == "make test"
        # Both timestamps should be updated (new entry)
        assert result[0].timestamp == "251231_200000"
        assert result[0].last_used == "251231_200000"


def test_same_command_different_project_not_deduplicated(tmp_path: Path) -> None:
    """Test that same command on different project is not deduplicated."""
    test_file = tmp_path / "command_history.json"
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        # Add initial command
        initial_entry = CommandEntry(
            command="make test",
            project="project1",
            cl_name=None,
            timestamp="251231_100000",
            last_used="251231_100000",
        )
        _save_command_history([initial_entry])

        # Add same command for different project
        with patch("command_history.generate_timestamp", return_value="251231_200000"):
            add_or_update_command("make test", "project2", None)

        result = _load_command_history()
        # Should have 2 entries (different projects)
        assert len(result) == 2


def test_same_command_different_cl_not_deduplicated(tmp_path: Path) -> None:
    """Test that same command on different CL is not deduplicated."""
    test_file = tmp_path / "command_history.json"
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        # Add initial command
        initial_entry = CommandEntry(
            command="make test",
            project="myproject",
            cl_name="feature1",
            timestamp="251231_100000",
            last_used="251231_100000",
        )
        _save_command_history([initial_entry])

        # Add same command for different CL
        with patch("command_history.generate_timestamp", return_value="251231_200000"):
            add_or_update_command("make test", "myproject", "feature2")

        result = _load_command_history()
        # Should have 2 entries (different CLs)
        assert len(result) == 2


def test_format_command_for_display_current_cl() -> None:
    """Test formatting a command from the current CL shows asterisk."""
    entry = CommandEntry(
        command="make test",
        project="myproject",
        cl_name="feature",
        timestamp="251231_143052",
        last_used="251231_143052",
    )
    result = _format_command_for_display(entry, "feature", "myproject", 20)
    assert result.startswith("*")
    assert "myproject/feature" in result
    assert "make test" in result


def test_format_command_for_display_same_project() -> None:
    """Test formatting a command from same project but different CL shows tilde."""
    entry = CommandEntry(
        command="make test",
        project="myproject",
        cl_name="other-feature",
        timestamp="251231_143052",
        last_used="251231_143052",
    )
    result = _format_command_for_display(entry, "feature", "myproject", 25)
    assert result.startswith("~")
    assert "myproject/other-feature" in result


def test_format_command_for_display_other_project() -> None:
    """Test formatting a command from another project shows space."""
    entry = CommandEntry(
        command="make test",
        project="otherproject",
        cl_name=None,
        timestamp="251231_143052",
        last_used="251231_143052",
    )
    result = _format_command_for_display(entry, "feature", "myproject", 15)
    assert result.startswith(" ")
    assert "otherproject" in result


def test_format_command_truncates_long_commands() -> None:
    """Test that long commands are truncated with ellipsis."""
    entry = CommandEntry(
        command="a" * 100,
        project="myproject",
        cl_name=None,
        timestamp="251231_143052",
        last_used="251231_143052",
    )
    result = _format_command_for_display(entry, None, "myproject", 10)
    assert "..." in result
    # Should not contain the full command
    assert "a" * 100 not in result


def test_get_commands_for_display_empty(tmp_path: Path) -> None:
    """Test get_commands_for_display returns empty list when no history."""
    test_file = tmp_path / "command_history.json"
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        result = get_commands_for_display("feature", "myproject")
        assert result == []


def test_get_commands_for_display_sorts_current_cl_first(tmp_path: Path) -> None:
    """Test that commands from current CL are sorted first."""
    test_file = tmp_path / "command_history.json"
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        entries = [
            CommandEntry(
                command="other cl command",
                project="myproject",
                cl_name="other-feature",
                timestamp="251231_143052",
                last_used="251231_200000",  # More recent
            ),
            CommandEntry(
                command="current cl command",
                project="myproject",
                cl_name="feature",
                timestamp="251231_143052",
                last_used="251231_100000",  # Less recent
            ),
        ]
        _save_command_history(entries)

        result = get_commands_for_display("feature", "myproject")
        assert len(result) == 2
        # Current CL should be first despite being less recent
        assert result[0][1].command == "current cl command"
        assert result[1][1].command == "other cl command"


def test_get_commands_for_display_sorts_project_second(tmp_path: Path) -> None:
    """Test that commands from same project but different CL are sorted second."""
    test_file = tmp_path / "command_history.json"
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        entries = [
            CommandEntry(
                command="other project command",
                project="otherproject",
                cl_name=None,
                timestamp="251231_143052",
                last_used="251231_300000",  # Most recent
            ),
            CommandEntry(
                command="same project command",
                project="myproject",
                cl_name="other-feature",
                timestamp="251231_143052",
                last_used="251231_200000",  # Middle
            ),
            CommandEntry(
                command="current cl command",
                project="myproject",
                cl_name="feature",
                timestamp="251231_143052",
                last_used="251231_100000",  # Least recent
            ),
        ]
        _save_command_history(entries)

        result = get_commands_for_display("feature", "myproject")
        assert len(result) == 3
        # Current CL first, then same project, then other
        assert result[0][1].command == "current cl command"
        assert result[1][1].command == "same project command"
        assert result[2][1].command == "other project command"


def test_get_commands_for_display_sorts_by_recency_within_tier(tmp_path: Path) -> None:
    """Test that commands within same tier are sorted by recency."""
    test_file = tmp_path / "command_history.json"
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        entries = [
            CommandEntry(
                command="older command",
                project="myproject",
                cl_name="feature",
                timestamp="251231_143052",
                last_used="251231_100000",
            ),
            CommandEntry(
                command="newer command",
                project="myproject",
                cl_name="feature",
                timestamp="251231_143052",
                last_used="251231_200000",
            ),
        ]
        _save_command_history(entries)

        result = get_commands_for_display("feature", "myproject")
        assert len(result) == 2
        # Newer command should be first
        assert result[0][1].command == "newer command"
        assert result[1][1].command == "older command"


def test_handles_corrupt_json(tmp_path: Path) -> None:
    """Test that corrupt JSON files are handled gracefully."""
    test_file = tmp_path / "command_history.json"
    test_file.write_text("not valid json {")
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        result = _load_command_history()
        assert result == []


def test_handles_missing_fields_in_json(tmp_path: Path) -> None:
    """Test that JSON entries with missing fields are filtered out."""
    test_file = tmp_path / "command_history.json"
    test_file.write_text(
        '{"commands": [{"command": "valid", "project": "proj", '
        '"timestamp": "251231_143052", "last_used": "251231_143052"}, '
        '{"command": "missing_fields"}]}'
    )
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        result = _load_command_history()
        assert len(result) == 1
        assert result[0].command == "valid"


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    """Test that save_command_history creates parent directory if needed."""
    test_file = tmp_path / "subdir" / "command_history.json"
    with patch("command_history._COMMAND_HISTORY_FILE", test_file):
        entry = CommandEntry(
            command="make test",
            project="myproject",
            cl_name=None,
            timestamp="251231_143052",
            last_used="251231_143052",
        )
        assert _save_command_history([entry])
        assert test_file.exists()
