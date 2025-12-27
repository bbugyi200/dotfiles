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
from ..comments import (
    generate_comments_timestamp,
    set_comment_suffix,
)
from ..operations import update_to_changespec


def run_crs_workflow(
    changespec: ChangeSpec,
    console: Console,
    comments_file: str | None = None,
    comment_reviewer: str = "reviewer",
) -> bool:
    """Run crs workflow to address Critique comments.

    Args:
        changespec: The ChangeSpec to run the workflow for
        console: Rich console for output
        comments_file: Optional path to comments JSON file from COMMENTS field.
            If provided, use this file instead of running critique_comments.
        comment_reviewer: The reviewer type for the COMMENTS entry (e.g., "reviewer" or "author").
            Used to update the correct suffix when CRS completes.

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

        # Set timestamp suffix on comment entry to indicate CRS is running
        crs_start_timestamp = generate_comments_timestamp()
        if changespec.comments:
            set_comment_suffix(
                changespec.file_path,
                changespec.name,
                comment_reviewer,
                crs_start_timestamp,
                changespec.comments,
            )

        # Run the CRS workflow
        console.print("[cyan]Running CRS workflow...[/cyan]")
        workflow = CrsWorkflow(
            context_file_directory=context_file_directory,
            comments_file=comments_file,
        )
        workflow_succeeded = workflow.run()

        if not workflow_succeeded:
            console.print("[red]CRS workflow failed[/red]")
            # Set suffix to "!" to indicate failure
            if changespec.comments:
                set_comment_suffix(
                    changespec.file_path,
                    changespec.name,
                    comment_reviewer,
                    "!",
                    changespec.comments,
                )
            return False

        # Prompt user for action on changes (creates proposal first)
        result = prompt_for_change_action(
            console,
            target_dir,
            workflow_name="crs",
            chat_path=workflow.response_path,
        )
        if result is None:
            # No changes to show - just show warning and prompt to continue
            console.print(
                "\n[yellow]Warning: CRS workflow completed but no changes were made.[/yellow]"
            )
            console.print("[dim]Press enter to continue...[/dim]", end="")
            input()
            # Set suffix to "!" to indicate failure (no changes)
            if changespec.comments:
                set_comment_suffix(
                    changespec.file_path,
                    changespec.name,
                    comment_reviewer,
                    "!",
                    changespec.comments,
                )
            return False

        action, proposal_id = result

        # Handle reject (proposal stays in HISTORY)
        if action == "reject":
            console.print("[yellow]Changes rejected. Proposal saved.[/yellow]")
            # Update suffix to proposal ID if we have one
            if proposal_id and changespec.comments:
                set_comment_suffix(
                    changespec.file_path,
                    changespec.name,
                    comment_reviewer,
                    proposal_id,
                    changespec.comments,
                )
            return False

        # Execute the action (accept or purge)
        success = execute_change_action(
            action=action,
            action_args=proposal_id,
            console=console,
            target_dir=target_dir,
        )

        if not success:
            # Set suffix to "!" on failure
            if changespec.comments:
                set_comment_suffix(
                    changespec.file_path,
                    changespec.name,
                    comment_reviewer,
                    "!",
                    changespec.comments,
                )
            return False

        # Update suffix to proposal ID on success
        if proposal_id and changespec.comments:
            set_comment_suffix(
                changespec.file_path,
                changespec.name,
                comment_reviewer,
                proposal_id,
                changespec.comments,
            )

        console.print("[green]CRS workflow completed successfully![/green]")
        return True

    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Always release the workspace when done
        release_workspace(changespec.file_path, workspace_num, "crs", changespec.name)
