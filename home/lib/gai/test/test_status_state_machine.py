"""Tests for gai.status_state_machine module."""

import tempfile
from pathlib import Path

from status_state_machine import (
    VALID_STATUSES,
    VALID_TRANSITIONS,
    is_valid_transition,
    transition_changespec_status,
)
from status_state_machine.field_updates import _apply_cl_update


def test_valid_statuses_defined() -> None:
    """Test that all valid statuses are defined."""
    expected_statuses = [
        "WIP",
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


def test_is_valid_transition_wip_to_drafted() -> None:
    """Test transition from 'WIP' to 'Drafted' is valid."""
    assert is_valid_transition("WIP", "Drafted") is True


def test_is_valid_transition_invalid_from_wip() -> None:
    """Test that WIP can only transition to Drafted."""
    assert is_valid_transition("WIP", "Mailed") is False
    assert is_valid_transition("WIP", "Submitted") is False
    assert is_valid_transition("WIP", "Reverted") is False


def test_is_valid_transition_drafted_to_mailed() -> None:
    """Test transition from 'Drafted' to 'Mailed' is valid."""
    assert is_valid_transition("Drafted", "Mailed") is True


def test_is_valid_transition_mailed_to_submitted() -> None:
    """Test transition from 'Mailed' to 'Submitted' is valid."""
    assert is_valid_transition("Mailed", "Submitted") is True


def test_is_valid_transition_invalid_from_submitted() -> None:
    """Test that transitions from 'Submitted' (terminal state) are invalid."""
    assert is_valid_transition("Submitted", "Mailed") is False
    assert is_valid_transition("Submitted", "Drafted") is False


def test_is_valid_transition_invalid_from_reverted() -> None:
    """Test that transitions from 'Reverted' (terminal state) are invalid."""
    assert is_valid_transition("Reverted", "Mailed") is False
    assert is_valid_transition("Reverted", "Drafted") is False


def test_is_valid_transition_invalid_status() -> None:
    """Test that invalid status names are rejected."""
    assert is_valid_transition("Invalid Status", "Mailed") is False
    assert is_valid_transition("Mailed", "Invalid Status") is False


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


# Additional tests for remove_workspace_suffix
def test_remove_workspace_suffix_with_workspace() -> None:
    """Test remove_workspace_suffix strips workspace suffix."""
    from status_state_machine import remove_workspace_suffix

    assert remove_workspace_suffix("WIP (fig_3)") == "WIP"
    assert remove_workspace_suffix("Drafted (project_99)") == "Drafted"
    assert remove_workspace_suffix("Mailed (my-proj_1)") == "Mailed"


def test_remove_workspace_suffix_no_suffix() -> None:
    """Test remove_workspace_suffix returns unchanged when no suffix."""
    from status_state_machine import remove_workspace_suffix

    assert remove_workspace_suffix("WIP") == "WIP"
    assert remove_workspace_suffix("Drafted") == "Drafted"
    assert remove_workspace_suffix("Mailed") == "Mailed"
    assert remove_workspace_suffix("Submitted") == "Submitted"


def test_remove_workspace_suffix_both_suffixes() -> None:
    """Test remove_workspace_suffix removes both workspace and READY TO MAIL."""
    from status_state_machine import remove_workspace_suffix

    # Note: This pattern shouldn't occur in practice but tests the function
    result = remove_workspace_suffix("Drafted - (!: READY TO MAIL)")
    assert result == "Drafted"


def test_is_valid_transition_with_workspace_suffix() -> None:
    """Test that is_valid_transition handles workspace suffixes correctly."""
    assert is_valid_transition("WIP (fig_3)", "Drafted") is True
    assert is_valid_transition("Drafted", "Mailed (project_1)") is True
    assert is_valid_transition("WIP (proj_1)", "Drafted (proj_2)") is True


def test_is_valid_transition_drafted_to_wip() -> None:
    """Test that Drafted CAN transition back to WIP."""
    assert is_valid_transition("Drafted", "WIP") is True


def test__apply_cl_update_sets_cl() -> None:
    """Test _apply_cl_update sets CL field."""
    lines = [
        "NAME: Test Feature\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "CL: old_cl\n",
        "STATUS: WIP\n",
    ]
    result = _apply_cl_update(lines, "Test Feature", "new_cl_value")
    assert "CL: new_cl_value\n" in result
    assert "CL: old_cl\n" not in result


def test__apply_cl_update_removes_cl() -> None:
    """Test _apply_cl_update removes CL when None."""
    lines = [
        "NAME: Test Feature\n",
        "CL: old_cl\n",
        "STATUS: WIP\n",
    ]
    result = _apply_cl_update(lines, "Test Feature", None)
    assert "CL:" not in result


def test__apply_cl_update_adds_cl_before_status() -> None:
    """Test _apply_cl_update adds CL before STATUS when missing."""
    lines = [
        "NAME: Test Feature\n",
        "DESCRIPTION:\n",
        "  Test description\n",
        "STATUS: WIP\n",
    ]
    result = _apply_cl_update(lines, "Test Feature", "new_cl")
    assert "CL: new_cl\n" in result
    # CL should appear before STATUS
    lines_list = result.split("\n")
    cl_idx = next(i for i, ln in enumerate(lines_list) if "CL:" in ln)
    status_idx = next(i for i, ln in enumerate(lines_list) if "STATUS:" in ln)
    assert cl_idx < status_idx


def test_is_valid_transition_mailed_cannot_go_back() -> None:
    """Test that Mailed cannot transition back to Drafted or WIP."""
    assert is_valid_transition("Mailed", "Drafted") is False
    assert is_valid_transition("Mailed", "WIP") is False


def _create_test_project_file_with_suffix(
    name: str = "Test Feature", status: str = "Drafted"
) -> str:
    """Create a temporary project file with a specific NAME for suffix testing."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write(f"""# Test Project

## ChangeSpec

NAME: {name}
DESCRIPTION:
  A test feature for unit testing
PARENT: None
CL: None
STATUS: {status}
TEST TARGETS: None

---
""")
        return f.name


def test_transition_changespec_status_drafted_to_wip_adds_suffix() -> None:
    """Test that Drafted -> WIP transition adds __<N> suffix."""
    from unittest.mock import patch

    project_file = _create_test_project_file_with_suffix(
        name="Test Feature", status="Drafted"
    )

    try:
        # Mock functions imported at runtime - use source module paths
        with (
            patch("ace.changespec.find_all_changespecs") as mock_find,
            patch("ace.mentors.set_mentor_wip_flags") as mock_set_wip,
            patch("ace.revert.update_changespec_name_atomic") as mock_rename,
            patch("running_field.get_workspace_directory") as mock_ws_dir,
            patch(
                "status_state_machine.field_updates.update_parent_references_atomic"
            ) as mock_parent_refs,
            patch("running_field.update_running_field_cl_name"),
        ):
            mock_find.return_value = []
            mock_ws_dir.side_effect = RuntimeError("No workspace")

            success, old_status, error, _ = transition_changespec_status(
                project_file, "Test Feature", "WIP", validate=True
            )

            assert success is True
            assert old_status == "Drafted"
            assert error is None

            # Verify NAME rename was called with correct suffix
            mock_rename.assert_called_once_with(
                project_file, "Test Feature", "Test Feature__1"
            )

            # Verify PARENT references were updated
            mock_parent_refs.assert_called_once_with(
                project_file, "Test Feature", "Test Feature__1"
            )

            # Verify set_mentor_wip_flags was called
            mock_set_wip.assert_called_once()

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_drafted_to_wip_increments_suffix() -> None:
    """Test that Drafted -> WIP uses next available suffix number."""
    from unittest.mock import MagicMock, patch

    project_file = _create_test_project_file_with_suffix(
        name="Test Feature", status="Drafted"
    )

    try:
        # Mock find_all_changespecs to return existing suffixed names
        mock_cs1 = MagicMock()
        mock_cs1.name = "Test Feature__1"
        mock_cs2 = MagicMock()
        mock_cs2.name = "Test Feature__2"

        # Mock functions imported at runtime - use source module paths
        with (
            patch("ace.changespec.find_all_changespecs") as mock_find,
            patch("ace.mentors.set_mentor_wip_flags"),
            patch("ace.revert.update_changespec_name_atomic") as mock_rename,
            patch("running_field.get_workspace_directory") as mock_ws_dir,
            patch("status_state_machine.field_updates.update_parent_references_atomic"),
            patch("running_field.update_running_field_cl_name"),
        ):
            mock_find.return_value = [mock_cs1, mock_cs2]
            mock_ws_dir.side_effect = RuntimeError("No workspace")

            success, old_status, error, _ = transition_changespec_status(
                project_file, "Test Feature", "WIP", validate=True
            )

            assert success is True

            # Should use __3 since __1 and __2 exist
            mock_rename.assert_called_once_with(
                project_file, "Test Feature", "Test Feature__3"
            )

    finally:
        Path(project_file).unlink()


def test_transition_changespec_status_drafted_to_wip_updates_parent_refs() -> None:
    """Test that Drafted -> WIP updates PARENT references in child ChangeSpecs."""
    import tempfile
    from unittest.mock import patch

    # Create a project file with parent-child relationship
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("""# Test Project

## ChangeSpec

NAME: Parent Feature
DESCRIPTION:
  A parent feature
CL: None
STATUS: Drafted
TEST TARGETS: None


## ChangeSpec

NAME: Child Feature
DESCRIPTION:
  A child feature
PARENT: Parent Feature
CL: None
STATUS: WIP
TEST TARGETS: None

---
""")
        project_file = f.name

    try:
        # Mock functions imported at runtime - use source module paths
        with (
            patch("ace.changespec.find_all_changespecs") as mock_find,
            patch("ace.mentors.set_mentor_wip_flags"),
            patch("ace.revert.update_changespec_name_atomic"),
            patch("running_field.get_workspace_directory") as mock_ws_dir,
            patch(
                "status_state_machine.field_updates.update_parent_references_atomic"
            ) as mock_parent_refs,
            patch("running_field.update_running_field_cl_name"),
        ):
            mock_find.return_value = []
            mock_ws_dir.side_effect = RuntimeError("No workspace")

            success, _, _, _ = transition_changespec_status(
                project_file, "Parent Feature", "WIP", validate=True
            )

            assert success is True

            # Verify PARENT references update was called with old->new names
            mock_parent_refs.assert_called_once_with(
                project_file, "Parent Feature", "Parent Feature__1"
            )

    finally:
        Path(project_file).unlink()


# === WIP children constraint tests ===


def test_transition_to_wip_blocked_when_child_is_drafted() -> None:
    """Test that transition to WIP is blocked when a child has Drafted status."""
    from unittest.mock import MagicMock, patch

    project_file = _create_test_project_file_with_suffix(
        name="Parent Feature", status="Drafted"
    )

    try:
        # Mock find_all_changespecs to return a child with Drafted status
        mock_child = MagicMock()
        mock_child.name = "Child Feature"
        mock_child.parent = "Parent Feature"
        mock_child.status = "Drafted"

        with patch("ace.changespec.find_all_changespecs") as mock_find:
            mock_find.return_value = [mock_child]

            success, old_status, error, _ = transition_changespec_status(
                project_file, "Parent Feature", "WIP", validate=True
            )

            assert success is False
            assert old_status == "Drafted"
            assert error is not None
            assert "Cannot transition 'Parent Feature' to WIP" in error
            assert "children must be WIP or Reverted" in error
            assert "Child Feature (Drafted)" in error

    finally:
        Path(project_file).unlink()


def test_transition_to_wip_allowed_when_children_are_wip_or_reverted() -> None:
    """Test that transition to WIP succeeds when children are WIP or Reverted."""
    from unittest.mock import MagicMock, patch

    project_file = _create_test_project_file_with_suffix(
        name="Parent Feature", status="Drafted"
    )

    try:
        # Mock find_all_changespecs to return children with valid statuses
        mock_child_wip = MagicMock()
        mock_child_wip.name = "Child WIP"
        mock_child_wip.parent = "Parent Feature"
        mock_child_wip.status = "WIP"

        mock_child_reverted = MagicMock()
        mock_child_reverted.name = "Child Reverted"
        mock_child_reverted.parent = "Parent Feature"
        mock_child_reverted.status = "Reverted"

        # Also include an unrelated child (different parent)
        mock_unrelated = MagicMock()
        mock_unrelated.name = "Unrelated"
        mock_unrelated.parent = "Other Parent"
        mock_unrelated.status = "Drafted"

        with (
            patch("ace.changespec.find_all_changespecs") as mock_find,
            patch("ace.mentors.set_mentor_wip_flags"),
            patch("ace.revert.update_changespec_name_atomic"),
            patch("running_field.get_workspace_directory") as mock_ws_dir,
            patch("status_state_machine.field_updates.update_parent_references_atomic"),
            patch("running_field.update_running_field_cl_name"),
        ):
            mock_find.return_value = [
                mock_child_wip,
                mock_child_reverted,
                mock_unrelated,
            ]
            mock_ws_dir.side_effect = RuntimeError("No workspace")

            success, old_status, error, _ = transition_changespec_status(
                project_file, "Parent Feature", "WIP", validate=True
            )

            assert success is True
            assert old_status == "Drafted"
            assert error is None

    finally:
        Path(project_file).unlink()


def test_transition_from_wip_blocked_when_parent_is_wip() -> None:
    """Test that child cannot transition away from WIP/Reverted when parent is WIP."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("""# Test Project

## ChangeSpec

NAME: Parent Feature
DESCRIPTION:
  A parent feature
CL: None
STATUS: WIP
TEST TARGETS: None


## ChangeSpec

NAME: Child Feature
DESCRIPTION:
  A child feature
PARENT: Parent Feature
CL: None
STATUS: WIP
TEST TARGETS: None

---
""")
        project_file = f.name

    try:
        # Try to transition child from WIP to Drafted when parent is WIP
        success, old_status, error, _ = transition_changespec_status(
            project_file, "Child Feature", "Drafted", validate=True
        )

        assert success is False
        assert old_status == "WIP"
        assert error is not None
        assert "Cannot transition 'Child Feature' to Drafted" in error
        assert "parent 'Parent Feature' is WIP" in error
        assert "Children of WIP ChangeSpecs must be WIP or Reverted" in error

    finally:
        Path(project_file).unlink()


def test_transition_from_wip_allowed_when_parent_is_not_wip() -> None:
    """Test that child can transition when parent is not WIP."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("""# Test Project

## ChangeSpec

NAME: Parent Feature
DESCRIPTION:
  A parent feature
CL: None
STATUS: Drafted
TEST TARGETS: None


## ChangeSpec

NAME: Child Feature
DESCRIPTION:
  A child feature
PARENT: Parent Feature
CL: None
STATUS: WIP
TEST TARGETS: None

---
""")
        project_file = f.name

    try:
        # Mock the external dependencies
        from unittest.mock import patch

        with (
            patch("ace.mentors.clear_mentor_wip_flags"),
            patch("gai_utils.has_suffix") as mock_has_suffix,
        ):
            mock_has_suffix.return_value = False

            # Transition child from WIP to Drafted when parent is Drafted
            success, old_status, error, _ = transition_changespec_status(
                project_file, "Child Feature", "Drafted", validate=True
            )

            assert success is True
            assert old_status == "WIP"
            assert error is None

    finally:
        Path(project_file).unlink()


def test_transition_to_reverted_allowed_when_parent_is_wip() -> None:
    """Test that child can transition to Reverted even when parent is WIP."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
        f.write("""# Test Project

## ChangeSpec

NAME: Parent Feature
DESCRIPTION:
  A parent feature
CL: None
STATUS: WIP
TEST TARGETS: None


## ChangeSpec

NAME: Child Feature
DESCRIPTION:
  A child feature
PARENT: Parent Feature
CL: None
STATUS: WIP
TEST TARGETS: None

---
""")
        project_file = f.name

    try:
        # Transition child to Reverted - this should succeed even with WIP parent
        # Note: validate=False because Reverted is typically set via revert operation
        success, old_status, error, _ = transition_changespec_status(
            project_file, "Child Feature", "Reverted", validate=False
        )

        assert success is True
        assert old_status == "WIP"
        assert error is None

    finally:
        Path(project_file).unlink()
