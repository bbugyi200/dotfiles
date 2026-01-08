"""Tests for HISTORY field parsing and history_utils module."""

import os
import tempfile
from pathlib import Path

from ace.changespec import CommitEntry
from ace.changespec.parser import _build_commit_entry, _parse_changespec_from_lines
from commit_utils import (
    _extract_timestamp_from_chat_path,
    _format_chat_line_with_duration,
    _get_last_regular_commit_number,
    _get_next_proposal_letter,
    add_commit_entry,
    add_proposed_commit_entry,
    get_next_commit_number,
    save_diff,
)
from gai_utils import ensure_gai_directory, generate_timestamp, get_gai_directory


# Tests for _build_commit_entry
def test_build_commit_entry_all_fields() -> None:
    """Test building CommitEntry with all fields."""
    entry_dict: dict[str, str | int | None] = {
        "number": 1,
        "note": "Initial Commit",
        "chat": "~/.gai/chats/test.md",
        "diff": "~/.gai/diffs/test.diff",
    }
    entry = _build_commit_entry(entry_dict)
    assert entry.number == 1
    assert entry.note == "Initial Commit"
    assert entry.chat == "~/.gai/chats/test.md"
    assert entry.diff == "~/.gai/diffs/test.diff"


def test_build_commit_entry_missing_optional_fields() -> None:
    """Test building CommitEntry with only required fields."""
    entry_dict: dict[str, str | int | None] = {
        "number": 2,
        "note": "Test commit",
        "chat": None,
        "diff": None,
    }
    entry = _build_commit_entry(entry_dict)
    assert entry.number == 2
    assert entry.note == "Test commit"
    assert entry.chat is None
    assert entry.diff is None


def test_build_commit_entry_defaults() -> None:
    """Test building CommitEntry with empty dict (all defaults)."""
    entry_dict: dict[str, str | int | None] = {}
    entry = _build_commit_entry(entry_dict)
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
        "COMMITS:\n",
        "  (1) Initial Commit\n",
        "      | CHAT: ~/.gai/chats/test-251221130813.md\n",
        "      | DIFF: ~/.gai/diffs/test_251221130813.diff\n",
        "  (2) Added feature\n",
        "      | DIFF: ~/.gai/diffs/test_251221140000.diff\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.name == "test_cl"
    assert changespec.commits is not None
    assert len(changespec.commits) == 2
    # Check first entry
    assert changespec.commits[0].number == 1
    assert changespec.commits[0].note == "Initial Commit"
    assert changespec.commits[0].chat == "~/.gai/chats/test-251221130813.md"
    assert changespec.commits[0].diff == "~/.gai/diffs/test_251221130813.diff"
    # Check second entry
    assert changespec.commits[1].number == 2
    assert changespec.commits[1].note == "Added feature"
    assert changespec.commits[1].chat is None
    assert changespec.commits[1].diff == "~/.gai/diffs/test_251221140000.diff"


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
    assert changespec.commits is None


def test_parse_changespec_history_without_optional_fields() -> None:
    """Test parsing HISTORY entry without CHAT field."""
    lines = [
        "## ChangeSpec\n",
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) Manual commit\n",
        "      | DIFF: ~/.gai/diffs/test.diff\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.commits is not None
    assert len(changespec.commits) == 1
    assert changespec.commits[0].number == 1
    assert changespec.commits[0].note == "Manual commit"
    assert changespec.commits[0].chat is None
    assert changespec.commits[0].diff == "~/.gai/diffs/test.diff"


# Tests for history_utils functions
def test_get_diffs_directory() -> None:
    """Test getting diffs directory path."""
    expected = os.path.expanduser("~/.gai/diffs")
    assert get_gai_directory("diffs") == expected


def test_ensure_diffs_directory() -> None:
    """Test that ensure_diffs_directory creates the directory."""
    # This should not raise any errors
    ensure_gai_directory("diffs")
    diffs_dir = get_gai_directory("diffs")
    assert os.path.isdir(diffs_dir)


def test_generate_timestamp_format() -> None:
    """Test that timestamp has correct format."""
    timestamp = generate_timestamp()
    # Should be 13 characters: YYmmdd_HHMMSS
    assert len(timestamp) == 13
    # Should have underscore at position 6
    assert timestamp[6] == "_"
    # Date and time parts should be digits
    assert timestamp[:6].isdigit()
    assert timestamp[7:].isdigit()


