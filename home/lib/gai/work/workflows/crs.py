"""CRS workflow runner."""

import os
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crs_workflow import CrsWorkflow
from running_field import (
    claim_workspace,
    get_first_available_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from shared_utils import (
    execute_change_action,
    prompt_for_change_action,
)

from ..changespec import ChangeSpec
from ..operations import update_to_changespec


def run_crs_workflow(changespec: ChangeSpec, console: Console) -> bool:
    """Run crs workflow for 'Changes Requested' status.

    Args:
        changespec: The ChangeSpec to run the workflow for
        console: Rich console for output

    Returns:
        True if workflow completed successfully, False otherwise
    """
    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Find first available workspace and claim it
    workspace_num = get_first_available_workspace(
        changespec.file_path, project_basename
    )
    workspace_dir, workspace_suffix = get_workspace_directory_for_num(
        workspace_num, project_basename
    )

    # Claim the workspace FIRST to reserve it before doing any work
    claim_success = claim_workspace(
        changespec.file_path,
        workspace_num,
        "crs",
        changespec.name,
    )
    if not claim_success:
        console.print("[red]Error: Failed to claim workspace[/red]")
        return False

    if workspace_suffix:
        console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")

    # Now update to the changespec NAME (cd and bb_hg_update to the branch)
    success, error_msg = update_to_changespec(
        changespec, console, revision=changespec.name, workspace_dir=workspace_dir
    )
    if not success:
        console.print(f"[red]Error: {error_msg}[/red]")
        # Release workspace since we failed before running the workflow
        release_workspace(changespec.file_path, workspace_num, "crs", changespec.name)
        return False

    # Save current directory to restore later
    original_dir = os.getcwd()
    target_dir = workspace_dir

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

        # Prompt user for action on changes (creates proposal first)
        result = prompt_for_change_action(
            console,
            target_dir,
            workflow_name="crs",
        )
        if result is None:
            # No changes to show - just show warning and prompt to continue
            console.print(
                "\n[yellow]Warning: CRS workflow completed but no changes were made.[/yellow]"
            )
            console.print("[dim]Press enter to continue...[/dim]", end="")
            input()
            return False

        action, action_args = result

        # Handle reject (proposal stays in HISTORY)
        if action == "reject":
            console.print("[yellow]Changes rejected. Proposal saved.[/yellow]")
            return False

        # Execute the action (accept or purge)
        success = execute_change_action(
            action=action,
            action_args=action_args,
            console=console,
            target_dir=target_dir,
        )

        if not success:
            return False

        console.print("[green]CRS workflow completed successfully![/green]")
        return True

    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Always release the workspace when done
        release_workspace(changespec.file_path, workspace_num, "crs", changespec.name)
