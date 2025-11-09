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
        "Blocked",
        "Not Started",
        "In Progress",
        "Creating EZ CL...",
        "Creating TDD CL...",
        "Running TAP Tests",
        "Failed to Create CL",
        "TDD CL Created",
        "Fixing Tests",
        "Failed to Fix Tests",
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


def test__is_valid_transition_not_started_to_in_progress() -> None:
    """Test transition from 'Not Started' to 'In Progress' is valid."""
    assert _is_valid_transition("Not Started", "In Progress") is True


def test__is_valid_transition_in_progress_to_tdd_cl_created() -> None:
    """Test transition from 'In Progress' to 'TDD CL Created' is valid."""
    assert _is_valid_transition("In Progress", "TDD CL Created") is True


def test__is_valid_transition_in_progress_to_not_started() -> None:
    """Test transition from 'In Progress' to 'Not Started' is valid (rollback)."""
    assert _is_valid_transition("In Progress", "Not Started") is True


def test__is_valid_transition_tdd_cl_created_to_fixing_tests() -> None:
    """Test transition from 'TDD CL Created' to 'Fixing Tests' is valid."""
    assert _is_valid_transition("TDD CL Created", "Fixing Tests") is True


def test__is_valid_transition_fixing_tests_to_tdd_cl_created() -> None:
    """Test transition from 'Fixing Tests' to 'TDD CL Created' is valid (retry)."""
    assert _is_valid_transition("Fixing Tests", "TDD CL Created") is True


def test__is_valid_transition_fixing_tests_to_pre_mailed() -> None:
    """Test transition from 'Fixing Tests' to 'Pre-Mailed' is valid."""
    assert _is_valid_transition("Fixing Tests", "Pre-Mailed") is True


def test__is_valid_transition_pre_mailed_to_mailed() -> None:
    """Test transition from 'Pre-Mailed' to 'Mailed' is valid."""
    assert _is_valid_transition("Pre-Mailed", "Mailed") is True


def test__is_valid_transition_mailed_to_submitted() -> None:
    """Test transition from 'Mailed' to 'Submitted' is valid."""
    assert _is_valid_transition("Mailed", "Submitted") is True


def test__is_valid_transition_invalid_from_not_started_to_mailed() -> None:
    """Test that invalid transition from 'Not Started' to 'Mailed' is rejected."""
    assert _is_valid_transition("Not Started", "Mailed") is False


def test__is_valid_transition_invalid_from_submitted() -> None:
    """Test that transitions from 'Submitted' (terminal state) are invalid."""
    assert _is_valid_transition("Submitted", "Mailed") is False
    assert _is_valid_transition("Submitted", "Not Started") is False


def test__is_valid_transition_invalid_status() -> None:
    """Test that invalid status names are rejected."""
    assert _is_valid_transition("Invalid Status", "In Progress") is False
    assert _is_valid_transition("In Progress", "Invalid Status") is False


def _create_test_project_file(status: str = "Not Started") -> str:
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
    project_file = _create_test_project_file("Not Started")

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Test Feature", "In Progress", validate=True
        )

        assert success is True
        assert old_status == "Not Started"
        assert error is None

        # Verify the file was updated
        with open(project_file) as f:
            content = f.read()
            assert "STATUS: In Progress" in content
            assert "STATUS: Not Started" not in content

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_invalid_transition() -> None:
    """Test that invalid transition is rejected."""
    project_file = _create_test_project_file("Not Started")

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Test Feature", "Mailed", validate=True
        )

        assert success is False
        assert old_status == "Not Started"
        assert error is not None
        assert "Invalid status transition" in error

        # Verify the file was NOT updated
        with open(project_file) as f:
            content = f.read()
            assert "STATUS: Not Started" in content
            assert "STATUS: Mailed" not in content

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_skip_validation() -> None:
    """Test that validation can be skipped with validate=False."""
    project_file = _create_test_project_file("Not Started")

    try:
        # This transition would normally be invalid
        success, old_status, error = transition_changespec_status(
            project_file, "Test Feature", "Mailed", validate=False
        )

        assert success is True
        assert old_status == "Not Started"
        assert error is None

        # Verify the file was updated
        with open(project_file) as f:
            content = f.read()
            assert "STATUS: Mailed" in content

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_nonexistent_changespec() -> None:
    """Test handling of nonexistent ChangeSpec."""
    project_file = _create_test_project_file("Not Started")

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Nonexistent Feature", "In Progress", validate=True
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
STATUS: Not Started
TEST TARGETS: None