def test_get_next_commit_number_no_history() -> None:
    """Test getting next history number when no history exists."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
    ]
    next_num = get_next_commit_number(lines, "test_cl")
    assert next_num == 1


def test_get_next_commit_number_with_history() -> None:
    """Test getting next history number when history exists."""
    lines = [
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "      | DIFF: test.diff\n",
        "  (2) Second commit\n",
        "      | DIFF: test2.diff\n",
    ]
    next_num = get_next_commit_number(lines, "test_cl")
    assert next_num == 3


def test_get_next_commit_number_wrong_changespec() -> None:
    """Test getting next history number for non-existent changespec."""
    lines = [
        "NAME: other_cl\n",
        "DESCRIPTION:\n",
        "  Test\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
    ]
    next_num = get_next_commit_number(lines, "test_cl")
    assert next_num == 1


def test_add_commit_entry_new_history_field() -> None:
    """Test adding history entry when HISTORY field doesn't exist."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("DESCRIPTION:\n")
        f.write("  Test description\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = add_commit_entry(
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
        assert "COMMITS:" in content
        assert "  (1) Initial Commit" in content
        assert "      | CHAT: ~/.gai/chats/test.md" in content
        assert "      | DIFF: ~/.gai/diffs/test.diff" in content
    finally:
        os.unlink(temp_path)


def test_add_commit_entry_existing_history_field() -> None:
    """Test adding history entry when HISTORY field already exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("DESCRIPTION:\n")
        f.write("  Test description\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("      | DIFF: ~/.gai/diffs/first.diff\n")
        temp_path = f.name

    try:
        result = add_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Second commit",
            diff_path="~/.gai/diffs/second.diff",
        )
        assert result is True

        # Verify the file contents
        with open(temp_path) as f:
            content = f.read()
        assert "  (1) First commit" in content
        assert "  (2) Second commit" in content
        assert "      | DIFF: ~/.gai/diffs/second.diff" in content
    finally:
        os.unlink(temp_path)


def test_add_commit_entry_nonexistent_file() -> None:
    """Test adding history entry to non-existent file."""
    result = add_commit_entry(
        project_file="/nonexistent/file.gp",
        cl_name="test_cl",
        note="Test",
    )
    assert result is False


def test_add_commit_entry_no_optional_fields() -> None:
    """Test adding history entry without optional fields."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = add_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Manual commit",
        )
        assert result is True

        # Verify the file contents
        with open(temp_path) as f:
            content = f.read()
        assert "  (1) Manual commit" in content
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
    """Test CommitEntry dataclass creation."""
    entry = CommitEntry(
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
    """Test CommitEntry dataclass with default values."""
    entry = CommitEntry(number=1, note="Test")
    assert entry.number == 1
    assert entry.note == "Test"
    assert entry.chat is None
    assert entry.diff is None


# Tests for CommitEntry proposal properties
def test_history_entry_is_proposed_false() -> None:
    """Test is_proposed returns False for regular entries."""
    entry = CommitEntry(number=1, note="Test")
    assert entry.is_proposed is False


def test_history_entry_is_proposed_true() -> None:
    """Test is_proposed returns True for proposed entries."""
    entry = CommitEntry(number=2, note="Test", proposal_letter="a")
    assert entry.is_proposed is True


def test_history_entry_display_number_regular() -> None:
    """Test display_number for regular entries."""
    entry = CommitEntry(number=3, note="Test")
    assert entry.display_number == "3"


def test_history_entry_display_number_proposed() -> None:
    """Test display_number for proposed entries."""
    entry = CommitEntry(number=2, note="Test", proposal_letter="b")
    assert entry.display_number == "2b"


# Tests for _get_last_regular_commit_number
def test_get_last_regular_commit_number_no_history() -> None:
    """Test getting last regular number when no history exists."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
    ]
    last_num = _get_last_regular_commit_number(lines, "test_cl")
    assert last_num == 0


def test_get_last_regular_commit_number_with_history() -> None:
    """Test getting last regular number with existing history."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "  (2) Second commit\n",
    ]
    last_num = _get_last_regular_commit_number(lines, "test_cl")
    assert last_num == 2


