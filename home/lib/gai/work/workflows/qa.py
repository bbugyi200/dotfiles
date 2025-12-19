"""QA workflow runner."""

import os
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from qa_workflow import QaWorkflow
from shared_utils import (
    execute_change_action,
    generate_workflow_tag,
    prompt_for_change_action,
)
from status_state_machine import transition_changespec_status

from ..changespec import ChangeSpec, find_all_changespecs
from ..commit_ops import run_bb_hg_upload
from ..operations import get_workspace_directory, update_to_changespec


def run_qa_workflow(changespec: ChangeSpec, console: Console) -> bool:
    """Run qa workflow for 'Pre-Mailed' or 'Mailed' status.

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

    # Update status to "Running QA..." FIRST to reserve the workspace
    # This must happen before update_to_changespec to prevent race conditions
    # Add workspace suffix if using a workspace share
    status_running = "Running QA..."
    if workspace_suffix:
        status_running_with_suffix = f"{status_running} ({workspace_suffix})"
        console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")
    else:
        status_running_with_suffix = status_running

    success, old_status, error_msg = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        status_running_with_suffix,
        validate=True,
    )
    if not success:
        console.print(f"[red]Error updating status: {error_msg}[/red]")
        return False

    # Now update to the changespec NAME (cd and bb_hg_update to the CL being QA'd)
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

    # Copy context files from ~/.gai/projects/<project>/context/ to target_dir/.gai/context/<project>
    source_context_dir = os.path.expanduser(
        f"~/.gai/projects/{project_basename}/context/"
    )
    target_context_dir = os.path.join(target_dir, ".gai", "context", project_basename)

    if os.path.exists(source_context_dir) and os.path.isdir(source_context_dir):
        import shutil

        os.makedirs(os.path.dirname(target_context_dir), exist_ok=True)
        if os.path.exists(target_context_dir):
            shutil.rmtree(target_context_dir)
        shutil.copytree(source_context_dir, target_context_dir)

    # Set context file directory to the copied location
    context_file_directory = (
        target_context_dir if os.path.exists(target_context_dir) else None
    )

    # Track whether workflow succeeded for proper rollback
    workflow_succeeded = False

    # Save current directory to restore later
    original_dir = os.getcwd()

    try:
        # Change to target directory before running workflow
        os.chdir(target_dir)

        # Run the QA workflow
        console.print("[cyan]Running qa workflow...[/cyan]")
        workflow = QaWorkflow(context_file_directory=context_file_directory)
        workflow_succeeded = workflow.run()

        if not workflow_succeeded:
            console.print("[red]QA workflow failed - reverting status[/red]")
            return False

        # Prompt user for action on changes
        result = prompt_for_change_action(console, target_dir)
        if result is None:
            # No changes to show - just show warning and prompt to continue
            console.print(
                "\n[yellow]Warning: QA workflow completed but no changes were made.[/yellow]"
            )
            console.print("[dim]Press enter to continue...[/dim]", end="")
            input()
            workflow_succeeded = False
            return False

        action, action_args = result

        # Handle reject early - no need to execute anything
        if action == "reject":
            console.print(
                "[yellow]Changes rejected. Returning to ChangeSpec view.[/yellow]"
            )
            workflow_succeeded = False
            return False

        # Generate workflow tag for amend
        workflow_tag = generate_workflow_tag()

        # Execute the action
        action_success = execute_change_action(
            action=action,
            action_args=action_args,
            console=console,
            target_dir=target_dir,
            workflow_tag=workflow_tag,
            workflow_name="qa",
        )

        if not action_success:
            workflow_succeeded = False
            return False

        # For amend action, also upload to Critique
        if action == "amend":
            upload_success, error_msg = run_bb_hg_upload(target_dir, console)
            if not upload_success:
                console.print(f"[red]{error_msg}[/red]")
                workflow_succeeded = False
                return False

        # Transition status to Pre-Mailed on success
        if action in ("amend", "commit"):
            success, _, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "Pre-Mailed",
                validate=True,
            )
            if success:
                console.print("[green]QA workflow completed successfully![/green]")
            else:
                console.print(
                    f"[yellow]Warning: Could not update status to 'Pre-Mailed': {error_msg}[/yellow]"
                )

    except KeyboardInterrupt:
        console.print(
            "\n[yellow]QA workflow interrupted (Ctrl+C) - reverting status[/yellow]"
        )
        workflow_succeeded = False
    except Exception as e:
        console.print(f"[red]QA workflow crashed: {str(e)} - reverting status[/red]")
        workflow_succeeded = False
    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Revert status to "Needs QA" if workflow didn't succeed
        if not workflow_succeeded:
            success, _, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                "Needs QA",
                validate=True,
            )
            if not success:
                console.print(
                    f"[red]Critical: Failed to revert status: {error_msg}[/red]"
                )

    return workflow_succeeded
