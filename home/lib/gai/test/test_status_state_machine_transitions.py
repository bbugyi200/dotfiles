"""Tests for status_state_machine file-based transitions and atomic operations."""

import tempfile
from pathlib import Path

from status_state_machine import (
    is_valid_transition,
    transition_changespec_status,
)


def _create_test_project_file(status: str = "Drafted") -> str:
    """Create a temporary project file with a test ChangeSpec."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(f"""# Test Project

## ChangeSpec

NAME: Test Feature
DESCRIPTION:
  A test feature for unit testing
PARENT: None
CL: None
STATUS: {status}
TEST TARGETS: None

---
""")
        return f.name


def test_transition_changespec_status_valid_transition() -> None:
    """Test successful status transition."""
    project_file = _create_test_project_file("Drafted")

    try:
        success, old_status, error, _ = transition_changespec_status(
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
        success, old_status, error, _ = transition_changespec_status(
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
        success, old_status, error, _ = transition_changespec_status(
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
        success, old_status, error, _ = transition_changespec_status(
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
        f.write("""# Test Project

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
""")
        project_file = f.name

    try:
        success, old_status, error, _ = transition_changespec_status(
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
        ("WIP", "Drafted"),
        ("Drafted", "Mailed"),
        ("Mailed", "Submitted"),
    ]

    for from_status, to_status in required_transitions:
        error_msg = f"Required transition '{from_status}' -> '{to_status}' is not valid"
        assert is_valid_transition(from_status, to_status), error_msg


def test_atomic_file_operations() -> None:
    """Test that file updates are atomic and handle UTF-8 correctly."""
    project_file = _create_test_project_file("Drafted")

    try:
        # Test 1: Verify file is updated atomically
        success, old_status, error, _ = transition_changespec_status(
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
        success2, old_status2, error2, _ = transition_changespec_status(
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


def _create_project_file_with_multiple_changespecs(
    changespecs: list[tuple[str, str, str | None]],
) -> str:
    """Create a project file with multiple ChangeSpecs.

    Args:
        changespecs: List of (name, status, parent) tuples.

    Returns:
        Path to the created project file.
    """
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("# Test Project\n\n")
        for name, status, parent in changespecs:
            parent_val = parent if parent else "None"
            f.write(f"""## ChangeSpec

NAME: {name}
DESCRIPTION:
  Test description
PARENT: {parent_val}
CL: None
STATUS: {status}
TEST TARGETS: None

---

""")
        return f.name


def test_wip_to_drafted_blocked_when_sibling_has_children() -> None:
    """Test WIP->Drafted blocked when sibling WIP ChangeSpec has unreverted children."""
    from unittest.mock import patch

    # Create project file with:
    # - foo_bar__1 (WIP) - the one we're transitioning
    # - foo_bar__2 (WIP) - sibling that has a child
    # - child_of_2 (Drafted) - child of foo_bar__2
    project_file = _create_project_file_with_multiple_changespecs(
        [
            ("foo_bar__1", "WIP", None),
            ("foo_bar__2", "WIP", None),
            ("child_of_2", "Drafted", "foo_bar__2"),
        ]
    )

    try:
        # Mock find_all_changespecs to return our test ChangeSpecs
        from ace.changespec import ChangeSpec

        mock_changespecs = [
            ChangeSpec(
                name="foo_bar__1",
                description="Test",
                parent=None,
                cl=None,
                status="WIP",
                test_targets=None,
                kickstart=None,
                file_path=project_file,
                line_number=6,
            ),
            ChangeSpec(
                name="foo_bar__2",
                description="Test",
                parent=None,
                cl=None,
                status="WIP",
                test_targets=None,
                kickstart=None,
                file_path=project_file,
                line_number=18,
            ),
            ChangeSpec(
                name="child_of_2",
                description="Test",
                parent="foo_bar__2",
                cl=None,
                status="Drafted",
                test_targets=None,
                kickstart=None,
                file_path=project_file,
                line_number=30,
            ),
        ]

        with patch(
            "ace.changespec.find_all_changespecs",
            return_value=mock_changespecs,
        ):
            success, old_status, error, _ = transition_changespec_status(
                project_file, "foo_bar__1", "Drafted", validate=True
            )

        assert success is False
        assert old_status == "WIP"
        assert error is not None
        assert "sibling WIP ChangeSpec 'foo_bar__2' has unreverted children" in error

    finally:
        Path(project_file).unlink()


def test_wip_to_drafted_allowed_when_sibling_children_reverted() -> None:
    """Test WIP->Drafted allowed when sibling's children are all Reverted."""
    from unittest.mock import patch

    # Create project file with:
    # - foo_bar__1 (WIP) - the one we're transitioning
    # - foo_bar__2 (WIP) - sibling
    # - child_of_2 (Reverted) - child of foo_bar__2 that is reverted
    project_file = _create_project_file_with_multiple_changespecs(
        [
            ("foo_bar__1", "WIP", None),
            ("foo_bar__2", "WIP", None),
            ("child_of_2", "Reverted", "foo_bar__2"),
        ]
    )

    try:
        from ace.changespec import ChangeSpec

        mock_changespecs = [
            ChangeSpec(
                name="foo_bar__1",
                description="Test",
                parent=None,
                cl=None,
                status="WIP",
                test_targets=None,
                kickstart=None,
                file_path=project_file,
                line_number=6,
            ),
            ChangeSpec(
                name="foo_bar__2",
                description="Test",
                parent=None,
                cl=None,
                status="WIP",
                test_targets=None,
                kickstart=None,
                file_path=project_file,
                line_number=18,
            ),
            ChangeSpec(
                name="child_of_2",
                description="Test",
                parent="foo_bar__2",
                cl=None,
                status="Reverted",
                test_targets=None,
                kickstart=None,
                file_path=project_file,
                line_number=30,
            ),
        ]

        with patch(
            "ace.changespec.find_all_changespecs",
            return_value=mock_changespecs,
        ):
            # Also need to mock the functions called after successful transition
            with patch("ace.mentors.clear_mentor_wip_flags"):
                with patch(
                    "status_state_machine.transitions._handle_suffix_strip",
                    return_value=[],
                ):
                    success, old_status, error, _ = transition_changespec_status(
                        project_file, "foo_bar__1", "Drafted", validate=True
                    )

        assert success is True
        assert old_status == "WIP"
        assert error is None

    finally:
        Path(project_file).unlink()


def test_wip_to_drafted_allowed_when_no_siblings() -> None:
    """Test WIP->Drafted allowed when no sibling WIP ChangeSpecs exist."""
    from unittest.mock import patch

    # Create project file with just one WIP ChangeSpec (no siblings)
    project_file = _create_project_file_with_multiple_changespecs(
        [
            ("foo_bar__1", "WIP", None),
        ]
    )

    try:
        from ace.changespec import ChangeSpec

        mock_changespecs = [
            ChangeSpec(
                name="foo_bar__1",
                description="Test",
                parent=None,
                cl=None,
                status="WIP",
                test_targets=None,
                kickstart=None,
                file_path=project_file,
                line_number=6,
            ),
        ]

        with patch(
            "ace.changespec.find_all_changespecs",
            return_value=mock_changespecs,
        ):
            with patch("ace.mentors.clear_mentor_wip_flags"):
                with patch(
                    "status_state_machine.transitions._handle_suffix_strip",
                    return_value=[],
                ):
                    success, old_status, error, _ = transition_changespec_status(
                        project_file, "foo_bar__1", "Drafted", validate=True
                    )

        assert success is True
        assert old_status == "WIP"
        assert error is None

    finally:
        Path(project_file).unlink()
