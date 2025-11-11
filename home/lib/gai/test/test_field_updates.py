"""Tests for field_updates.py."""

from work.field_updates import _extract_cl_number


def test_extract_cl_number_from_url() -> None:
    """Test extracting CL number from URL format."""
    assert _extract_cl_number("http://cl/829085633") == "829085633"
    assert _extract_cl_number("https://cl/829085633") == "829085633"
    assert _extract_cl_number("cl/829085633") == "829085633"


def test_extract_cl_number_from_plain_number() -> None:
    """Test extracting CL number from plain number format."""
    assert _extract_cl_number("829085633") == "829085633"
    assert _extract_cl_number("12345") == "12345"


def test_extract_cl_number_none_cases() -> None:
    """Test that None is returned for invalid inputs."""
    assert _extract_cl_number("") is None
    assert _extract_cl_number("None") is None
    assert _extract_cl_number("invalid") is None
    assert _extract_cl_number("http://example.com") is None
