"""Tests for the rebase feature (PARENT field updates and eligible parents)."""

import tempfile
from pathlib import Path

from ace.changespec import get_eligible_parents_in_project
from status_state_machine import update_changespec_parent_atomic
from status_state_machine.field_updates import _apply_parent_update


def _create_test_project_file_with_parent(
    status: str = "Drafted", parent: str | None = None
) -> str:
    """Create a temporary project file with a test ChangeSpec."""
    parent_line = f"PARENT: {parent}\n" if parent else ""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write(f"""# Test Project

## ChangeSpec

NAME: Test Feature
DESCRIPTION:
  A test feature for unit testing
{parent_line}CL: None
STATUS: {status}
TEST TARGETS: None

---
""")
        return f.name


def _create_multi_changespec_file() -> str:
    """Create a project file with multiple ChangeSpecs for testing eligible parents."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("""# Test Project

NAME: Feature A
DESCRIPTION:
  First feature
CL: http://cl/123
STATUS: WIP

---

NAME: Feature B
DESCRIPTION:
  Second feature
PARENT: Feature A
CL: http://cl/456
STATUS: Drafted

---

NAME: Feature C
DESCRIPTION:
  Third feature
CL: http://cl/789
STATUS: Mailed

---

NAME: Feature D
DESCRIPTION:
  Fourth feature (terminal)
CL: http://cl/999
STATUS: Submitted

---

NAME: Feature E
DESCRIPTION:
  Fifth feature (terminal)
CL: None
STATUS: Reverted

---
""")
        return f.name


# === Tests for _apply_parent_update ===


def test_apply_parent_update_existing_field() -> None:
    """Test updating an existing PARENT field."""
    lines = [
        "NAME: Test Feature\n",
        "DESCRIPTION:\n",
        "  A test feature\n",
        "PARENT: OldParent\n",
        "CL: http://cl/123\n",
        "STATUS: Drafted\n",
    ]

    result = _apply_parent_update(lines, "Test Feature", "NewParent")
    assert "PARENT: NewParent\n" in result
    assert "PARENT: OldParent" not in result


def test_apply_parent_update_no_existing_field() -> None:
    """Test adding PARENT field when it doesn't exist."""
    lines = [
        "NAME: Test Feature\n",
        "DESCRIPTION:\n",
        "  A test feature\n",
        "CL: http://cl/123\n",
        "STATUS: Drafted\n",
    ]

    result = _apply_parent_update(lines, "Test Feature", "NewParent")
    assert "PARENT: NewParent\n" in result
    # PARENT should be added before CL
    assert result.index("PARENT: NewParent") < result.index("CL:")


def test_apply_parent_update_to_none_removes_field() -> None:
    """Test that setting PARENT to None removes the field."""
    lines = [
        "NAME: Test Feature\n",
        "DESCRIPTION:\n",
        "  A test feature\n",
        "PARENT: OldParent\n",
        "CL: http://cl/123\n",
        "STATUS: Drafted\n",
    ]

    result = _apply_parent_update(lines, "Test Feature", None)
    assert "PARENT:" not in result


def test_apply_parent_update_wrong_changespec_unchanged() -> None:
    """Test that other ChangeSpecs are not affected."""
    lines = [
        "NAME: Feature A\n",
        "DESCRIPTION:\n",
        "  First feature\n",
        "PARENT: ParentA\n",
        "STATUS: Drafted\n",
        "\n",
        "NAME: Feature B\n",
        "DESCRIPTION:\n",
        "  Second feature\n",
        "PARENT: ParentB\n",
        "STATUS: Mailed\n",
    ]

    result = _apply_parent_update(lines, "Feature A", "NewParentA")
    assert "PARENT: NewParentA\n" in result
    assert "PARENT: ParentB\n" in result


# === Tests for update_changespec_parent_atomic ===


