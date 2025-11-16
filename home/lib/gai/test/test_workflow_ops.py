"""Tests for workflow operations."""

from rich.console import Console
from work.changespec import ChangeSpec
from work.workflow_ops import unblock_child_changespecs


def test_unblock_child_changespecs_no_children() -> None:
    """Test that unblock_child_changespecs returns 0 when no children exist."""
    parent_changespec = ChangeSpec(
        name="parent-cs",
        description="Parent changespec",
        parent=None,
        cl="12345",
        status="Pre-Mailed",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
    )

    # Call with a parent that has no children
    count = unblock_child_changespecs(parent_changespec, None)

    # Should return 0 since no children exist
    assert count == 0


def test_unblock_child_changespecs_with_console() -> None:
    """Test that unblock_child_changespecs works with a Console parameter."""
    parent_changespec = ChangeSpec(
        name="parent-cs",
        description="Parent changespec",
        parent=None,
        cl="12345",
        status="Pre-Mailed",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
    )
    console = Console()

    # Call with a console parameter
    count = unblock_child_changespecs(parent_changespec, console)

    # Should still return 0 since no children exist
    assert count == 0


def test_unblock_child_changespecs_different_parent_name() -> None:
    """Test with different parent names to ensure no false matches."""
    parent_changespec1 = ChangeSpec(
        name="parent-one",
        description="First parent",
        parent=None,
        cl="11111",
        status="Pre-Mailed",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
    )
    parent_changespec2 = ChangeSpec(
        name="parent-two",
        description="Second parent",
        parent=None,
        cl="22222",
        status="Pre-Mailed",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=10,
    )

    # Both should return 0
    assert unblock_child_changespecs(parent_changespec1, None) == 0
    assert unblock_child_changespecs(parent_changespec2, None) == 0


def test_unblock_child_changespecs_idempotency() -> None:
    """Test that calling unblock multiple times is safe."""
    parent_changespec = ChangeSpec(
        name="parent-cs",
        description="Parent changespec",
        parent=None,
        cl="12345",
        status="Pre-Mailed",
        test_targets=None,
        kickstart=None,
        file_path="/path/to/project.gp",
        line_number=1,
    )

    # Call multiple times - should be safe
    count1 = unblock_child_changespecs(parent_changespec, None)
    count2 = unblock_child_changespecs(parent_changespec, None)

    assert count1 == 0
    assert count2 == 0
