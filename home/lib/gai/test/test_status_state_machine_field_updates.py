"""Tests for CL updates, WIP suffix, parent-child constraints, and description updates."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from status_state_machine import transition_changespec_status
from status_state_machine.field_updates import (
    _apply_cl_update,
    _apply_description_update,
)


def _create_test_project_file_with_suffix(
    name: str = "Test Feature", status: str = "Drafted"
) -> str:
    """Create a temporary project file with a specific NAME for suffix testing."""
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


def test_transition_changespec_status_drafted_to_wip_adds_suffix() -> None:
    """Test that Drafted -> WIP transition adds __<N> suffix."""
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


# === DESCRIPTION update tests ===


def test__apply_description_update_single_line() -> None:
    """Test _apply_description_update replaces a single-line description."""
    lines = [
        "NAME: Test Feature\n",
        "DESCRIPTION:\n",
        "  Old description\n",
        "PARENT: None\n",
        "CL: 12345\n",
        "STATUS: WIP\n",
    ]
    result = _apply_description_update(lines, "Test Feature", "New description")
    assert "DESCRIPTION:\n" in result
    assert "  New description\n" in result
    assert "Old description" not in result
    # Surrounding fields preserved
    assert "PARENT: None\n" in result
    assert "CL: 12345\n" in result
    assert "STATUS: WIP\n" in result


def test__apply_description_update_multi_line() -> None:
    """Test _apply_description_update replaces a multi-line description with blank lines."""
    lines = [
        "NAME: Test Feature\n",
        "DESCRIPTION:\n",
        "  Old line one\n",
        "\n",
        "  Old line two\n",
        "PARENT: None\n",
        "STATUS: WIP\n",
    ]
    result = _apply_description_update(
        lines, "Test Feature", "New line one\n\nNew line two"
    )
    assert "  New line one\n" in result
    assert "  New line two\n" in result
    assert "Old line one" not in result
    assert "Old line two" not in result
    assert "PARENT: None\n" in result
    assert "STATUS: WIP\n" in result


def test__apply_description_update_only_targets_correct_changespec() -> None:
    """Test _apply_description_update only modifies the target ChangeSpec."""
    lines = [
        "NAME: First Feature\n",
        "DESCRIPTION:\n",
        "  First description\n",
        "STATUS: WIP\n",
        "\n",
        "NAME: Second Feature\n",
        "DESCRIPTION:\n",
        "  Second description\n",
        "STATUS: Drafted\n",
    ]
    result = _apply_description_update(lines, "Second Feature", "Updated second")
    # First feature's description should be untouched
    assert "  First description\n" in result
    # Second feature's description should be updated
    assert "  Updated second\n" in result
    assert "  Second description" not in result


def test__apply_description_update_preserves_surrounding_fields() -> None:
    """Test that surrounding fields (PARENT, CL, STATUS) are preserved."""
    lines = [
        "NAME: Test Feature\n",
        "DESCRIPTION:\n",
        "  Old description line 1\n",
        "  Old description line 2\n",
        "PARENT: Parent CL\n",
        "CL: 99999\n",
        "STATUS: Drafted\n",
        "TEST TARGETS: //foo:bar_test\n",
    ]
    result = _apply_description_update(lines, "Test Feature", "Brand new desc")
    result_lines = result.splitlines(keepends=True)
    # Verify all surrounding fields are present and in order
    field_order = []
    for line in result_lines:
        if line.startswith("NAME:"):
            field_order.append("NAME")
        elif line.startswith("DESCRIPTION:"):
            field_order.append("DESCRIPTION")
        elif line.startswith("PARENT:"):
            field_order.append("PARENT")
        elif line.startswith("CL:"):
            field_order.append("CL")
        elif line.startswith("STATUS:"):
            field_order.append("STATUS")
        elif line.startswith("TEST TARGETS:"):
            field_order.append("TEST TARGETS")
    assert field_order == [
        "NAME",
        "DESCRIPTION",
        "PARENT",
        "CL",
        "STATUS",
        "TEST TARGETS",
    ]
