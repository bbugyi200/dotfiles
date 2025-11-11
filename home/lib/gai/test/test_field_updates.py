"""Tests for field_updates.py."""

import tempfile
from pathlib import Path

from work.field_updates import (
    _construct_tap_url,
    _extract_cl_number,
    update_tap_field_from_cl,
)


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


def test_construct_tap_url() -> None:
    """Test constructing TAP URL from CL number."""
    assert (
        _construct_tap_url("829085633") == "http://fusion2/invocations?q=cl:829085633"
    )
    assert _construct_tap_url("12345") == "http://fusion2/invocations?q=cl:12345"


def test_update_tap_field_from_cl_success() -> None:
    """Test updating TAP field from CL field successfully."""
    # Create a temporary project file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """## ChangeSpec: test-feature

NAME: test-feature
DESCRIPTION:
  Test description
PARENT: None
CL: http://cl/829085633
STATUS: Creating EZ CL...
"""
        )
        temp_file = f.name

    try:
        # Update TAP field
        success, error_msg = update_tap_field_from_cl(temp_file, "test-feature")
        assert success is True
        assert error_msg is None

        # Verify TAP field was added
        content = Path(temp_file).read_text()
        assert "TAP: http://fusion2/invocations?q=cl:829085633" in content
    finally:
        Path(temp_file).unlink()


def test_update_tap_field_from_cl_with_plain_number() -> None:
    """Test updating TAP field when CL is a plain number."""
    # Create a temporary project file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """## ChangeSpec: test-feature

NAME: test-feature
DESCRIPTION:
  Test description
PARENT: None
CL: 829085633
STATUS: Creating EZ CL...
"""
        )
        temp_file = f.name

    try:
        # Update TAP field
        success, error_msg = update_tap_field_from_cl(temp_file, "test-feature")
        assert success is True
        assert error_msg is None

        # Verify TAP field was added
        content = Path(temp_file).read_text()
        assert "TAP: http://fusion2/invocations?q=cl:829085633" in content
    finally:
        Path(temp_file).unlink()


def test_update_tap_field_from_cl_no_cl_field() -> None:
    """Test error when ChangeSpec has no CL field."""
    # Create a temporary project file without CL field
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """## ChangeSpec: test-feature

NAME: test-feature
DESCRIPTION:
  Test description
PARENT: None
STATUS: In Progress
"""
        )
        temp_file = f.name

    try:
        # Update TAP field should fail
        success, error_msg = update_tap_field_from_cl(temp_file, "test-feature")
        assert success is False
        assert error_msg is not None
        assert "has no CL field set" in error_msg
    finally:
        Path(temp_file).unlink()


def test_update_tap_field_from_cl_changespec_not_found() -> None:
    """Test error when ChangeSpec is not found."""
    # Create a temporary project file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """## ChangeSpec: different-feature

NAME: different-feature
DESCRIPTION:
  Test description
CL: http://cl/829085633
STATUS: In Progress
"""
        )
        temp_file = f.name

    try:
        # Update TAP field should fail
        success, error_msg = update_tap_field_from_cl(temp_file, "test-feature")
        assert success is False
        assert error_msg is not None
        assert "Could not find ChangeSpec 'test-feature'" in error_msg
    finally:
        Path(temp_file).unlink()


def test_update_tap_field_from_cl_invalid_cl_format() -> None:
    """Test error when CL field has invalid format."""
    # Create a temporary project file with invalid CL
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """## ChangeSpec: test-feature

NAME: test-feature
DESCRIPTION:
  Test description
CL: invalid-cl-value
STATUS: In Progress
"""
        )
        temp_file = f.name

    try:
        # Update TAP field should fail
        success, error_msg = update_tap_field_from_cl(temp_file, "test-feature")
        assert success is False
        assert error_msg is not None
        assert "Could not extract CL number" in error_msg
    finally:
        Path(temp_file).unlink()
