"""CRS workflow runner."""

import os
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from change_actions import (
    execute_change_action,
    prompt_for_change_action,
)
from chat_history import save_chat_history
from crs_workflow import CrsWorkflow
from gai_utils import generate_timestamp, shorten_path
from running_field import (
    claim_workspace,
    get_first_available_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)

from ..changespec import ChangeSpec
from ..comments import set_comment_suffix
from ..operations import update_to_changespec


def run_crs_workflow(
    changespec: ChangeSpec,
    console: Console,
    comments_file: str | None = None,
    comment_reviewer: str = "critique",
) -> bool:
    """Run crs workflow to address Critique comments.

    Args:
        changespec: The ChangeSpec to run the workflow for
        console: Rich console for output
        comments_file: Optional path to comments JSON file from COMMENTS field.
            If provided, use this file instead of running critique_comments.
        comment_reviewer: The reviewer type for the COMMENTS entry (e.g., "critique" or "critique:me").
            Used to update the correct suffix when CRS completes.

    Returns:
        True if workflow completed successfully, False otherwise
    """
    # Find first available workspace and claim it
    workspace_num = get_first_available_workspace(changespec.file_path)
    workspace_dir, workspace_suffix = get_workspace_directory_for_num(
        workspace_num, changespec.project_basename
    )

    # Claim the workspace FIRST to reserve it before doing any work
    claim_success = claim_workspace(
        changespec.file_path,
        workspace_num,
        "crs",
        os.getpid(),
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
            f"~/.gai/projects/{changespec.project_basename}/context/"
        )

        # Set timestamp suffix on comment entry to indicate CRS is running
        crs_start_timestamp = generate_timestamp()
        if changespec.comments:
            set_comment_suffix(
                changespec.file_path,
                changespec.name,
                comment_reviewer,
                crs_start_timestamp,
                changespec.comments,
                suffix_type="running_agent",
            )

        # Run the CRS workflow
        console.print("[cyan]Running CRS workflow...[/cyan]")
        workflow = CrsWorkflow(
            context_file_directory=context_file_directory,
            comments_file=comments_file,
            timestamp=crs_start_timestamp,
        )
        workflow_succeeded = workflow.run()

        if not workflow_succeeded:
            console.print("[red]CRS workflow failed[/red]")
            # Set suffix to indicate unresolved comments
            if changespec.comments:
                set_comment_suffix(
                    changespec.file_path,
                    changespec.name,
                    comment_reviewer,
                    "Unresolved Critique Comments",
                    changespec.comments,
                )
            return False

        # Read CRS response and save as a proper chat file
        crs_response = ""
        if workflow.response_path and os.path.exists(workflow.response_path):
            with open(workflow.response_path, encoding="utf-8") as f:
                crs_response = f.read()

        # Build a prompt description that references the comments file
        comments_ref = shorten_path(comments_file) if comments_file else "comments"
        prompt_desc = f"CRS workflow processing: {comments_ref}"

        # Save chat history as ~/.gai/chats/*.md file
        chat_path = save_chat_history(
            prompt=prompt_desc,
            response=crs_response,
            workflow="crs",
            timestamp=crs_start_timestamp,
        )

        # Build workflow name with comments file reference for the amend note
        workflow_name = f"crs ({comments_ref})" if comments_file else "crs"

        # Prompt user for action on changes (creates proposal first)
        result = prompt_for_change_action(
            console,
            target_dir,
            workflow_name=workflow_name,
            chat_path=chat_path,
        )
        if result is None:
            # No changes to show - just show warning and prompt to continue
            console.print(
                "\n[yellow]Warning: CRS workflow completed but no changes were made.[/yellow]"
            )
            console.print("[dim]Press enter to continue...[/dim]", end="")
            input()
            # Set suffix to indicate unresolved comments
            if changespec.comments:
                set_comment_suffix(
                    changespec.file_path,
                    changespec.name,
                    comment_reviewer,
                    "Unresolved Critique Comments",
                    changespec.comments,
                )
            return False

        action, proposal_id = result

        # Handle reject (proposal stays in HISTORY)
        if action == "reject":
            console.print("[yellow]Changes rejected. Proposal saved.[/yellow]")
            # Set suffix to indicate unresolved comments
            if changespec.comments:
                set_comment_suffix(
                    changespec.file_path,
                    changespec.name,
                    comment_reviewer,
                    "Unresolved Critique Comments",
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
            # Set suffix to indicate unresolved comments on failure
            if changespec.comments:
                set_comment_suffix(
                    changespec.file_path,
                    changespec.name,
                    comment_reviewer,
                    "Unresolved Critique Comments",
                    changespec.comments,
                )
            return False

        # Set suffix on success - gai axe will remove entry when no more comments
        if changespec.comments:
            set_comment_suffix(
                changespec.file_path,
                changespec.name,
                comment_reviewer,
                "Unresolved Critique Comments",
                changespec.comments,
            )

        console.print("[green]CRS workflow completed successfully![/green]")
        return True

    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Always release the workspace when done
        release_workspace(changespec.file_path, workspace_num, "crs", changespec.name)
