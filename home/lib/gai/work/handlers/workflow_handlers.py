"""Handler functions for workflow-related operations in the work subcommand."""

import os
import sys
from typing import TYPE_CHECKING

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from ..changespec import ChangeSpec, find_all_changespecs
from ..operations import (
    get_workspace_directory,
    update_to_changespec,
)
from ..workflow_ops import (
    run_crs_workflow,
    run_fix_tests_workflow,
    run_qa_workflow,
)

if TYPE_CHECKING:
    from ..workflow import WorkWorkflow


def handle_run_workflow(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
    workflow_index: int = 0,
) -> tuple[list[ChangeSpec], int]:
    """Handle 'r' (run workflow) action.

    Runs workflow based on available workflows for the ChangeSpec.
    When multiple workflows are available, workflow_index selects which one to run.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index
        workflow_index: Index of workflow to run (default 0)

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    from ..operations import get_available_workflows

    workflows = get_available_workflows(changespec)
    if not workflows:
        self.console.print(
            "[yellow]Run option not available for this ChangeSpec[/yellow]"
        )
        return changespecs, current_idx

    # Validate workflow index
    if workflow_index < 0 or workflow_index >= len(workflows):
        self.console.print(f"[red]Invalid workflow index: {workflow_index + 1}[/red]")
        return changespecs, current_idx

    # Get the selected workflow
    selected_workflow = workflows[workflow_index]

    # Route to the appropriate handler based on workflow name
    if selected_workflow == "qa":
        return handle_run_qa_workflow(self, changespec, changespecs, current_idx)
    elif selected_workflow == "fix-tests":
        return handle_run_fix_tests_workflow(self, changespec, changespecs, current_idx)
    elif selected_workflow == "crs":
        return handle_run_crs_workflow(self, changespec, changespecs, current_idx)
    elif selected_workflow == "presubmit":
        return _handle_run_presubmit_workflow(
            self, changespec, changespecs, current_idx
        )
    else:
        self.console.print(f"[red]Unknown workflow: {selected_workflow}[/red]")
        return changespecs, current_idx


def handle_run_qa_workflow(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle running qa workflow for 'Pre-Mailed' or 'Mailed' status.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    # Run the workflow (handles all logic including status transitions)
    run_qa_workflow(changespec, self.console)

    # Reload changespecs to reflect updates
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx


def handle_run_fix_tests_workflow(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle running fix-tests workflow for 'Failing Tests' status.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    # Run the workflow (handles all logic including status transitions)
    run_fix_tests_workflow(changespec, self.console)

    # Reload changespecs to reflect updates
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx


def handle_run_crs_workflow(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle running crs workflow for 'Mailed' status.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    # Run the workflow (handles all logic)
    run_crs_workflow(changespec, self.console)

    # Reload changespecs to reflect updates
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx


def _handle_run_presubmit_workflow(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle running presubmit workflow for 'Needs Presubmit' status.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    from ..presubmit import run_presubmit

    # Determine which workspace directory to use (for workspace suffix)
    all_changespecs = find_all_changespecs()
    workspace_dir, workspace_suffix = get_workspace_directory(
        changespec, all_changespecs
    )

    # Update to the changespec NAME (cd and bb_hg_update) to checkout the right branch
    success, error_msg = update_to_changespec(
        changespec, self.console, revision=changespec.name, workspace_dir=workspace_dir
    )
    if not success:
        self.console.print(f"[red]Error: {error_msg}[/red]")
        return changespecs, current_idx

    # Run the presubmit workflow (starts background process)
    run_presubmit(changespec, self.console, workspace_suffix)

    # Reload changespecs to reflect updates
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx
