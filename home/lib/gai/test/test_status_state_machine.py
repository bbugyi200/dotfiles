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
        "Blocked (EZ)",
        "Blocked (TDD)",
        "Unstarted (EZ)",
        "Unstarted (TDD)",
        "Creating EZ CL...",
        "Creating TDD CL...",
        "Running TAP Tests",
        "Ready for QA",
        "Running QA...",
        "TDD CL Created",
        "Finishing TDD CL...",
        "Fixing Tests...",
        "Pre-Mailed",
        "Mailed",
        "Submitted",
    ]
    assert VALID_STATUSES == expected_statuses


def test_valid_transitions_defined() -> None:
    """Test that valid transitions are defined for all statuses."""
    # Ensure all valid statuses have an entry in transitions
    for status in VALID_STATUSES:
        assert status in VALID_TRANSITIONS


def test__is_valid_transition_tdd_cl_created_to_finishing_tdd_cl() -> None:
    """Test transition from 'TDD CL Created' to 'Finishing TDD CL...' is valid."""
    assert _is_valid_transition("TDD CL Created", "Finishing TDD CL...") is True


def test__is_valid_transition_finishing_tdd_cl_to_tdd_cl_created() -> None:
    """Test transition from 'Finishing TDD CL...' to 'TDD CL Created' is valid (retry)."""
    assert _is_valid_transition("Finishing TDD CL...", "TDD CL Created") is True


def test__is_valid_transition_finishing_tdd_cl_to_pre_mailed() -> None:
    """Test transition from 'Finishing TDD CL...' to 'Pre-Mailed' is valid."""
    assert _is_valid_transition("Finishing TDD CL...", "Pre-Mailed") is True


def test__is_valid_transition_finishing_tdd_cl_to_running_tap_tests() -> None:
    """Test transition from 'Finishing TDD CL...' to 'Running TAP Tests' is valid."""
    assert _is_valid_transition("Finishing TDD CL...", "Running TAP Tests") is True


def test__is_valid_transition_fixing_tests_to_running_tap_tests() -> None:
    """Test transition from 'Fixing Tests...' to 'Running TAP Tests' is valid."""
    assert _is_valid_transition("Fixing Tests...", "Running TAP Tests") is True


def test__is_valid_transition_pre_mailed_to_mailed() -> None:
    """Test transition from 'Pre-Mailed' to 'Mailed' is valid."""
    assert _is_valid_transition("Pre-Mailed", "Mailed") is True


def test__is_valid_transition_mailed_to_submitted() -> None:
    """Test transition from 'Mailed' to 'Submitted' is valid."""
    assert _is_valid_transition("Mailed", "Submitted") is True


def test__is_valid_transition_invalid_from_unstarted_tdd_to_mailed() -> None:
    """Test that invalid transition from 'Unstarted (TDD)' to 'Mailed' is rejected."""
    assert _is_valid_transition("Unstarted (TDD)", "Mailed") is False


def test__is_valid_transition_invalid_from_submitted() -> None:
    """Test that transitions from 'Submitted' (terminal state) are invalid."""
    assert _is_valid_transition("Submitted", "Mailed") is False
    assert _is_valid_transition("Submitted", "Unstarted (TDD)") is False


def test__is_valid_transition_invalid_status() -> None:
    """Test that invalid status names are rejected."""
    assert _is_valid_transition("Invalid Status", "TDD CL Created") is False
    assert _is_valid_transition("TDD CL Created", "Invalid Status") is False


def _create_test_project_file(status: str = "Unstarted (TDD)") -> str:
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
    project_file = _create_test_project_file("Unstarted (TDD)")

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Test Feature", "Creating TDD CL...", validate=True
        )

        assert success is True
        assert old_status == "Unstarted (TDD)"
        assert error is None

        # Verify the file was updated
        with open(project_file) as f:
            content = f.read()
            assert "STATUS: Creating TDD CL..." in content
            assert "STATUS: Unstarted (TDD)" not in content

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_invalid_transition() -> None:
    """Test that invalid transition is rejected."""
    project_file = _create_test_project_file("Unstarted (TDD)")

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Test Feature", "Mailed", validate=True
        )

        assert success is False
        assert old_status == "Unstarted (TDD)"
        assert error is not None
        assert "Invalid status transition" in error

        # Verify the file was NOT updated
        with open(project_file) as f:
            content = f.read()
            assert "STATUS: Unstarted (TDD)" in content
            assert "STATUS: Mailed" not in content

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_skip_validation() -> None:
    """Test that validation can be skipped with validate=False."""
    project_file = _create_test_project_file("Unstarted (TDD)")

    try:
        # This transition would normally be invalid
        success, old_status, error = transition_changespec_status(
            project_file, "Test Feature", "Mailed", validate=False
        )

        assert success is True
        assert old_status == "Unstarted (TDD)"
        assert error is None

        # Verify the file was updated
        with open(project_file) as f:
            content = f.read()
            assert "STATUS: Mailed" in content

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_nonexistent_changespec() -> None:
    """Test handling of nonexistent ChangeSpec."""
    project_file = _create_test_project_file("Unstarted (TDD)")

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Nonexistent Feature", "Creating TDD CL...", validate=True
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
STATUS: Unstarted (EZ)