---

## ChangeSpec 2

NAME: Feature B
DESCRIPTION:
  Second feature
PARENT: None
CL: None
STATUS: Not Started
TEST TARGETS: None

---
"""
        )
        project_file = f.name

    try:
        success, old_status, error = transition_changespec_status(
            project_file, "Feature A", "In Progress", validate=True
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

            assert feature_a_status == "In Progress"
            assert feature_b_status == "Not Started"

    finally:
        Path(project_file).unlink()


def test_required_transitions_are_valid() -> None:
    """Test that all required transitions from the spec are valid."""
    # Transitions from the requirements
    required_transitions = [
        ("Not Started", "In Progress"),
        ("In Progress", "Not Started"),
        ("In Progress", "TDD CL Created"),
        ("TDD CL Created", "Fixing Tests"),
        ("Fixing Tests", "TDD CL Created"),
        ("Fixing Tests", "Pre-Mailed"),
        ("Pre-Mailed", "Mailed"),
        ("Mailed", "Submitted"),
    ]

    for from_status, to_status in required_transitions:
        error_msg = f"Required transition '{from_status}' -> '{to_status}' is not valid"
        assert _is_valid_transition(from_status, to_status), error_msg


def test_failed_states_allow_retry() -> None:
    """Test that failed states can transition back to retry."""
    assert _is_valid_transition("Failed to Create CL", "Not Started") is True
    assert _is_valid_transition("Failed to Fix Tests", "TDD CL Created") is True


def test_blocked_status_transitions() -> None:
    """Test that Blocked status has correct transitions."""
    # Blocked can only transition to Not Started
    assert _is_valid_transition("Blocked", "Not Started") is True
    # Blocked cannot transition to other statuses
    assert _is_valid_transition("Blocked", "In Progress") is False
    assert _is_valid_transition("Blocked", "Pre-Mailed") is False


def test_not_started_can_transition_to_blocked() -> None:
    """Test that Not Started can transition back to Blocked."""
    assert _is_valid_transition("Not Started", "Blocked") is True


def test_not_started_to_creating_ez_cl() -> None:
    """Test transition from 'Not Started' to 'Creating EZ CL...' is valid."""
    assert _is_valid_transition("Not Started", "Creating EZ CL...") is True


def test_creating_ez_cl_to_running_tap_tests() -> None:
    """Test transition from 'Creating EZ CL...' to 'Running TAP Tests' is valid."""
    assert _is_valid_transition("Creating EZ CL...", "Running TAP Tests") is True


def test_creating_ez_cl_to_not_started() -> None:
    """Test transition from 'Creating EZ CL...' to 'Not Started' is valid (rollback)."""
    assert _is_valid_transition("Creating EZ CL...", "Not Started") is True


def test_running_tap_tests_to_pre_mailed() -> None:
    """Test transition from 'Running TAP Tests' to 'Pre-Mailed' is valid."""
    assert _is_valid_transition("Running TAP Tests", "Pre-Mailed") is True


def test_running_tap_tests_to_not_started() -> None:
    """Test transition from 'Running TAP Tests' to 'Not Started' is valid (rollback)."""
    assert _is_valid_transition("Running TAP Tests", "Not Started") is True


def test_not_started_to_creating_tdd_cl() -> None:
    """Test transition from 'Not Started' to 'Creating TDD CL...' is valid."""
    assert _is_valid_transition("Not Started", "Creating TDD CL...") is True


def test_creating_tdd_cl_to_tdd_cl_created() -> None:
    """Test transition from 'Creating TDD CL...' to 'TDD CL Created' is valid."""
    assert _is_valid_transition("Creating TDD CL...", "TDD CL Created") is True


def test_creating_tdd_cl_to_not_started() -> None:
    """Test transition from 'Creating TDD CL...' to 'Not Started' is valid (rollback)."""
    assert _is_valid_transition("Creating TDD CL...", "Not Started") is True
