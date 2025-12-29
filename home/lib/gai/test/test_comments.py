"""Tests for comments module utilities."""

import tempfile
from pathlib import Path

from ace.changespec import ChangeSpec, CommentEntry
from ace.comments import (
    CRS_STALE_THRESHOLD_SECONDS,
    comment_needs_crs,
    generate_comments_timestamp,
    get_comments_file_path,
    is_comments_suffix_stale,
    is_timestamp_suffix,
)
from ace.display import _get_status_color, _is_suffix_timestamp
from gai_utils import get_gai_directory


def test_generate_comments_timestamp_format() -> None:
    """Test that generate_comments_timestamp returns correct format."""
    timestamp = generate_comments_timestamp()

    # Should be YYmmdd_HHMMSS format (13 chars with underscore at position 6)
    assert len(timestamp) == 13
    assert timestamp[6] == "_"
    # First 6 chars should be digits (YYmmdd)
    assert timestamp[:6].isdigit()
    # Last 6 chars should be digits (HHMMSS)
    assert timestamp[7:].isdigit()


def test_get_comments_directory() -> None:
    """Test that get_gai_directory('comments') returns correct path."""
    comments_dir = get_gai_directory("comments")

    # Should be ~/.gai/comments/
    assert comments_dir.endswith(".gai/comments")
    assert "~" not in comments_dir  # Should be expanded


def test_get_comments_file_path() -> None:
    """Test that get_comments_file_path builds correct path."""
    file_path = get_comments_file_path("my_feature", "reviewer", "241226_120000")

    # Should contain the name, reviewer, and timestamp
    assert "my_feature" in file_path
    assert "reviewer" in file_path
    assert "241226_120000" in file_path
    assert file_path.endswith(".json")


def test_is_timestamp_suffix_valid_new_format() -> None:
    """Test is_timestamp_suffix with new format YYmmdd_HHMMSS."""
    assert is_timestamp_suffix("241226_120000") is True
    assert is_timestamp_suffix("250101_000000") is True  # Jan 1, 2025


def test_is_timestamp_suffix_invalid() -> None:
    """Test is_timestamp_suffix with invalid formats."""
    assert is_timestamp_suffix("!") is False
    assert is_timestamp_suffix("2a") is False
    assert is_timestamp_suffix("ZOMBIE") is False
    assert is_timestamp_suffix("12345") is False


def test_is_comments_suffix_stale_fresh() -> None:
    """Test is_comments_suffix_stale returns False for fresh timestamp."""
    # Use a timestamp from now - should not be stale
    fresh_timestamp = generate_comments_timestamp()
    assert is_comments_suffix_stale(fresh_timestamp) is False


def test_is_comments_suffix_stale_non_timestamp() -> None:
    """Test is_comments_suffix_stale returns False for non-timestamp suffix."""
    # Non-timestamp suffixes are not considered stale
    assert is_comments_suffix_stale("!") is False
    assert is_comments_suffix_stale("2a") is False


def test_comment_needs_crs_no_suffix() -> None:
    """Test comment_needs_crs returns True when no suffix."""
    entry = CommentEntry(
        reviewer="reviewer",
        file_path="~/.gai/comments/test-reviewer-241226_120000.json",
        suffix=None,
    )
    assert comment_needs_crs(entry) is True


def test_comment_needs_crs_with_suffix() -> None:
    """Test comment_needs_crs returns False when suffix present."""
    # Timestamp suffix (running)
    entry1 = CommentEntry(
        reviewer="reviewer",
        file_path="~/.gai/comments/test-reviewer-241226_120000.json",
        suffix="241226_130000",
    )
    assert comment_needs_crs(entry1) is False

    # Proposal ID suffix (completed)
    entry2 = CommentEntry(
        reviewer="reviewer",
        file_path="~/.gai/comments/test-reviewer-241226_120000.json",
        suffix="2a",
    )
    assert comment_needs_crs(entry2) is False

    # Failed suffix
    entry3 = CommentEntry(
        reviewer="reviewer",
        file_path="~/.gai/comments/test-reviewer-241226_120000.json",
        suffix="!",
    )
    assert comment_needs_crs(entry3) is False


def test_crs_stale_threshold_is_two_hours() -> None:
    """Test that CRS_STALE_THRESHOLD_SECONDS is 2 hours."""
    assert CRS_STALE_THRESHOLD_SECONDS == 7200  # 2 hours in seconds


def test_comment_entry_parsing() -> None:
    """Test CommentEntry dataclass creation."""
    entry = CommentEntry(
        reviewer="johndoe",
        file_path="/path/to/comments.json",
        suffix="241226_120000",
    )
    assert entry.reviewer == "johndoe"
    assert entry.file_path == "/path/to/comments.json"
    assert entry.suffix == "241226_120000"


def test_comment_entry_no_suffix() -> None:
    """Test CommentEntry dataclass with no suffix."""
    entry = CommentEntry(
        reviewer="reviewer",
        file_path="/path/to/comments.json",
    )
    assert entry.reviewer == "reviewer"
    assert entry.file_path == "/path/to/comments.json"
    assert entry.suffix is None