def test_get_last_regular_commit_number_skips_proposals() -> None:
    """Test that proposed entries are skipped when counting."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "  (2) Second commit\n",
        "  (2a) Proposed change\n",
        "  (2b) Another proposal\n",
    ]
    last_num = _get_last_regular_commit_number(lines, "test_cl")
    assert last_num == 2


# Tests for _get_next_proposal_letter
def test_get_next_proposal_letter_no_proposals() -> None:
    """Test getting first proposal letter when none exist."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) First commit\n",
        "  (2) Second commit\n",
    ]
    letter = _get_next_proposal_letter(lines, "test_cl", 2)
    assert letter == "a"


def test_get_next_proposal_letter_with_existing() -> None:
    """Test getting next proposal letter when some exist."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (2) Second commit\n",
        "  (2a) First proposal\n",
        "  (2b) Second proposal\n",
    ]
    letter = _get_next_proposal_letter(lines, "test_cl", 2)
    assert letter == "c"


def test_get_next_proposal_letter_fills_gap() -> None:
    """Test that next letter fills gaps."""
    lines = [
        "NAME: test_cl\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (2) Second commit\n",
        "  (2a) First proposal\n",
        "  (2c) Third proposal\n",  # 'b' is missing
    ]
    letter = _get_next_proposal_letter(lines, "test_cl", 2)
    assert letter == "b"


# Tests for add_proposed_commit_entry
def test_add_proposed_commit_entry_new_history() -> None:
    """Test adding proposed entry when no HISTORY exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        success, entry_id = add_proposed_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Proposed change",
            diff_path="~/.gai/diffs/test.diff",
        )
        assert success is True
        assert entry_id == "0a"  # No prior entries, base is 0

        with open(temp_path) as f:
            content = f.read()
        assert "COMMITS:" in content
        assert "(0a) Proposed change" in content
        assert "| DIFF: ~/.gai/diffs/test.diff" in content
    finally:
        os.unlink(temp_path)


def test_add_proposed_commit_entry_existing_history() -> None:
    """Test adding proposed entry to existing HISTORY."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) First commit\n")
        f.write("      | DIFF: ~/.gai/diffs/first.diff\n")
        temp_path = f.name

    try:
        success, entry_id = add_proposed_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Proposed change",
            diff_path="~/.gai/diffs/proposed.diff",
            chat_path="~/.gai/chats/proposed.md",
        )
        assert success is True
        assert entry_id == "1a"

        with open(temp_path) as f:
            content = f.read()
        assert "(1) First commit" in content
        assert "(1a) Proposed change" in content
        assert "| CHAT: ~/.gai/chats/proposed.md" in content
        assert "| DIFF: ~/.gai/diffs/proposed.diff" in content
    finally:
        os.unlink(temp_path)


def test_add_proposed_commit_entry_multiple_proposals() -> None:
    """Test adding multiple proposed entries."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (2) Second commit\n")
        f.write("  (2a) First proposal\n")
        temp_path = f.name

    try:
        success, entry_id = add_proposed_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Second proposal",
            diff_path="~/.gai/diffs/second.diff",
        )
        assert success is True
        assert entry_id == "2b"

        with open(temp_path) as f:
            content = f.read()
        assert "(2) Second commit" in content
        assert "(2a) First proposal" in content
        assert "(2b) Second proposal" in content
    finally:
        os.unlink(temp_path)


def test_add_proposed_commit_entry_nonexistent_file() -> None:
    """Test adding proposed entry to non-existent file."""
    success, entry_id = add_proposed_commit_entry(
        project_file="/nonexistent/file.gp",
        cl_name="test_cl",
        note="Test",
    )
    assert success is False
    assert entry_id is None


# Tests for parsing proposed HISTORY entries
def test_parse_changespec_with_proposed_entries() -> None:
    """Test parsing ChangeSpec with proposed HISTORY entries."""
    lines = [
        "## ChangeSpec\n",
        "NAME: test_cl\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: Drafted\n",
        "COMMITS:\n",
        "  (1) Initial Commit\n",
        "      | DIFF: ~/.gai/diffs/first.diff\n",
        "  (2) Second commit\n",
        "      | DIFF: ~/.gai/diffs/second.diff\n",
        "  (2a) First proposal\n",
        "      | DIFF: ~/.gai/diffs/proposal_a.diff\n",
        "  (2b) Second proposal\n",
        "      | CHAT: ~/.gai/chats/proposal_b.md\n",
        "      | DIFF: ~/.gai/diffs/proposal_b.diff\n",
        "\n",
    ]
    changespec, _ = _parse_changespec_from_lines(lines, 0, "/test/file.gp")
    assert changespec is not None
    assert changespec.commits is not None
    assert len(changespec.commits) == 4

    # Regular entries
    assert changespec.commits[0].number == 1
    assert changespec.commits[0].is_proposed is False
    assert changespec.commits[0].display_number == "1"

    assert changespec.commits[1].number == 2
    assert changespec.commits[1].is_proposed is False
    assert changespec.commits[1].display_number == "2"

    # Proposed entries
    assert changespec.commits[2].number == 2
    assert changespec.commits[2].proposal_letter == "a"
    assert changespec.commits[2].is_proposed is True
    assert changespec.commits[2].display_number == "2a"
    assert changespec.commits[2].note == "First proposal"

    assert changespec.commits[3].number == 2
    assert changespec.commits[3].proposal_letter == "b"
    assert changespec.commits[3].is_proposed is True
    assert changespec.commits[3].display_number == "2b"
    assert changespec.commits[3].chat == "~/.gai/chats/proposal_b.md"


