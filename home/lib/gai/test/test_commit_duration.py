"""Tests for timestamp/duration formatting and proposal rejection."""

import os
import re
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from commit_utils import (
    add_commit_entry,
    reject_all_new_proposals,
)
from commit_utils.entries import (
    _extract_timestamp_from_chat_path,
    format_chat_line_with_duration,
)


# Tests for _extract_timestamp_from_chat_path
def test_extract_timestamp_from_chat_path_valid() -> None:
    """Test extracting timestamp from a valid chat path."""
    path = "~/.gai/chats/mybranch-crs-251227_143052.md"
    assert _extract_timestamp_from_chat_path(path) == "251227_143052"


def test_extract_timestamp_from_chat_path_with_agent() -> None:
    """Test extracting timestamp from path with agent name."""
    path = "~/.gai/chats/mybranch-crs-editor-251227_143052.md"
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


# Tests for format_chat_line_with_duration
def testformat_chat_line_with_duration_fallback() -> None:
    """Test that invalid paths produce lines without duration."""
    path = "~/.gai/chats/invalid.md"
    result = format_chat_line_with_duration(path)
    assert result == "      | CHAT: ~/.gai/chats/invalid.md\n"
    assert "(" not in result or result.count("(") == 0


def testformat_chat_line_with_duration_no_extension() -> None:
    """Test that paths without .md extension produce lines without duration."""
    path = "~/.gai/chats/test.txt"
    result = format_chat_line_with_duration(path)
    assert result == "      | CHAT: ~/.gai/chats/test.txt\n"


def testformat_chat_line_with_duration_valid() -> None:
    """Test formatting chat line with duration suffix."""
    eastern = ZoneInfo("America/New_York")
    past_time = datetime.now(eastern) - timedelta(minutes=5, seconds=30)
    past_timestamp = past_time.strftime("%y%m%d_%H%M%S")

    path = f"~/.gai/chats/test-run-{past_timestamp}.md"
    result = format_chat_line_with_duration(path)

    # Should contain the path and a duration in parentheses
    assert path in result
    assert "(" in result and ")" in result
    # Should have the 6-space indentation and | CHAT: prefix
    assert result.startswith("      | CHAT: ")
    assert result.endswith(")\n")


def testformat_chat_line_with_duration_short_duration() -> None:
    """Test that short durations are formatted correctly (e.g., '30s')."""
    eastern = ZoneInfo("America/New_York")
    past_time = datetime.now(eastern) - timedelta(seconds=30)
    past_timestamp = past_time.strftime("%y%m%d_%H%M%S")

    # Test with .md path and extract duration part
    path_md = f"~/.gai/chats/test-run-{past_timestamp}.md"
    result_md = format_chat_line_with_duration(path_md)

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
    result = format_chat_line_with_duration(path, end_timestamp=end_timestamp)

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
    result = format_chat_line_with_duration(path, end_timestamp=end_timestamp)

    # Duration should be exactly 20 minutes
    assert "(20m0s)" in result or "(20m)" in result


# Tests for reject_all_new_proposals
def test_reject_all_new_proposals_success() -> None:
    """Test rejecting all new proposals changes suffix from (!:) to (~!:)."""
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
