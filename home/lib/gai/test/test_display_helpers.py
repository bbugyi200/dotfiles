"""Tests for ace/display_helpers.py."""

import tempfile
from dataclasses import dataclass
from pathlib import Path

from ace.display_helpers import (
    format_profile_with_count,
    format_running_claims_aligned,
    get_bug_field,
    get_status_color,
    is_entry_ref_suffix,
    is_suffix_timestamp,
)


@dataclass
class _MockWorkspaceClaim:
    """Mock workspace claim for testing."""

    workspace_num: int
    pid: int
    workflow: str
    cl_name: str | None


def test_format_running_claims_aligned_empty() -> None:
    """Test formatting empty claims list."""
    result = format_running_claims_aligned([])
    assert result == []


def test_format_running_claims_aligned_single() -> None:
    """Test formatting single claim - no padding needed."""
    claims = [_MockWorkspaceClaim(1, 12345, "crs", "my_feature")]
    result = format_running_claims_aligned(claims)
    assert len(result) == 1
    ws_col, pid_col, wf_col, cl_name = result[0]
    assert ws_col == "#1"
    assert pid_col == "12345"
    assert wf_col == "crs"
    assert cl_name == "my_feature"


def test_format_running_claims_aligned_single_no_cl_name() -> None:
    """Test formatting single claim with no cl_name."""
    claims = [_MockWorkspaceClaim(5, 99999, "run", None)]
    result = format_running_claims_aligned(claims)
    assert len(result) == 1
    ws_col, pid_col, wf_col, cl_name = result[0]
    assert ws_col == "#5"
    assert pid_col == "99999"
    assert wf_col == "run"
    assert cl_name is None


def test_format_running_claims_aligned_multiple_same_widths() -> None:
    """Test multiple claims with same column widths - no padding."""
    claims = [
        _MockWorkspaceClaim(1, 10000, "crs", "feat_a"),
        _MockWorkspaceClaim(2, 20000, "run", "feat_b"),
    ]
    result = format_running_claims_aligned(claims)

    assert len(result) == 2
    # Both workspace nums are 1 digit, both workflows are 3 chars
    assert result[0][0] == "#1"
    assert result[0][2] == "crs"
    assert result[1][0] == "#2"
    assert result[1][2] == "run"


def test_format_running_claims_aligned_different_workspace_widths() -> None:
    """Test alignment with different workspace number widths."""
    claims = [
        _MockWorkspaceClaim(1, 12345, "crs", "feat_a"),
        _MockWorkspaceClaim(99, 67890, "crs", "feat_b"),
    ]
    result = format_running_claims_aligned(claims)

    assert len(result) == 2
    # #1 should be padded to #1 (with leading space) to align with #99
    assert result[0][0] == " #1"
    assert result[1][0] == "#99"


def test_format_running_claims_aligned_different_workflow_widths() -> None:
    """Test alignment with different workflow name widths."""
    claims = [
        _MockWorkspaceClaim(1, 12345, "fix-hook", "feat_a"),
        _MockWorkspaceClaim(2, 67890, "crs", "feat_b"),
    ]
    result = format_running_claims_aligned(claims)

    assert len(result) == 2
    # crs should be padded to match fix-hook (8 chars)
    assert result[0][2] == "fix-hook"
    assert result[1][2] == "crs     "
    assert len(result[0][2]) == len(result[1][2])


def test_format_running_claims_aligned_both_columns() -> None:
    """Test alignment when both columns need padding."""
    claims = [
        _MockWorkspaceClaim(1, 12345, "fix-hook", "my_feature"),
        _MockWorkspaceClaim(99, 67890, "crs", "other_feature"),
        _MockWorkspaceClaim(3, 111, "longer_workflow", None),
    ]
    result = format_running_claims_aligned(claims)

    assert len(result) == 3

    # Check workspace column alignment (right-aligned, max width is 2 for "99")
    assert result[0][0] == " #1"
    assert result[1][0] == "#99"
    assert result[2][0] == " #3"

    # Check PID column alignment (right-aligned)
    assert result[0][1] == "12345"
    assert result[1][1] == "67890"
    assert result[2][1] == "  111"  # Padded to align

    # Check workflow column alignment (left-aligned, max width is 15)
    assert result[0][2] == "fix-hook       "
    assert result[1][2] == "crs            "
    assert result[2][2] == "longer_workflow"

    # All workflow columns should be same width
    assert len(result[0][2]) == len(result[1][2]) == len(result[2][2]) == 15

    # Check cl_name preserved
    assert result[0][3] == "my_feature"
    assert result[1][3] == "other_feature"
    assert result[2][3] is None


def test_format_running_claims_aligned_three_digit_workspace() -> None:
    """Test alignment with 3-digit workspace numbers (loop hooks)."""
    claims = [
        _MockWorkspaceClaim(1, 12345, "run", "feat"),
        _MockWorkspaceClaim(100, 67890, "run", "other"),
    ]
    result = format_running_claims_aligned(claims)

    # #1 should be padded to "  #1" to align with "#100"
    assert result[0][0] == "  #1"
    assert result[1][0] == "#100"


def test_format_running_claims_aligned_pid_column() -> None:
    """Test PID column alignment with different PID lengths."""
    claims = [
        _MockWorkspaceClaim(1, 1, "run", "feat_a"),
        _MockWorkspaceClaim(2, 99999, "run", "feat_b"),
    ]
    result = format_running_claims_aligned(claims)

    assert len(result) == 2
    # PIDs should be right-aligned
    assert result[0][1] == "    1"
    assert result[1][1] == "99999"
    assert len(result[0][1]) == len(result[1][1])


# Tests for format_profile_with_count