def test_is_timestamp_suffix_none() -> None:
    """Test is_timestamp_suffix with None."""
    assert is_timestamp_suffix(None) is False


def test_is_timestamp_suffix_zombie() -> None:
    """Test is_timestamp_suffix with ZOMBIE suffix."""
    assert is_timestamp_suffix("ZOMBIE") is False


def test_is_comments_suffix_stale_none() -> None:
    """Test is_comments_suffix_stale with None suffix."""
    assert is_comments_suffix_stale(None) is False


def test_get_available_workflows_with_suffix() -> None:
    """Test that COMMENTS entry with suffix does not return crs workflow."""
    from ace.operations import get_available_workflows

    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent="None",
        cl="123",
        test_targets=None,
        status="Mailed",
        file_path="/tmp/test.md",
        line_number=1,
        kickstart=None,
        comments=[
            CommentEntry(
                reviewer="reviewer",
                file_path="~/.gai/comments/test-reviewer-241226_120000.json",
                suffix="2a",  # Has suffix = CRS not available
            )
        ],
    )
    workflows = get_available_workflows(cs)
    assert "crs" not in workflows


def test_changespec_with_multiple_comments() -> None:
    """Test ChangeSpec with multiple comment entries."""
    from ace.changespec import ChangeSpec

    cs = ChangeSpec(
        name="Test",
        description="Test",
        parent=None,
        cl="123",
        status="Mailed",
        test_targets=None,
        kickstart=None,
        file_path="/tmp/test.md",
        line_number=1,
        comments=[
            CommentEntry(
                reviewer="reviewer1",
                file_path="~/.gai/comments/test-reviewer1-241226_120000.json",
            ),
            CommentEntry(
                reviewer="reviewer2",
                file_path="~/.gai/comments/test-reviewer2-241226_130000.json",
                suffix="!",
            ),
        ],
    )
    assert cs.comments is not None
    assert len(cs.comments) == 2
    assert cs.comments[0].reviewer == "reviewer1"
    assert cs.comments[0].suffix is None
    assert cs.comments[1].reviewer == "reviewer2"
    assert cs.comments[1].suffix == "!"


# --- Tests for display module helpers ---


def test_display_is_suffix_timestamp_new_format() -> None:
    """Test _is_suffix_timestamp with new format YYmmdd_HHMMSS."""
    assert _is_suffix_timestamp("241226_120000") is True


def test_display_is_suffix_timestamp_legacy_format() -> None:
    """Test _is_suffix_timestamp with legacy format YYmmddHHMMSS."""
    assert _is_suffix_timestamp("241226120000") is True


def test_display_is_suffix_timestamp_invalid() -> None:
    """Test _is_suffix_timestamp with invalid formats."""
    assert _is_suffix_timestamp("!") is False
    assert _is_suffix_timestamp("2a") is False
    assert _is_suffix_timestamp("ZOMBIE") is False


def test_get_status_color_drafted() -> None:
    """Test _get_status_color for Drafted status."""
    assert _get_status_color("Drafted") == "#87D700"


def test_get_status_color_submitted() -> None:
    """Test _get_status_color for Submitted status."""
    assert _get_status_color("Submitted") == "#00AF00"


def test_get_status_color_reverted() -> None:
    """Test _get_status_color for Reverted status."""
    assert _get_status_color("Reverted") == "#808080"


def test_get_status_color_with_workspace_suffix() -> None:
    """Test _get_status_color strips workspace suffix before lookup."""
    # Status with workspace suffix (e.g., "Drafted (fig_3)")
    assert _get_status_color("Drafted (fig_3)") == "#87D700"
    assert _get_status_color("Mailed (project_1)") == "#00D787"


def test_comments_entry_in_changespec_parsing() -> None:
    """Test that COMMENTS entries are parsed from project file."""
    from ace.changespec import parse_project_file

    # Create a temporary project file with COMMENTS field
    project_content = """NAME: test_feature
DESCRIPTION:
  Test feature description
STATUS: Mailed
COMMENTS:
  [reviewer] ~/.gai/comments/test_feature-reviewer-241226_120000.json
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(project_content)
        project_file = f.name

    try:
        changespecs = parse_project_file(project_file)
        assert len(changespecs) == 1
        cs = changespecs[0]
        assert cs.comments is not None
        assert len(cs.comments) == 1
        assert cs.comments[0].reviewer == "reviewer"
        assert "test_feature" in cs.comments[0].file_path
    finally:
        Path(project_file).unlink()


def test_comments_entry_with_suffix_parsing() -> None:
    """Test that COMMENTS entries with suffix are parsed correctly."""
    from ace.changespec import parse_project_file

    project_content = """NAME: test_feature
DESCRIPTION:
  Test feature description
STATUS: Mailed
COMMENTS:
  [reviewer] ~/.gai/comments/test_feature-reviewer-241226_120000.json - (2a)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(project_content)
        project_file = f.name

    try:
        changespecs = parse_project_file(project_file)
        assert len(changespecs) == 1
        cs = changespecs[0]
        assert cs.comments is not None
        assert len(cs.comments) == 1
        assert cs.comments[0].reviewer == "reviewer"
        assert cs.comments[0].suffix == "2a"
    finally:
        Path(project_file).unlink()
