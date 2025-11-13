"""Handler functions for workflow-related operations in the work subcommand."""

import os
import subprocess
import sys
from typing import TYPE_CHECKING

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from new_ez_feature_workflow.main import NewEzFeatureWorkflow
from new_failing_tests_workflow.main import NewFailingTestWorkflow
from status_state_machine import transition_changespec_status
from workflow_base import BaseWorkflow

from ..changespec import ChangeSpec
from ..commit_ops import run_bb_hg_commit_and_update_cl
from ..field_updates import update_test_targets
from ..operations import extract_changespec_text, update_to_changespec
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

    # Update to the changespec (cd and bb_hg_update)
    success, error_msg = update_to_changespec(changespec, self.console)
    if not success:
        self.console.print(f"[red]Error: {error_msg}[/red]")
        return changespecs, current_idx

    # Get target directory for running workflow
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")
    # These should be set since update_to_changespec already validated them
    assert goog_cloud_dir is not None
    assert goog_src_dir_base is not None
    target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    # Set design docs directory to ~/.gai/context/<project>
    design_docs_dir = os.path.expanduser(f"~/.gai/context/{project_basename}")

    # Update STATUS based on workflow type
    if is_tdd_workflow:
        status_creating = "Creating TDD CL..."
        status_final = "TDD CL Created"
        workflow_name = "new-failing-tests"
    else:
        status_creating = "Creating EZ CL..."
        status_final = "Running TAP Tests"
        workflow_name = "new-ez-feature"

    success, old_status, error_msg = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        status_creating,
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
            workflow = NewFailingTestWorkflow(
                project_name=project_basename,
                changespec_text=changespec_text,
                context_file_directory=design_docs_dir,
            )
        else:
            workflow = NewEzFeatureWorkflow(
                project_name=project_basename,
                design_docs_dir=design_docs_dir,
                changespec_text=changespec_text,
                context_file_directory=design_docs_dir,
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
            # Update TEST TARGETS field for TDD workflow
            if is_tdd_workflow:
                # Extract test_targets from workflow final state
                if hasattr(workflow, "final_state") and workflow.final_state:
                    test_targets = workflow.final_state.get("test_targets")
                    if test_targets and isinstance(test_targets, str):
                        self.console.print(
                            f"[cyan]Updating TEST TARGETS field with: {test_targets}[/cyan]"
                        )
                        success, error_msg = update_test_targets(
                            changespec.file_path, changespec.name, test_targets
                        )
                        if not success:
                            self.console.print(
                                f"[yellow]Warning: Failed to update TEST TARGETS: {error_msg}[/yellow]"
                            )
                        else:
                            self.console.print(
                                "[green]TEST TARGETS field updated successfully![/green]"
                            )
                    else:
                        self.console.print(
                            "[yellow]Warning: Workflow did not provide test_targets to update[/yellow]"
                        )

            # Run bb_hg_presubmit for new-ez-feature workflow
            if not is_tdd_workflow:
                self.console.print("[cyan]Running bb_hg_presubmit...[/cyan]")
                try:
                    subprocess.run(
                        ["bb_hg_presubmit"],
                        cwd=target_dir,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    self.console.print(
                        f"[yellow]Warning: bb_hg_presubmit failed (exit code {e.returncode})[/yellow]"
                    )
                except FileNotFoundError:
                    self.console.print(
                        "[yellow]Warning: bb_hg_presubmit command not found[/yellow]"
                    )
                except Exception as e:
                    self.console.print(
                        f"[yellow]Warning: Error running bb_hg_presubmit: {str(e)}[/yellow]"
                    )

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

        # Revert status to appropriate "Unstarted" variant if workflow didn't succeed
        if not workflow_succeeded:
            revert_status = "Unstarted (TDD)" if is_tdd_workflow else "Unstarted (EZ)"
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
