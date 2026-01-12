"""Tests for ace/display_helpers.py."""

from dataclasses import dataclass

from ace.display_helpers import format_profile_with_count, format_running_claims_aligned


@dataclass
class _MockWorkspaceClaim:
    """Mock workspace claim for testing."""

    workspace_num: int
    workflow: str
    cl_name: str | None


def test_format_running_claims_aligned_empty() -> None:
    """Test formatting empty claims list."""
    result = format_running_claims_aligned([])
    assert result == []


def test_format_running_claims_aligned_single() -> None:
    """Test formatting single claim - no padding needed."""
    claims = [_MockWorkspaceClaim(1, "crs", "my_feature")]
    result = format_running_claims_aligned(claims)
    assert len(result) == 1
    ws_col, wf_col, cl_name = result[0]
    assert ws_col == "#1"
    assert wf_col == "crs"
    assert cl_name == "my_feature"


def test_format_running_claims_aligned_single_no_cl_name() -> None:
    """Test formatting single claim with no cl_name."""
    claims = [_MockWorkspaceClaim(5, "run", None)]
    result = format_running_claims_aligned(claims)
    assert len(result) == 1
    ws_col, wf_col, cl_name = result[0]
    assert ws_col == "#5"
    assert wf_col == "run"
    assert cl_name is None


def test_format_running_claims_aligned_multiple_same_widths() -> None:
    """Test multiple claims with same column widths - no padding."""
    claims = [
        _MockWorkspaceClaim(1, "crs", "feat_a"),
        _MockWorkspaceClaim(2, "run", "feat_b"),
    ]
    result = format_running_claims_aligned(claims)

    assert len(result) == 2
    # Both workspace nums are 1 digit, both workflows are 3 chars
    assert result[0][0] == "#1"
    assert result[0][1] == "crs"
    assert result[1][0] == "#2"
    assert result[1][1] == "run"


def test_format_running_claims_aligned_different_workspace_widths() -> None:
    """Test alignment with different workspace number widths."""
    claims = [
        _MockWorkspaceClaim(1, "crs", "feat_a"),
        _MockWorkspaceClaim(99, "crs", "feat_b"),
    ]
    result = format_running_claims_aligned(claims)

    assert len(result) == 2
    # #1 should be padded to #1 (with leading space) to align with #99
    assert result[0][0] == " #1"
    assert result[1][0] == "#99"


def test_format_running_claims_aligned_different_workflow_widths() -> None:
    """Test alignment with different workflow name widths."""
    claims = [
        _MockWorkspaceClaim(1, "fix-tests", "feat_a"),
        _MockWorkspaceClaim(2, "crs", "feat_b"),
    ]
    result = format_running_claims_aligned(claims)

    assert len(result) == 2
    # crs should be padded to match fix-tests (9 chars)
    assert result[0][1] == "fix-tests"
    assert result[1][1] == "crs      "
    assert len(result[0][1]) == len(result[1][1])


def test_format_running_claims_aligned_both_columns() -> None:
    """Test alignment when both columns need padding."""
    claims = [
        _MockWorkspaceClaim(1, "fix-tests", "my_feature"),
        _MockWorkspaceClaim(99, "crs", "other_feature"),
        _MockWorkspaceClaim(3, "longer_workflow", None),
    ]
    result = format_running_claims_aligned(claims)

    assert len(result) == 3

    # Check workspace column alignment (right-aligned, max width is 2 for "99")
    assert result[0][0] == " #1"
    assert result[1][0] == "#99"
    assert result[2][0] == " #3"

    # Check workflow column alignment (left-aligned, max width is 15)
    assert result[0][1] == "fix-tests      "
    assert result[1][1] == "crs            "
    assert result[2][1] == "longer_workflow"

    # All workflow columns should be same width
    assert len(result[0][1]) == len(result[1][1]) == len(result[2][1]) == 15

    # Check cl_name preserved
    assert result[0][2] == "my_feature"
    assert result[1][2] == "other_feature"
    assert result[2][2] is None


def test_format_running_claims_aligned_three_digit_workspace() -> None:
    """Test alignment with 3-digit workspace numbers (loop hooks)."""
    claims = [
        _MockWorkspaceClaim(1, "run", "feat"),
        _MockWorkspaceClaim(100, "run", "other"),
    ]
    result = format_running_claims_aligned(claims)

    # #1 should be padded to "  #1" to align with "#100"
    assert result[0][0] == "  #1"
    assert result[1][0] == "#100"


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
