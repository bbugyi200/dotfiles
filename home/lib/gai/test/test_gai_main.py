"""Tests for gai.main module."""

import pytest
from main import _normalize_spec


class TestNormalizeSpec:
    """Tests for the _normalize_spec function."""

    def test_normalize_spec_plus_format_unchanged(self) -> None:
        """Test that M+N+P format remains unchanged."""
        assert _normalize_spec("2+2+2") == "2+2+2"
        assert _normalize_spec("1+2+3") == "1+2+3"
        assert _normalize_spec("5+10+15") == "5+10+15"

    def test_normalize_spec_mxn_format_conversion(self) -> None:
        """Test that MxN format is converted to M+M+...+M."""
        assert _normalize_spec("2x3") == "2+2+2"
        assert _normalize_spec("1x5") == "1+1+1+1+1"
        assert _normalize_spec("3x2") == "3+3"
        assert _normalize_spec("4x1") == "4"

    def test_normalize_spec_with_whitespace(self) -> None:
        """Test that whitespace is handled correctly."""
        assert _normalize_spec(" 2x3 ") == "2+2+2"
        # Plus format is returned with stripped whitespace
        assert _normalize_spec(" 1 + 2 + 3 ") == "1 + 2 + 3"

    def test_normalize_spec_invalid_mxn_format(self) -> None:
        """Test that invalid MxN formats raise ValueError."""
        with pytest.raises(ValueError, match="Invalid MxN format"):
            _normalize_spec("2x3x4")

        with pytest.raises(ValueError, match="Both M and N must be positive integers"):
            _normalize_spec("axb")

    def test_normalize_spec_negative_or_zero_values(self) -> None:
        """Test that negative or zero values raise ValueError."""
        with pytest.raises(ValueError, match="positive integers"):
            _normalize_spec("0x3")

        with pytest.raises(ValueError, match="positive integers"):
            _normalize_spec("2x0")

    def test_normalize_spec_single_value(self) -> None:
        """Test that single values are returned as-is."""
        assert _normalize_spec("5") == "5"
        assert _normalize_spec("10") == "10"
