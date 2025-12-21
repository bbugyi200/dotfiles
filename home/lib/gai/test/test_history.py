"""Tests for HISTORY field parsing and history_utils module."""

import os
import tempfile
from pathlib import Path

from history_utils import (
    _ensure_diffs_directory,
    _generate_timestamp,
    _get_diffs_directory,
    _get_next_history_number,
    add_history_entry,
    save_diff,
)
from work.changespec import (
    HistoryEntry,
    _build_history_entry,
    _parse_changespec_from_lines,
)


# Tests for _build_history_entry
def test_build_history_entry_all_fields() -> None:
    """Test building HistoryEntry with all fields."""
    entry_dict: dict[str, str | int | None] = {
        "number": 1,
        "note": "Initial Commit",
        "chat": "~/.gai/chats/test.md",
        "diff": "~/.gai/diffs/test.diff",
    }
    entry = _build_history_entry(entry_dict)
    assert entry.number == 1
    assert entry.note == "Initial Commit"
    assert entry.chat == "~/.gai/chats/test.md"
    assert entry.diff == "~/.gai/diffs/test.diff"


def test_build_history_entry_missing_optional_fields() -> None:
    """Test building HistoryEntry with only required fields."""
    entry_dict: dict[str, str | int | None] = {
        "number": 2,
        "note": "Test commit",
        "chat": None,
        "diff": None,
    }
    entry = _build_history_entry(entry_dict)
    assert entry.number == 2
    assert entry.note == "Test commit"
    assert entry.chat is None
    assert entry.diff is None


def test_build_history_entry_defaults() -> None:
    """Test building HistoryEntry with empty dict (all defaults)."""
    entry_dict: dict[str, str | int | None] = {}
    entry = _build_history_entry(entry_dict)
    assert entry.number == 0
    assert entry.note == ""
    assert entry.chat is None
    assert entry.diff is None