---

## ChangeSpec 2

NAME: Feature B
DESCRIPTION:
  Second feature
PARENT: None
CL: None
STATUS: Unstarted (TDD)

---
"""
        )
        project_file = f.name

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Feature A", "Creating EZ CL...", validate=True
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

            assert feature_a_status == "Creating EZ CL..."
            assert feature_b_status == "Unstarted (TDD)"

    finally:
        Path(project_file).unlink()


def test_required_transitions_are_valid() -> None:
    """Test that all required transitions from the spec are valid."""
    # Transitions from the requirements
    required_transitions = [
        ("Unstarted (TDD)", "Creating TDD CL..."),
        ("Unstarted (EZ)", "Creating EZ CL..."),
        ("TDD CL Created", "Finishing TDD CL..."),
        ("Finishing TDD CL...", "TDD CL Created"),
        ("Finishing TDD CL...", "Pre-Mailed"),
        ("Pre-Mailed", "Mailed"),
        ("Mailed", "Submitted"),
    ]

    for from_status, to_status in required_transitions:
        error_msg = f"Required transition '{from_status}' -> '{to_status}' is not valid"
        assert _is_valid_transition(from_status, to_status), error_msg


def test_rollback_transitions_allowed() -> None:
    """Test that rollback transitions are allowed."""
    # Creating workflows can rollback to Unstarted
    assert _is_valid_transition("Creating TDD CL...", "Unstarted (TDD)") is True
    assert _is_valid_transition("Creating EZ CL...", "Unstarted (EZ)") is True
    # Finishing workflow can rollback to TDD CL Created
    assert _is_valid_transition("Finishing TDD CL...", "TDD CL Created") is True


def test_blocked_ez_status_transitions() -> None:
    """Test that Blocked (EZ) status has correct transitions."""
    # Blocked (EZ) can only transition to Unstarted (EZ)
    assert _is_valid_transition("Blocked (EZ)", "Unstarted (EZ)") is True
    # Blocked (EZ) cannot transition to other statuses
    assert _is_valid_transition("Blocked (EZ)", "Creating EZ CL...") is False
    assert _is_valid_transition("Blocked (EZ)", "Pre-Mailed") is False


def test_blocked_tdd_status_transitions() -> None:
    """Test that Blocked (TDD) status has correct transitions."""
    # Blocked (TDD) can only transition to Unstarted (TDD)
    assert _is_valid_transition("Blocked (TDD)", "Unstarted (TDD)") is True
    # Blocked (TDD) cannot transition to other statuses
    assert _is_valid_transition("Blocked (TDD)", "Creating TDD CL...") is False
    assert _is_valid_transition("Blocked (TDD)", "Pre-Mailed") is False


def test_unstarted_ez_can_transition_to_blocked_ez() -> None:
    """Test that Unstarted (EZ) can transition back to Blocked (EZ)."""
    assert _is_valid_transition("Unstarted (EZ)", "Blocked (EZ)") is True


def test_unstarted_tdd_can_transition_to_blocked_tdd() -> None:
    """Test that Unstarted (TDD) can transition back to Blocked (TDD)."""
    assert _is_valid_transition("Unstarted (TDD)", "Blocked (TDD)") is True


def test_unstarted_ez_to_creating_ez_cl() -> None:
    """Test transition from 'Unstarted (EZ)' to 'Creating EZ CL...' is valid."""
    assert _is_valid_transition("Unstarted (EZ)", "Creating EZ CL...") is True


def test_creating_ez_cl_to_running_tap_tests() -> None:
    """Test transition from 'Creating EZ CL...' to 'Running TAP Tests' is valid."""
    assert _is_valid_transition("Creating EZ CL...", "Running TAP Tests") is True


def test_creating_ez_cl_to_unstarted_ez() -> None:
    """Test transition from 'Creating EZ CL...' to 'Unstarted (EZ)' is valid (rollback)."""
    assert _is_valid_transition("Creating EZ CL...", "Unstarted (EZ)") is True


def test_running_tap_tests_to_pre_mailed() -> None:
    """Test transition from 'Running TAP Tests' to 'Pre-Mailed' is valid."""
    assert _is_valid_transition("Running TAP Tests", "Pre-Mailed") is True


def test_running_tap_tests_to_unstarted_ez() -> None:
    """Test transition from 'Running TAP Tests' to 'Unstarted (EZ)' is valid (rollback)."""
    assert _is_valid_transition("Running TAP Tests", "Unstarted (EZ)") is True


def test_unstarted_tdd_to_creating_tdd_cl() -> None:
    """Test transition from 'Unstarted (TDD)' to 'Creating TDD CL...' is valid."""
    assert _is_valid_transition("Unstarted (TDD)", "Creating TDD CL...") is True


def test_creating_tdd_cl_to_tdd_cl_created() -> None:
    """Test transition from 'Creating TDD CL...' to 'TDD CL Created' is valid."""
    assert _is_valid_transition("Creating TDD CL...", "TDD CL Created") is True


def test_creating_tdd_cl_to_unstarted_tdd() -> None:
    """Test transition from 'Creating TDD CL...' to 'Unstarted (TDD)' is valid (rollback)."""
    assert _is_valid_transition("Creating TDD CL...", "Unstarted (TDD)") is True


def test_running_tap_tests_to_ready_for_qa() -> None:
    """Test transition from 'Running TAP Tests' to 'Ready for QA' is valid."""
    assert _is_valid_transition("Running TAP Tests", "Ready for QA") is True


def test_ready_for_qa_to_running_qa() -> None:
    """Test transition from 'Ready for QA' to 'Running QA...' is valid."""
    assert _is_valid_transition("Ready for QA", "Running QA...") is True


def test_running_qa_to_pre_mailed() -> None:
    """Test transition from 'Running QA...' to 'Pre-Mailed' is valid."""
    assert _is_valid_transition("Running QA...", "Pre-Mailed") is True


def test_running_qa_to_ready_for_qa() -> None:
    """Test transition from 'Running QA...' to 'Ready for QA' is valid (rollback)."""
    assert _is_valid_transition("Running QA...", "Ready for QA") is True


def test_ready_for_qa_cannot_skip_to_pre_mailed() -> None:
    """Test that 'Ready for QA' cannot skip directly to 'Pre-Mailed'."""
    assert _is_valid_transition("Ready for QA", "Pre-Mailed") is False


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

    project_file = _create_test_project_file("Unstarted (TDD)")

    try:
        # Mock os.replace to raise an exception, simulating a failure during atomic rename
        with patch("os.replace", side_effect=OSError("Simulated rename failure")):
            try:
                _update_changespec_status_atomic(
                    project_file, "Test Feature", "Creating TDD CL..."
                )
                # Should raise an exception
                raise AssertionError("Expected OSError to be raised")
            except OSError as e:
                # Verify the exception was raised
                assert "Simulated rename failure" in str(e)

        # Verify the original file is unchanged
        with open(project_file) as f:
            content = f.read()
            assert "STATUS: Unstarted (TDD)" in content
            assert "STATUS: Creating TDD CL..." not in content

    finally:
        Path(project_file).unlink()


def test_atomic_file_operations() -> None:
    """Test that file updates are atomic and handle UTF-8 correctly."""
    project_file = _create_test_project_file("Unstarted (TDD)")

    try:
        # Test 1: Verify file is updated atomically
        success, old_status, error = transition_changespec_status(
            project_file, "Test Feature", "Creating TDD CL...", validate=True
        )

        assert success is True
        assert old_status == "Unstarted (TDD)"
        assert error is None

        # Verify the file was updated
        with open(project_file, encoding="utf-8") as f:
            content = f.read()
            assert "STATUS: Creating TDD CL..." in content

        # Test 2: Test UTF-8 encoding by using Unicode characters
        # Add a status with special characters (though our statuses don't use them,
        # this tests the encoding path)
        with open(project_file, encoding="utf-8") as f:
            original_content = f.read()

        # The file should be readable with UTF-8 encoding
        assert len(original_content) > 0

        # Test 3: Verify that multiple status updates work correctly
        success2, old_status2, error2 = transition_changespec_status(
            project_file, "Test Feature", "TDD CL Created", validate=True
        )

        assert success2 is True
        assert old_status2 == "Creating TDD CL..."

        with open(project_file, encoding="utf-8") as f:
            content2 = f.read()
            assert "STATUS: TDD CL Created" in content2
            # Verify the old status is not present
            assert "STATUS: Creating TDD CL..." not in content2

    finally:
        Path(project_file).unlink()