# Tests for _extract_timestamp_from_chat_path
def test_extract_timestamp_from_chat_path_valid() -> None:
    """Test extracting timestamp from a valid chat path."""
    path = "~/.gai/chats/mybranch-fix_tests-251227_143052.md"
    assert _extract_timestamp_from_chat_path(path) == "251227_143052"


def test_extract_timestamp_from_chat_path_with_agent() -> None:
    """Test extracting timestamp from path with agent name."""
    path = "~/.gai/chats/mybranch-fix_tests-editor-251227_143052.md"
    assert _extract_timestamp_from_chat_path(path) == "251227_143052"


def test_extract_timestamp_from_chat_path_no_extension() -> None:
    """Test that None is returned for paths without .md extension."""
    assert _extract_timestamp_from_chat_path("~/.gai/chats/test.txt") is None
    assert _extract_timestamp_from_chat_path("") is None


def test_extract_timestamp_from_chat_path_too_short() -> None:
    """Test that None is returned for filenames too short to contain timestamp."""
    assert _extract_timestamp_from_chat_path("~/.gai/chats/short.md") is None


def test_extract_timestamp_from_chat_path_invalid_timestamp() -> None:
    """Test that None is returned for invalid timestamp format."""
    # Missing underscore
    assert (
        _extract_timestamp_from_chat_path("~/.gai/chats/test-2512271430521.md") is None
    )
    # Non-digit characters
    assert (
        _extract_timestamp_from_chat_path("~/.gai/chats/test-25122a_143052.md") is None
    )


# Tests for _format_chat_line_with_duration
def test_format_chat_line_with_duration_fallback() -> None:
    """Test that invalid paths produce lines without duration."""
    path = "~/.gai/chats/invalid.md"
    result = _format_chat_line_with_duration(path)
    assert result == "      | CHAT: ~/.gai/chats/invalid.md\n"
    assert "(" not in result or result.count("(") == 0


def test_format_chat_line_with_duration_no_extension() -> None:
    """Test that paths without .md extension produce lines without duration."""
    path = "~/.gai/chats/test.txt"
    result = _format_chat_line_with_duration(path)
    assert result == "      | CHAT: ~/.gai/chats/test.txt\n"