# Tests for HISTORY field parsing
def test_parse_changespec_with_history() -> None:
    """Test parsing ChangeSpec with HISTORY field."""
    lines = [
        "## ChangeSpec\n",
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "HISTORY:\n",
        "(1) Initial Commit\n",
        "    | CHAT: ~/.gai/chats/test-251221130813.md\n",
        "    | DIFF: ~/.gai/diffs/test_251221130813.diff\n",
        "(2) Added feature\n",
        "    | DIFF: ~/.gai/diffs/test_251221140000.diff\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.name == "test_cl"
    assert changespec.history is not None
    assert len(changespec.history) == 2
    # Check first entry
    assert changespec.history[0].number == 1
    assert changespec.history[0].note == "Initial Commit"
    assert changespec.history[0].chat == "~/.gai/chats/test-251221130813.md"
    assert changespec.history[0].diff == "~/.gai/diffs/test_251221130813.diff"
    # Check second entry
    assert changespec.history[1].number == 2
    assert changespec.history[1].note == "Added feature"
    assert changespec.history[1].chat is None
    assert changespec.history[1].diff == "~/.gai/diffs/test_251221140000.diff"


def test_parse_changespec_without_history() -> None:
    """Test parsing ChangeSpec without HISTORY field."""
    lines = [
        "## ChangeSpec\n",
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.name == "test_cl"
    assert changespec.history is None


def test_parse_changespec_history_without_optional_fields() -> None:
    """Test parsing HISTORY entry without CHAT field."""
    lines = [
        "## ChangeSpec\n",
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "HISTORY:\n",
        "(1) Manual commit\n",
        "    | DIFF: ~/.gai/diffs/test.diff\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.history is not None
    assert len(changespec.history) == 1
    assert changespec.history[0].number == 1
    assert changespec.history[0].note == "Manual commit"
    assert changespec.history[0].chat is None
    assert changespec.history[0].diff == "~/.gai/diffs/test.diff"


# Tests for history_utils functions
def test_get_diffs_directory() -> None:
    """Test getting diffs directory path."""
    expected = os.path.expanduser("~/.gai/diffs")
    assert _get_diffs_directory() == expected


def test_ensure_diffs_directory() -> None:
    """Test that ensure_diffs_directory creates the directory."""
    # This should not raise any errors
    _ensure_diffs_directory()
    diffs_dir = _get_diffs_directory()
    assert os.path.isdir(diffs_dir)


def test_generate_timestamp_format() -> None:
    """Test that timestamp has correct format."""
    timestamp = _generate_timestamp()
    # Should be 12 characters: YYmmddHHMMSS
    assert len(timestamp) == 12
    # Should be all digits
    assert timestamp.isdigit()


def test_get_next_history_number_no_history() -> None:
    """Test getting next history number when no history exists."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
    ]
    next_num = _get_next_history_number(lines, "test_cl")
    assert next_num == 1


def test_get_next_history_number_with_history() -> None:
    """Test getting next history number when history exists."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
        "HISTORY:\n",
        "(1) First commit\n",
        "    | DIFF: test.diff\n",
        "(2) Second commit\n",
        "    | DIFF: test2.diff\n",
    ]
    next_num = _get_next_history_number(lines, "test_cl")
    assert next_num == 3


def test_get_next_history_number_wrong_changespec() -> None:
    """Test getting next history number for non-existent changespec."""
    lines = [
        "NAME: other_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
        "HISTORY:\n",
        "(1) First commit\n",
    ]
    next_num = _get_next_history_number(lines, "test_cl")
    assert next_num == 1


def test_add_history_entry_new_history_field() -> None:
    """Test adding history entry when HISTORY field doesn't exist."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("DESCRIPTION:\n")
        f.write("  Test description\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = add_history_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Initial Commit",
            diff_path="~/.gai/diffs/test.diff",
            chat_path="~/.gai/chats/test.md",
        )
        assert result is True

        # Verify the file contents
        with open(temp_path) as f:
            content = f.read()
        assert "HISTORY:" in content
        assert "(1) Initial Commit" in content
        assert "| CHAT: ~/.gai/chats/test.md" in content
        assert "| DIFF: ~/.gai/diffs/test.diff" in content
    finally:
        os.unlink(temp_path)


def test_add_history_entry_existing_history_field() -> None:
    """Test adding history entry when HISTORY field already exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("DESCRIPTION:\n")
        f.write("  Test description\n")
        f.write("STATUS: Drafted\n")
        f.write("HISTORY:\n")
        f.write("(1) First commit\n")
        f.write("    | DIFF: ~/.gai/diffs/first.diff\n")
        temp_path = f.name

    try:
        result = add_history_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Second commit",
            diff_path="~/.gai/diffs/second.diff",
        )
        assert result is True

        # Verify the file contents
        with open(temp_path) as f:
            content = f.read()
        assert "(1) First commit" in content
        assert "(2) Second commit" in content
        assert "| DIFF: ~/.gai/diffs/second.diff" in content
    finally:
        os.unlink(temp_path)


def test_add_history_entry_nonexistent_file() -> None:
    """Test adding history entry to non-existent file."""
    result = add_history_entry(
        project_file="/nonexistent/file.gp",
        cl_name="test_cl",
        note="Test",
    )
    assert result is False


def test_add_history_entry_no_optional_fields() -> None:
    """Test adding history entry without optional fields."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = add_history_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Manual commit",
        )
        assert result is True

        # Verify the file contents
        with open(temp_path) as f:
            content = f.read()
        assert "(1) Manual commit" in content
        assert "| CHAT:" not in content
        assert "| DIFF:" not in content
    finally:
        os.unlink(temp_path)


def test_save_diff_no_changes(tmp_path: Path) -> None:
    """Test save_diff when there are no changes (returns None)."""
    # Create a temporary directory that's not an hg repo
    result = save_diff("test_cl", str(tmp_path))
    # Should return None since not in an hg repo or no changes
    assert result is None


def test_history_entry_dataclass() -> None:
    """Test HistoryEntry dataclass creation."""
    entry = HistoryEntry(
        number=1,
        note="Test note",
        chat="test.md",
        diff="test.diff",
    )
    assert entry.number == 1
    assert entry.note == "Test note"
    assert entry.chat == "test.md"
    assert entry.diff == "test.diff"


def test_history_entry_dataclass_defaults() -> None:
    """Test HistoryEntry dataclass with default values."""
    entry = HistoryEntry(number=1, note="Test")
    assert entry.number == 1
    assert entry.note == "Test"
    assert entry.chat is None
    assert entry.diff is None
