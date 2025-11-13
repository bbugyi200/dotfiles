"""Workflow-specific operations for ChangeSpecs."""

import os
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import transition_changespec_status

from .changespec import ChangeSpec, find_all_changespecs

# Import workflow runners from workflows subpackage
from .workflows import (
    run_crs_workflow,
    run_fix_tests_workflow,
    run_qa_workflow,
    run_tdd_feature_workflow,
)

# Re-export workflow runners for backward compatibility
__all__ = [
    "run_crs_workflow",
    "run_fix_tests_workflow",
    "run_qa_workflow",
    "run_tdd_feature_workflow",
    "unblock_child_changespecs",
]


def unblock_child_changespecs(
    parent_changespec: ChangeSpec, console: Console | None = None
) -> int:
    """Unblock child ChangeSpecs when parent is moved to Pre-Mailed.

    When a ChangeSpec is moved to "Pre-Mailed", any ChangeSpecs that:
    - Have STATUS of "Blocked" or "Blocked"
    - Have PARENT field equal to the NAME of the parent ChangeSpec

    Will automatically have their STATUS changed to the corresponding Unstarted status:
    - "Blocked" -> "Unstarted"
    - "Blocked" -> "Unstarted"

    Args:
        parent_changespec: The ChangeSpec that was moved to Pre-Mailed
        console: Optional Rich Console for output

    Returns:
        Number of child ChangeSpecs that were unblocked
    """
    # Find all ChangeSpecs
    all_changespecs = find_all_changespecs()

    # Filter for blocked children of this parent
    blocked_children = [
        cs
        for cs in all_changespecs
        if cs.status in ["Blocked", "Blocked"] and cs.parent == parent_changespec.name
    ]

    if not blocked_children:
        return 0

    # Unblock each child
    unblocked_count = 0
    for child in blocked_children:
        # Determine the new status
        new_status = "Unstarted" if child.status == "Blocked" else "Unstarted"

        # Update the status
        success, old_status, error_msg = transition_changespec_status(
            child.file_path,
            child.name,
            new_status,
            validate=False,  # Don't validate - we know this transition is valid
        )

        if success:
            unblocked_count += 1
            if console:
                console.print(
                    f"[green]Unblocked child ChangeSpec '{child.name}': {old_status} → {new_status}[/green]"
                )
        else:
            if console:
                console.print(
                    f"[yellow]Warning: Failed to unblock '{child.name}': {error_msg}[/yellow]"
                )

    return unblocked_count