def test_format_chat_line_with_duration_valid() -> None:
    """Test formatting chat line with duration suffix."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    eastern = ZoneInfo("America/New_York")
    past_time = datetime.now(eastern) - timedelta(minutes=5, seconds=30)
    past_timestamp = past_time.strftime("%y%m%d_%H%M%S")

    path = f"~/.gai/chats/test-run-{past_timestamp}.md"
    result = _format_chat_line_with_duration(path)

    # Should contain the path and a duration in parentheses
    assert path in result
    assert "(" in result and ")" in result
    # Should have the 6-space indentation and | CHAT: prefix
    assert result.startswith("      | CHAT: ")
    assert result.endswith(")\n")


def test_format_chat_line_with_duration_short_duration() -> None:
    """Test that short durations are formatted correctly (e.g., '30s')."""
    import re
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    eastern = ZoneInfo("America/New_York")
    past_time = datetime.now(eastern) - timedelta(seconds=30)
    past_timestamp = past_time.strftime("%y%m%d_%H%M%S")

    # Test with .md path and extract duration part
    path_md = f"~/.gai/chats/test-run-{past_timestamp}.md"
    result_md = _format_chat_line_with_duration(path_md)

    # Extract duration from the result (e.g., "(30s)" or "(45s)")
    duration_match = re.search(r"\((\d+s)\)$", result_md.strip())
    assert duration_match is not None, f"Expected seconds-only duration in: {result_md}"
    duration = duration_match.group(1)
    # Should NOT contain hours or minutes for a ~30-second duration
    assert "h" not in duration
    assert "m" not in duration


# Tests for add_commit_entry with duration suffix
def test_add_commit_entry_with_chat_duration() -> None:
    """Test that add_commit_entry includes duration suffix for chat path."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    # Create a chat path with a recent timestamp
    eastern = ZoneInfo("America/New_York")
    past_time = datetime.now(eastern) - timedelta(minutes=2)
    past_timestamp = past_time.strftime("%y%m%d_%H%M%S")
    chat_path = f"~/.gai/chats/test-run-{past_timestamp}.md"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        temp_path = f.name

    try:
        result = add_commit_entry(
            project_file=temp_path,
            cl_name="test_cl",
            note="Test commit",
            chat_path=chat_path,
        )
        assert result is True

        with open(temp_path) as f:
            content = f.read()

        # Should have CHAT line with duration
        assert f"| CHAT: {chat_path}" in content
        assert "(" in content and ")" in content
        # Check for duration format (should be around 2m)
        assert "m" in content or "s" in content
    finally:
        os.unlink(temp_path)


def test_format_chat_line_with_end_timestamp() -> None:
    """Test that end_timestamp is used when provided instead of current time."""
    # Create a chat path with a timestamp from 10 minutes ago
    start_timestamp = "250101_120000"  # Jan 1, 2025, 12:00:00
    end_timestamp = "250101_120530"  # Jan 1, 2025, 12:05:30 (5 min 30 sec later)

    path = f"~/.gai/chats/test-run-{start_timestamp}.md"
    result = _format_chat_line_with_duration(path, end_timestamp=end_timestamp)

    # Should contain the path and a duration in parentheses
    assert path in result
    assert "(5m30s)" in result
    # Should have the 6-space indentation and | CHAT: prefix
    assert result.startswith("      | CHAT: ")


def test_format_chat_line_with_end_timestamp_exact() -> None:
    """Test end_timestamp calculates exact duration regardless of current time."""
    # These timestamps are fixed, so the result should be deterministic
    start_timestamp = "250615_143052"  # June 15, 2025, 14:30:52
    end_timestamp = "250615_145052"  # June 15, 2025, 14:50:52 (20 min later)

    path = f"~/.gai/chats/test-run-{start_timestamp}.md"
    result = _format_chat_line_with_duration(path, end_timestamp=end_timestamp)

    # Duration should be exactly 20 minutes
    assert "(20m0s)" in result or "(20m)" in result


# Tests for reject_all_new_proposals
def test_reject_all_new_proposals_success() -> None:
    """Test rejecting all new proposals changes suffix from (!:) to (~!:)."""
    from commit_utils import reject_all_new_proposals

    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) Initial commit\n")
        f.write("  (1a) Proposal one - (!: NEW PROPOSAL)\n")
        f.write("  (1b) Proposal two - (!: NEW PROPOSAL)\n")
        temp_path = f.name

    try:
        result = reject_all_new_proposals(temp_path, "test_cl")
        assert result == 2

        # Verify the file was updated
        with open(temp_path, encoding="utf-8") as f:
            content = f.read()
        assert "(~!: NEW PROPOSAL)" in content
        assert "(!: NEW PROPOSAL)" not in content
    finally:
        os.unlink(temp_path)


def test_reject_all_new_proposals_no_proposals() -> None:
    """Test that returning 0 when no new proposals exist."""
    from commit_utils import reject_all_new_proposals

    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1) Initial commit\n")
        temp_path = f.name

    try:
        result = reject_all_new_proposals(temp_path, "test_cl")
        assert result == 0
    finally:
        os.unlink(temp_path)


def test_reject_all_new_proposals_wrong_cl_name() -> None:
    """Test that returning 0 when CL name doesn't match."""
    from commit_utils import reject_all_new_proposals

    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write("NAME: test_cl\n")
        f.write("STATUS: Drafted\n")
        f.write("COMMITS:\n")
        f.write("  (1a) Proposal - (!: NEW PROPOSAL)\n")
        temp_path = f.name

    try:
        result = reject_all_new_proposals(temp_path, "wrong_cl")
        assert result == 0
    finally:
        os.unlink(temp_path)
