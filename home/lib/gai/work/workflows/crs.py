"""CRS workflow runner."""

import os
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crs_workflow import CrsWorkflow
from shared_utils import (
    execute_change_action,
    generate_workflow_tag,
    prompt_for_change_action,
)
from status_state_machine import transition_changespec_status

from ..changespec import ChangeSpec, find_all_changespecs
from ..commit_ops import run_bb_hg_upload
from ..operations import get_workspace_directory, update_to_changespec


def run_crs_workflow(changespec: ChangeSpec, console: Console) -> bool:
    """Run crs workflow for 'Mailed' status.

    Args:
        changespec: The ChangeSpec to run the workflow for
        console: Rich console for output

    Returns:
        True if workflow completed successfully, False otherwise
    """
    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Determine which workspace directory to use
    all_changespecs = find_all_changespecs()
    workspace_dir, workspace_suffix = get_workspace_directory(
        changespec, all_changespecs
    )

    # Use the determined workspace directory
    target_dir = workspace_dir

    # Update STATUS to "Making Change Requests..." FIRST to reserve the workspace
    # This must happen before update_to_changespec to prevent race conditions
    # Add workspace suffix if using a workspace share
    status_text = "Making Change Requests..."
    if workspace_suffix:
        status_text = f"{status_text} ({workspace_suffix})"
        console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")

    success, old_status, error_msg = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        status_text,
        validate=True,
    )
    if not success:
        console.print(f"[red]Error updating status: {error_msg}[/red]")
        return False

    # Now update to the changespec NAME (cd and bb_hg_update to the branch)
    success, error_msg = update_to_changespec(
        changespec, console, revision=changespec.name, workspace_dir=workspace_dir
    )
    if not success:
        console.print(f"[red]Error: {error_msg}[/red]")
        # Revert status since we failed before running the workflow
        if old_status:
            transition_changespec_status(
                changespec.file_path, changespec.name, old_status, validate=True
            )
        return False

    # Save current directory to restore later
    original_dir = os.getcwd()

    try:
        # Change to target directory BEFORE running workflow
        # (this ensures the workflow runs in the correct directory)
        os.chdir(target_dir)

        # Set context file directory to ~/.gai/projects/<project>/context/
        # (CrsWorkflow will copy these files to local bb/gai/context/ directory)
        context_file_directory = os.path.expanduser(
            f"~/.gai/projects/{project_basename}/context/"
        )

        # Run the CRS workflow
        console.print("[cyan]Running CRS workflow...[/cyan]")
        workflow = CrsWorkflow(context_file_directory=context_file_directory)
        workflow_succeeded = workflow.run()

        if not workflow_succeeded:
            console.print("[red]CRS workflow failed[/red]")
            return False

        # Prompt user for action on changes
        result = prompt_for_change_action(console, target_dir)
        if result is None:
            # No changes to show - just show warning and prompt to continue
            console.print(
                "\n[yellow]Warning: CRS workflow completed but no changes were made.[/yellow]"
            )
            console.print("[dim]Press enter to continue...[/dim]", end="")
            input()
            return False

        action, action_args = result

        # Handle reject early - no need to execute anything
        if action == "reject":
            console.print(
                "[yellow]Changes rejected. Returning to ChangeSpec view.[/yellow]"
            )
            return False

        # Generate workflow tag for amend
        workflow_tag = generate_workflow_tag()

        # Execute the action
        success = execute_change_action(
            action=action,
            action_args=action_args,
            console=console,
            target_dir=target_dir,
            workflow_tag=workflow_tag,
            workflow_name="crs",
        )

        if not success:
            return False

        # For amend action, also upload to Critique
        if action == "amend":
            upload_success, error_msg = run_bb_hg_upload(target_dir, console)
            if not upload_success:
                console.print(f"[red]{error_msg}[/red]")
                return False

        console.print("[green]CRS workflow completed successfully![/green]")
        return True

    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Always revert status back to original status
        # (status transitions to "Mailed" should happen via periodic checks
        # or manually by the user, not automatically after CRS workflow)
        if old_status:
            revert_success, _, revert_error = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                old_status,
                validate=True,
            )
            if not revert_success:
                console.print(
                    f"[red]Critical: Failed to revert status: {revert_error}[/red]"
                )