def test_update_changespec_parent_atomic_success() -> None:
    """Test successful atomic PARENT update."""
    project_file = _create_test_project_file_with_parent(
        status="Drafted", parent="OldParent"
    )

    try:
        update_changespec_parent_atomic(project_file, "Test Feature", "NewParent")

        with open(project_file, encoding="utf-8") as f:
            content = f.read()
            assert "PARENT: NewParent" in content
            assert "PARENT: OldParent" not in content

    finally:
        Path(project_file).unlink()


def test_update_changespec_parent_atomic_add_parent() -> None:
    """Test adding PARENT when it doesn't exist."""
    project_file = _create_test_project_file_with_parent(status="Drafted", parent=None)

    try:
        update_changespec_parent_atomic(project_file, "Test Feature", "NewParent")

        with open(project_file, encoding="utf-8") as f:
            content = f.read()
            assert "PARENT: NewParent" in content

    finally:
        Path(project_file).unlink()


def test_update_changespec_parent_atomic_remove_parent() -> None:
    """Test removing PARENT field."""
    project_file = _create_test_project_file_with_parent(
        status="Drafted", parent="OldParent"
    )

    try:
        update_changespec_parent_atomic(project_file, "Test Feature", None)

        with open(project_file, encoding="utf-8") as f:
            content = f.read()
            assert "PARENT:" not in content

    finally:
        Path(project_file).unlink()


# === Tests for get_eligible_parents_in_project ===


def test_get_eligible_parents_filters_by_status() -> None:
    """Test that only WIP, Drafted, and Mailed statuses are eligible."""
    project_file = _create_multi_changespec_file()

    try:
        # From Feature A's perspective
        eligible = get_eligible_parents_in_project(project_file, "Feature A")

        # Should include Feature B (Drafted), Feature C (Mailed)
        # Should NOT include Feature D (Submitted), Feature E (Reverted)
        names = [name for name, status in eligible]

        assert "Feature B" in names
        assert "Feature C" in names
        assert "Feature D" not in names
        assert "Feature E" not in names

    finally:
        Path(project_file).unlink()


def test_get_eligible_parents_excludes_self() -> None:
    """Test that the current ChangeSpec is excluded from eligible parents."""
    project_file = _create_multi_changespec_file()

    try:
        eligible = get_eligible_parents_in_project(project_file, "Feature A")
        names = [name for name, status in eligible]

        assert "Feature A" not in names

    finally:
        Path(project_file).unlink()


def test_get_eligible_parents_returns_status() -> None:
    """Test that status is included in the result tuples."""
    project_file = _create_multi_changespec_file()

    try:
        eligible = get_eligible_parents_in_project(project_file, "Feature D")
        eligible_dict = dict(eligible)

        assert eligible_dict.get("Feature A") == "WIP"
        assert eligible_dict.get("Feature B") == "Drafted"
        assert eligible_dict.get("Feature C") == "Mailed"

    finally:
        Path(project_file).unlink()


def test_get_eligible_parents_empty_when_no_matches() -> None:
    """Test that empty list is returned when no eligible parents exist."""
    # Create a file with only terminal status ChangeSpecs
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("""# Test Project

NAME: Feature A
DESCRIPTION:
  Only one feature
STATUS: Submitted

---
""")
        project_file = f.name

    try:
        eligible = get_eligible_parents_in_project(project_file, "Feature A")
        assert eligible == []

    finally:
        Path(project_file).unlink()


def test_get_eligible_parents_handles_ready_to_mail_suffix() -> None:
    """Test that READY TO MAIL suffix is handled correctly."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".gp") as f:
        f.write("""# Test Project

NAME: Feature A
DESCRIPTION:
  First feature
STATUS: Drafted - (!: READY TO MAIL)

---

NAME: Feature B
DESCRIPTION:
  Second feature
STATUS: WIP

---
""")
        project_file = f.name

    try:
        eligible = get_eligible_parents_in_project(project_file, "Feature B")
        eligible_dict = dict(eligible)

        # Feature A should be eligible with base status "Drafted"
        assert "Feature A" in eligible_dict
        assert eligible_dict["Feature A"] == "Drafted"

    finally:
        Path(project_file).unlink()
