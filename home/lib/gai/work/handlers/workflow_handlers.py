"""Handler functions for workflow-related operations in the work subcommand."""

import os
import sys
from typing import TYPE_CHECKING

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from new_ez_feature_workflow.main import NewEzFeatureWorkflow
from new_failing_tests_workflow.main import NewFailingTestWorkflow
from status_state_machine import transition_changespec_status
from workflow_base import BaseWorkflow

from ..changespec import ChangeSpec, find_all_changespecs
from ..commit_ops import run_bb_hg_commit_and_update_cl
from ..operations import (
    extract_changespec_text,
    get_workspace_directory,
    update_to_changespec,
)
from ..workflow_ops import (
    run_crs_workflow,
    run_fix_tests_workflow,
    run_qa_workflow,
    run_tdd_feature_workflow,
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
    if selected_workflow == "new-tdd-feature":
        return handle_run_tdd_feature_workflow(
            self, changespec, changespecs, current_idx
        )
    elif selected_workflow == "qa":
        return handle_run_qa_workflow(self, changespec, changespecs, current_idx)
    elif selected_workflow == "fix-tests":
        return handle_run_fix_tests_workflow(self, changespec, changespecs, current_idx)
    elif selected_workflow == "crs":
        return handle_run_crs_workflow(self, changespec, changespecs, current_idx)
    elif selected_workflow == "new-failing-tests":
        # Continue with the new-failing-tests workflow logic below
        pass
    elif selected_workflow == "new-ez-feature":
        # Continue with the new-ez-feature workflow logic below
        pass
    else:
        self.console.print(f"[red]Unknown workflow: {selected_workflow}[/red]")
        return changespecs, current_idx

    # Handle new-failing-tests and new-ez-feature workflows
    # (the original logic below continues here)

    # Determine which workflow to run based on selected workflow
    is_tdd_workflow = selected_workflow == "new-failing-tests"

    # Extract project basename and changespec text
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]
    changespec_text = extract_changespec_text(
        changespec.file_path, changespec.name, self.console
    )

    if not changespec_text:
        self.console.print("[red]Error: Could not extract ChangeSpec text[/red]")
        return changespecs, current_idx

    # Determine which workspace directory to use
    all_changespecs = find_all_changespecs()
    workspace_dir, workspace_suffix = get_workspace_directory(
        changespec, all_changespecs
    )

    # Update to the changespec (cd and bb_hg_update)
    success, error_msg = update_to_changespec(
        changespec, self.console, workspace_dir=workspace_dir
    )
    if not success:
        self.console.print(f"[red]Error: {error_msg}[/red]")
        return changespecs, current_idx

    # Use the determined workspace directory
    target_dir = workspace_dir

    # Set design docs directory to ~/.gai/projects/<project>/context/
    design_docs_dir = os.path.expanduser(f"~/.gai/projects/{project_basename}/context/")

    # Update STATUS based on workflow type
    # The workflow type is determined by the presence of TEST TARGETS in the ChangeSpec
    if is_tdd_workflow:
        status_creating = "Creating TDD CL..."
        status_final = "TDD CL Created"
        workflow_name = "new-failing-tests"
    else:
        status_creating = "Creating EZ CL..."
        status_final = "Pre-Mailed"
        workflow_name = "new-ez-feature"

    # Add workspace suffix to status if using a workspace share
    if workspace_suffix:
        status_creating_with_suffix = f"{status_creating} ({workspace_suffix})"
        self.console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")
    else:
        status_creating_with_suffix = status_creating

    success, old_status, error_msg = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        status_creating_with_suffix,
        validate=True,
    )
    if not success:
        self.console.print(f"[red]Error updating status: {error_msg}[/red]")
        return changespecs, current_idx

    # Track whether workflow succeeded for proper rollback
    workflow_succeeded = False

    # Save current directory to restore later
    original_dir = os.getcwd()

    try:
        # Change to target directory before running workflow
        os.chdir(target_dir)

        # Run the appropriate workflow
        self.console.print(f"[cyan]Running {workflow_name} workflow...[/cyan]")
        workflow: BaseWorkflow
        if is_tdd_workflow:
            # Extract test targets from changespec for TDD workflow
            test_targets = changespec.test_targets if changespec.test_targets else []
            workflow = NewFailingTestWorkflow(
                project_name=project_basename,
                changespec_text=changespec_text,
                test_targets=test_targets,
                context_file_directory=design_docs_dir,
                guidance=changespec.kickstart,
            )
        else:
            workflow = NewEzFeatureWorkflow(
                project_name=project_basename,
                design_docs_dir=design_docs_dir,
                changespec_text=changespec_text,
                context_file_directory=design_docs_dir,
                guidance=changespec.kickstart,
            )
        workflow_succeeded = workflow.run()

        if workflow_succeeded:
            # Run bb_hg_commit to create commit and update CL field
            self.console.print(
                "[cyan]Creating Mercurial commit with bb_hg_commit...[/cyan]"
            )
            success, error_msg = run_bb_hg_commit_and_update_cl(
                changespec, self.console
            )
            if not success:
                self.console.print(
                    f"[red]Error: Failed to create commit: {error_msg}[/red]"
                )
                # Fail the workflow and trigger status rollback
                workflow_succeeded = False

        if workflow_succeeded:
            # Update STATUS to final status
            success, _, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                status_final,
                validate=True,
            )
            if success:
                self.console.print("[green]Workflow completed successfully![/green]")
            else:
                self.console.print(
                    f"[yellow]Warning: Could not update status to '{status_final}': {error_msg}[/yellow]"
                )
        else:
            self.console.print("[red]Workflow failed - reverting status[/red]")

    except KeyboardInterrupt:
        self.console.print(
            "\n[yellow]Workflow interrupted (Ctrl+C) - reverting status[/yellow]"
        )
        workflow_succeeded = False
    except Exception as e:
        self.console.print(f"[red]Workflow crashed: {str(e)} - reverting status[/red]")
        workflow_succeeded = False
    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Revert status to "Unstarted" if workflow didn't succeed
        if not workflow_succeeded:
            revert_status = "Unstarted"
            success, _, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                revert_status,
                validate=True,
            )
            if not success:
                self.console.print(
                    f"[red]Critical: Failed to revert status: {error_msg}[/red]"
                )

        # Reload changespecs to reflect updates
        changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx


def handle_run_tdd_feature_workflow(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle running new-tdd-feature workflow for 'TDD CL Created' status.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    # Run the workflow (handles all logic including status transitions)
    run_tdd_feature_workflow(changespec, self.console)

    # Reload changespecs to reflect updates
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

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
