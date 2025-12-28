"""Tests for gai.status_state_machine module."""

import tempfile
from pathlib import Path

from status_state_machine import (
    VALID_STATUSES,
    VALID_TRANSITIONS,
    _is_valid_transition,
    transition_changespec_status,
)


def test_valid_statuses_defined() -> None:
    """Test that all valid statuses are defined."""
    expected_statuses = [
        "Drafted",
        "Mailed",
        "Submitted",
        "Reverted",
    ]
    assert VALID_STATUSES == expected_statuses


def test_valid_transitions_defined() -> None:
    """Test that valid transitions are defined for all statuses."""
    # Ensure all valid statuses have an entry in transitions
    for status in VALID_STATUSES:
        assert status in VALID_TRANSITIONS


def test__is_valid_transition_drafted_to_mailed() -> None:
    """Test transition from 'Drafted' to 'Mailed' is valid."""
    assert _is_valid_transition("Drafted", "Mailed") is True


def test__is_valid_transition_mailed_to_submitted() -> None:
    """Test transition from 'Mailed' to 'Submitted' is valid."""
    assert _is_valid_transition("Mailed", "Submitted") is True


def test__is_valid_transition_invalid_from_submitted() -> None:
    """Test that transitions from 'Submitted' (terminal state) are invalid."""
    assert _is_valid_transition("Submitted", "Mailed") is False
    assert _is_valid_transition("Submitted", "Drafted") is False


def test__is_valid_transition_invalid_from_reverted() -> None:
    """Test that transitions from 'Reverted' (terminal state) are invalid."""
    assert _is_valid_transition("Reverted", "Mailed") is False
    assert _is_valid_transition("Reverted", "Drafted") is False


def test__is_valid_transition_invalid_status() -> None:
    """Test that invalid status names are rejected."""
    assert _is_valid_transition("Invalid Status", "Mailed") is False
    assert _is_valid_transition("Mailed", "Invalid Status") is False


def _create_test_project_file(status: str = "Drafted") -> str:
    """Create a temporary project file with a test ChangeSpec."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            f"""# Test Project

## ChangeSpec

NAME: Test Feature
DESCRIPTION:
  A test feature for unit testing
PARENT: None
CL: None
STATUS: {status}
TEST TARGETS: None

---
"""
        )
        return f.name


def test_transition_changespec_status_valid_transition() -> None:
    """Test successful status transition."""
    project_file = _create_test_project_file("Drafted")

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Test Feature", "Mailed", validate=True
        )

        assert success is True
        assert old_status == "Drafted"
        assert error is None

        # Verify the file was updated
        with open(project_file) as f:
            content = f.read()
            assert "STATUS: Mailed" in content
            assert "STATUS: Drafted" not in content

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_invalid_transition() -> None:
    """Test that invalid transition is rejected."""
    project_file = _create_test_project_file("Drafted")

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Test Feature", "Submitted", validate=True
        )

        assert success is False
        assert old_status == "Drafted"
        assert error is not None
        assert "Invalid status transition" in error

        # Verify the file was NOT updated
        with open(project_file) as f:
            content = f.read()
            assert "STATUS: Drafted" in content
            assert "STATUS: Submitted" not in content

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_skip_validation() -> None:
    """Test that validation can be skipped with validate=False."""
    project_file = _create_test_project_file("Drafted")

    try:
        # This transition would normally be invalid
        success, old_status, error = transition_changespec_status(
            project_file, "Test Feature", "Submitted", validate=False
        )

        assert success is True
        assert old_status == "Drafted"
        assert error is None

        # Verify the file was updated
        with open(project_file) as f:
            content = f.read()
            assert "STATUS: Submitted" in content

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_nonexistent_changespec() -> None:
    """Test handling of nonexistent ChangeSpec."""
    project_file = _create_test_project_file("Drafted")

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Nonexistent Feature", "Mailed", validate=True
        )

        assert success is False
        assert old_status is None
        assert error is not None
        assert "not found" in error

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_multiple_changespecs() -> None:
    """Test that only the target ChangeSpec is updated."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(
            """# Test Project

## ChangeSpec 1

NAME: Feature A
DESCRIPTION:
  First feature
PARENT: None
CL: None
TEST TARGETS: None
STATUS: Drafted

---

## ChangeSpec 2

NAME: Feature B
DESCRIPTION:
  Second feature
PARENT: None
CL: None
STATUS: Drafted

---
"""
        )
        project_file = f.name

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Feature A", "Mailed", validate=True
        )

        assert success is True

        # Verify only Feature A was updated
        with open(project_file) as f:
            content = f.read()
            lines = content.split("\n")

            # Find Feature A section
            in_feature_a = False
            in_feature_b = False
            feature_a_status = None
            feature_b_status = None

            for line in lines:
                if "NAME: Feature A" in line:
                    in_feature_a = True
                    in_feature_b = False
                elif "NAME: Feature B" in line:
                    in_feature_a = False
                    in_feature_b = True
                elif line.startswith("STATUS:"):
                    if in_feature_a:
                        feature_a_status = line.split(":", 1)[1].strip()
                    elif in_feature_b:
                        feature_b_status = line.split(":", 1)[1].strip()

            assert feature_a_status == "Mailed"
            assert feature_b_status == "Drafted"

    finally:
        Path(project_file).unlink()


