"""Tests for agent loader timestamp parsing functions."""

from ace.tui.models.agent_loader import (
    _extract_timestamp_from_workflow,
    _extract_timestamp_str_from_suffix,
    _parse_timestamp_from_suffix,
)

# --- Timestamp Parsing Tests ---


def test_parse_timestamp_from_suffix_new_format() -> None:
    """Test parsing timestamp from new format: agent-PID-timestamp."""
    suffix = "fix_hook-12345-251230_151429"
    result = _parse_timestamp_from_suffix(suffix)
    assert result is not None
    assert result.year == 2025
    assert result.month == 12
    assert result.day == 30
    assert result.hour == 15
    assert result.minute == 14
    assert result.second == 29


def test_parse_timestamp_from_suffix_legacy_format() -> None:
    """Test parsing timestamp from legacy format: agent-timestamp."""
    suffix = "fix_hook-251230_151429"
    result = _parse_timestamp_from_suffix(suffix)
    assert result is not None
    assert result.year == 2025
    assert result.month == 12
    assert result.day == 30


def test_parse_timestamp_from_suffix_bare_timestamp() -> None:
    """Test parsing bare timestamp format."""
    suffix = "251230_151429"
    result = _parse_timestamp_from_suffix(suffix)
    assert result is not None
    assert result.year == 2025
    assert result.month == 12


def test_parse_timestamp_from_suffix_crs_format() -> None:
    """Test parsing CRS format: crs-timestamp."""
    suffix = "crs-251230_151429"
    result = _parse_timestamp_from_suffix(suffix)
    assert result is not None
    assert result.year == 2025


def test_parse_timestamp_from_suffix_none() -> None:
    """Test parsing None suffix."""
    result = _parse_timestamp_from_suffix(None)
    assert result is None


def test_parse_timestamp_from_suffix_invalid() -> None:
    """Test parsing invalid suffix."""
    result = _parse_timestamp_from_suffix("invalid")
    assert result is None


def test_parse_timestamp_from_suffix_invalid_timestamp() -> None:
    """Test parsing suffix with invalid timestamp format."""
    result = _parse_timestamp_from_suffix("fix_hook-12345-invalid")
    assert result is None


# --- Timestamp Extraction Helper Tests ---


def test_extract_timestamp_str_from_suffix_new_format() -> None:
    """Test extracting timestamp from new format: agent-PID-timestamp."""
    result = _extract_timestamp_str_from_suffix("mentor_complete-1855023-260112_134051")
    assert result == "260112_134051"


def test_extract_timestamp_str_from_suffix_fix_hook() -> None:
    """Test extracting timestamp from fix-hook suffix."""
    result = _extract_timestamp_str_from_suffix("fix_hook-12345-251230_151429")
    assert result == "251230_151429"


def test_extract_timestamp_str_from_suffix_crs() -> None:
    """Test extracting timestamp from CRS suffix."""
    result = _extract_timestamp_str_from_suffix("crs-12345-251230_151429")
    assert result == "251230_151429"


def test_extract_timestamp_str_from_suffix_none() -> None:
    """Test extracting timestamp from None suffix."""
    result = _extract_timestamp_str_from_suffix(None)
    assert result is None


def test_extract_timestamp_str_from_suffix_no_dash() -> None:
    """Test extracting timestamp from suffix without dashes."""
    result = _extract_timestamp_str_from_suffix("nodashes")
    assert result is None


def test_extract_timestamp_str_from_suffix_invalid_format() -> None:
    """Test extracting timestamp from suffix with invalid format."""
    result = _extract_timestamp_str_from_suffix("fix_hook-12345-invalid")
    assert result is None


def test_extract_timestamp_from_workflow_mentor() -> None:
    """Test extracting timestamp from axe(mentor) workflow."""
    result = _extract_timestamp_from_workflow("axe(mentor)-complete-260112_134051")
    assert result == "260112_134051"


def test_extract_timestamp_from_workflow_fix_hook() -> None:
    """Test extracting timestamp from axe(fix-hook) workflow."""
    result = _extract_timestamp_from_workflow("axe(fix-hook)-251230_151429")
    assert result == "251230_151429"


def test_extract_timestamp_from_workflow_crs() -> None:
    """Test extracting timestamp from axe(crs) workflow."""
    result = _extract_timestamp_from_workflow("axe(crs)-critique-251230_151429")
    assert result == "251230_151429"


def test_extract_timestamp_from_workflow_ace_run() -> None:
    """Test extracting timestamp from ace(run) workflow."""
    result = _extract_timestamp_from_workflow("ace(run)-260112_134051")
    assert result == "260112_134051"


def test_extract_timestamp_from_workflow_none() -> None:
    """Test extracting timestamp from None workflow."""
    result = _extract_timestamp_from_workflow(None)
    assert result is None


def test_extract_timestamp_from_workflow_no_dash() -> None:
    """Test extracting timestamp from workflow without dashes."""
    result = _extract_timestamp_from_workflow("nodashes")
    assert result is None


def test_extract_timestamp_from_workflow_no_timestamp() -> None:
    """Test extracting timestamp from workflow without timestamp."""
    result = _extract_timestamp_from_workflow("axe(crs)-critique")
    assert result is None
