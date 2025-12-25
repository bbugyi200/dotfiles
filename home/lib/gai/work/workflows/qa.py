"""QA workflow runner."""

import os
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from qa_workflow import QaWorkflow
from running_field import (
    claim_workspace,
    get_first_available_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from shared_utils import (
    execute_change_action,
    generate_workflow_tag,
    prompt_for_change_action,
)

from ..changespec import ChangeSpec
from ..operations import update_to_changespec


def run_qa_workflow(changespec: ChangeSpec, console: Console) -> bool:
    """Run qa workflow for 'Drafted' or 'Mailed' status.

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
        "qa",
        changespec.name,
    )
    if not claim_success:
        console.print("[red]Error: Failed to claim workspace[/red]")
        return False

    if workspace_suffix:
        console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")

    # Now update to the changespec NAME (cd and bb_hg_update to the CL being QA'd)
    success, error_msg = update_to_changespec(
        changespec, console, revision=changespec.name, workspace_dir=workspace_dir
    )
    if not success:
        console.print(f"[red]Error: {error_msg}[/red]")
        # Release workspace since we failed before running the workflow
        release_workspace(changespec.file_path, workspace_num, "qa", changespec.name)
        return False

    # Copy context files from ~/.gai/projects/<project>/context/ to target_dir/.gai/context/<project>
    target_dir = workspace_dir
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

    # Track whether workflow succeeded
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
            console.print("[red]QA workflow failed[/red]")
            return False

        # Prompt user for action on changes (use propose mode)
        result = prompt_for_change_action(console, target_dir, propose_mode=True)
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

        console.print("[green]QA workflow completed successfully![/green]")
        workflow_succeeded = True

    except KeyboardInterrupt:
        console.print("\n[yellow]QA workflow interrupted (Ctrl+C)[/yellow]")
        workflow_succeeded = False
    except Exception as e:
        console.print(f"[red]QA workflow crashed: {str(e)}[/red]")
        workflow_succeeded = False
    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Always release the workspace when done
        release_workspace(changespec.file_path, workspace_num, "qa", changespec.name)

    return workflow_succeeded