def test_required_transitions_are_valid() -> None:
    """Test that all required transitions from the spec are valid."""
    # Transitions from the requirements
    # Note: "Changes Requested" status was removed and replaced with COMMENTS field
    required_transitions = [
        ("Drafted", "Mailed"),
        ("Mailed", "Submitted"),
    ]

    for from_status, to_status in required_transitions:
        error_msg = f"Required transition '{from_status}' -> '{to_status}' is not valid"
        assert _is_valid_transition(from_status, to_status), error_msg


def test_read_current_status_file_read_error() -> None:
    """Test that _read_current_status handles file read errors gracefully."""
    from status_state_machine import _read_current_status

    # Use a non-existent file path to trigger an exception
    status = _read_current_status("/nonexistent/file/path.md", "Test Feature")

    # Should return None on error
    assert status is None


def test_atomic_file_operations_exception_handling() -> None:
    """Test that atomic file operations clean up temp files on error."""
    from unittest.mock import patch

    from status_state_machine import _update_changespec_status_atomic

    project_file = _create_test_project_file("Drafted")

    try:
        # Mock os.replace to raise an exception, simulating a failure during atomic rename
        with patch("os.replace", side_effect=OSError("Simulated rename failure")):
            try:
                _update_changespec_status_atomic(project_file, "Test Feature", "Mailed")
                # Should raise an exception
                raise AssertionError("Expected OSError to be raised")
            except OSError as e:
                # Verify the exception was raised
                assert "Simulated rename failure" in str(e)

        # Verify the original file is unchanged
        with open(project_file) as f:
            content = f.read()
            assert "STATUS: Drafted" in content
            assert "STATUS: Mailed" not in content

    finally:
        Path(project_file).unlink()


def test_atomic_file_operations() -> None:
    """Test that file updates are atomic and handle UTF-8 correctly."""
    project_file = _create_test_project_file("Drafted")

    try:
        # Test 1: Verify file is updated atomically
        success, old_status, error = transition_changespec_status(
            project_file, "Test Feature", "Mailed", validate=True
        )

        assert success is True
        assert old_status == "Drafted"
        assert error is None

        # Verify the file was updated
        with open(project_file, encoding="utf-8") as f:
            content = f.read()
            assert "STATUS: Mailed" in content

        # Test 2: Test UTF-8 encoding by using Unicode characters
        # Add a status with special characters (though our statuses don't use them,
        # this tests the encoding path)
        with open(project_file, encoding="utf-8") as f:
            original_content = f.read()

        # The file should be readable with UTF-8 encoding
        assert len(original_content) > 0

        # Test 3: Verify that multiple status updates work correctly
        success2, old_status2, error2 = transition_changespec_status(
            project_file, "Test Feature", "Submitted", validate=True
        )

        assert success2 is True
        assert old_status2 == "Mailed"

        with open(project_file, encoding="utf-8") as f:
            content2 = f.read()
            assert "STATUS: Submitted" in content2
            # Verify the old status is not present
            assert "STATUS: Mailed" not in content2

    finally:
        Path(project_file).unlink()


# === READY TO MAIL suffix tests ===


def test_remove_workspace_suffix_strips_ready_to_mail() -> None:
    """Test remove_workspace_suffix also strips READY TO MAIL suffix."""
    from status_state_machine import remove_workspace_suffix

    assert remove_workspace_suffix("Drafted - (!: READY TO MAIL)") == "Drafted"
    assert remove_workspace_suffix("Drafted") == "Drafted"


def test_add_ready_to_mail_suffix() -> None:
    """Test add_ready_to_mail_suffix adds the suffix."""
    from status_state_machine import add_ready_to_mail_suffix

    project_file = _create_test_project_file("Drafted")

    try:
        result = add_ready_to_mail_suffix(project_file, "Test Feature")
        assert result is True

        with open(project_file, encoding="utf-8") as f:
            content = f.read()
            assert "STATUS: Drafted - (!: READY TO MAIL)" in content

    finally:
        Path(project_file).unlink()


def test_add_ready_to_mail_suffix_already_present() -> None:
    """Test add_ready_to_mail_suffix returns False if already present."""
    from status_state_machine import add_ready_to_mail_suffix

    project_file = _create_test_project_file("Drafted - (!: READY TO MAIL)")

    try:
        result = add_ready_to_mail_suffix(project_file, "Test Feature")
        assert result is False

    finally:
        Path(project_file).unlink()


def test_remove_ready_to_mail_suffix() -> None:
    """Test remove_ready_to_mail_suffix removes the suffix."""
    from status_state_machine import remove_ready_to_mail_suffix

    project_file = _create_test_project_file("Drafted - (!: READY TO MAIL)")

    try:
        result = remove_ready_to_mail_suffix(project_file, "Test Feature")
        assert result is True

        with open(project_file, encoding="utf-8") as f:
            content = f.read()
            assert "STATUS: Drafted\n" in content
            assert "READY TO MAIL" not in content

    finally:
        Path(project_file).unlink()


def test_remove_ready_to_mail_suffix_not_present() -> None:
    """Test remove_ready_to_mail_suffix returns False if not present."""
    from status_state_machine import remove_ready_to_mail_suffix

    project_file = _create_test_project_file("Drafted")

    try:
        result = remove_ready_to_mail_suffix(project_file, "Test Feature")
        assert result is False

    finally:
        Path(project_file).unlink()