@dataclass
class _MockMentorStatusLine:
    """Mock mentor status line for testing."""

    profile_name: str
    mentor_name: str = "mock_mentor"


def test_format_profile_with_count_unknown_profile() -> None:
    """Test formatting profile when profile is not found in config."""
    # Use a profile name that doesn't exist in the config
    result = format_profile_with_count("nonexistent_profile_xyz", None)
    # Should return just the profile name without counts
    assert result == "nonexistent_profile_xyz"


def test_format_profile_with_count_no_status_lines() -> None:
    """Test formatting profile with no status lines (0 started)."""
    # Profile won't be found in config (test environment), fallback to name
    result = format_profile_with_count("test_profile", None)
    assert "test_profile" in result


def test_format_profile_with_count_with_status_lines() -> None:
    """Test formatting profile when status lines exist."""
    status_lines = [
        _MockMentorStatusLine(profile_name="test_profile"),
        _MockMentorStatusLine(profile_name="test_profile"),
        _MockMentorStatusLine(profile_name="other_profile"),
    ]
    # Profile won't be found (test env), but function should still work
    result = format_profile_with_count("test_profile", status_lines)
    # Should at least contain the profile name
    assert "test_profile" in result


# Tests for get_bug_field
def test_get_bug_field_found() -> None:
    """Test get_bug_field returns value when BUG field exists."""
    content = """PROJECT: test
BUG: b/12345
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        result = get_bug_field(temp_path)
        assert result == "b/12345"
    finally:
        Path(temp_path).unlink()


def test_get_bug_field_none_value() -> None:
    """Test get_bug_field returns None when BUG value is 'None'."""
    content = """BUG: None
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        result = get_bug_field(temp_path)
        assert result is None
    finally:
        Path(temp_path).unlink()


def test_get_bug_field_not_found() -> None:
    """Test get_bug_field returns None when no BUG field."""
    content = """PROJECT: test
STATUS: Drafted
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        result = get_bug_field(temp_path)
        assert result is None
    finally:
        Path(temp_path).unlink()


def test_get_bug_field_file_not_found() -> None:
    """Test get_bug_field returns None when file doesn't exist."""
    result = get_bug_field("/nonexistent/path/file.gp")
    assert result is None


def test_get_bug_field_empty_value() -> None:
    """Test get_bug_field returns None when BUG value is empty."""
    content = """BUG:
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gp", delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        result = get_bug_field(temp_path)
        assert result is None
    finally:
        Path(temp_path).unlink()


# Tests for get_status_color
def test_get_status_color_wip() -> None:
    """Test get_status_color returns gold for WIP."""
    assert get_status_color("WIP") == "#FFD700"


def test_get_status_color_drafted() -> None:
    """Test get_status_color returns green for Drafted."""
    assert get_status_color("Drafted") == "#87D700"


def test_get_status_color_mailed() -> None:
    """Test get_status_color returns cyan-green for Mailed."""
    assert get_status_color("Mailed") == "#00D787"


def test_get_status_color_submitted() -> None:
    """Test get_status_color returns green for Submitted."""
    assert get_status_color("Submitted") == "#00AF00"


def test_get_status_color_reverted() -> None:
    """Test get_status_color returns gray for Reverted."""
    assert get_status_color("Reverted") == "#808080"


def test_get_status_color_unknown() -> None:
    """Test get_status_color returns white for unknown status."""
    assert get_status_color("Unknown") == "#FFFFFF"


def test_get_status_color_with_workspace_suffix() -> None:
    """Test get_status_color strips workspace suffix before lookup."""
    assert get_status_color("WIP (fig_3)") == "#FFD700"
    assert get_status_color("Drafted (project_99)") == "#87D700"
    assert get_status_color("Mailed (my-proj_1)") == "#00D787"


# Tests for is_suffix_timestamp
def test_is_suffix_timestamp_new_format() -> None:
    """Test is_suffix_timestamp returns True for YYmmdd_HHMMSS format."""
    assert is_suffix_timestamp("241225_120000") is True
    assert is_suffix_timestamp("250101_235959") is True


def test_is_suffix_timestamp_legacy_format() -> None:
    """Test is_suffix_timestamp returns True for 12-digit format."""
    assert is_suffix_timestamp("241225120000") is True
    assert is_suffix_timestamp("250101235959") is True


def test_is_suffix_timestamp_invalid() -> None:
    """Test is_suffix_timestamp returns False for non-timestamp."""
    assert is_suffix_timestamp("error") is False
    assert is_suffix_timestamp("2a") is False
    assert is_suffix_timestamp("12345") is False
    assert is_suffix_timestamp("") is False


# Tests for is_entry_ref_suffix
def test_is_entry_ref_suffix_numeric() -> None:
    """Test is_entry_ref_suffix returns True for numeric IDs."""
    assert is_entry_ref_suffix("1") is True
    assert is_entry_ref_suffix("2") is True
    assert is_entry_ref_suffix("99") is True


def test_is_entry_ref_suffix_with_letter() -> None:
    """Test is_entry_ref_suffix returns True for IDs with letter suffix."""
    assert is_entry_ref_suffix("1a") is True
    assert is_entry_ref_suffix("2b") is True
    assert is_entry_ref_suffix("10z") is True


def test_is_entry_ref_suffix_invalid() -> None:
    """Test is_entry_ref_suffix returns False for invalid formats."""
    assert is_entry_ref_suffix(None) is False
    assert is_entry_ref_suffix("") is False
    assert is_entry_ref_suffix("abc") is False
    assert is_entry_ref_suffix("1A") is False  # uppercase not allowed
    assert is_entry_ref_suffix("a1") is False  # letter must be after number
