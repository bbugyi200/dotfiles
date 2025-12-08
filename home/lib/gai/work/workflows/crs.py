"""CRS workflow runner."""

import os
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crs_workflow import CrsWorkflow
from shared_utils import generate_workflow_tag
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

        # Check if there are any changes to show
        try:
            result = subprocess.run(
                ["hg", "diff"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            has_changes = bool(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            console.print(f"[red]hg diff failed (exit code {e.returncode})[/red]")
            return False
        except FileNotFoundError:
            console.print("[red]hg command not found[/red]")
            return False

        if not has_changes:
            # No changes to show - just show warning and prompt to continue
            console.print(
                "\n[yellow]Warning: CRS workflow completed but no changes were made.[/yellow]"
            )
            console.print("[dim]Press enter to continue...[/dim]", end="")
            input()
            return False

        # Show diff with color
        console.print("\n[cyan]Showing changes from CRS workflow...[/cyan]\n")
        try:
            subprocess.run(
                ["hg", "diff", "--color=always"],
                cwd=target_dir,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]hg diff failed (exit code {e.returncode})[/red]")
            return False
        except FileNotFoundError:
            console.print("[red]hg command not found[/red]")
            return False

        # Prompt user for action
        console.print(
            "\n[cyan]Accept changes (y), reject changes (n), or purge changes (x)?[/cyan] ",
            end="",
        )
        user_input = input().strip().lower()

        if user_input == "y":
            # Generate workflow tag for the commit message
            workflow_tag = generate_workflow_tag()

            # Amend the commit with AI tag
            console.print("[cyan]Amending commit with AI tag...[/cyan]")
            try:
                subprocess.run(
                    ["hg", "amend", "-n", f"@AI({workflow_tag}) [crs]"],
                    cwd=target_dir,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]hg amend failed (exit code {e.returncode})[/red]")
                return False
            except FileNotFoundError:
                console.print("[red]hg command not found[/red]")
                return False

            # Upload to Critique
            success, error_msg = run_bb_hg_upload(target_dir, console)
            if not success:
                console.print(f"[red]{error_msg}[/red]")
                return False

            console.print("[green]CRS workflow completed successfully![/green]")
            return True

        elif user_input == "n":
            # Reject changes - just return
            console.print(
                "[yellow]Changes rejected. Returning to ChangeSpec view.[/yellow]"
            )
            return False

        elif user_input == "x":
            # Purge changes
            console.print("[cyan]Purging changes...[/cyan]")
            try:
                subprocess.run(
                    ["hg", "update", "--clean", "."],
                    cwd=target_dir,
                    check=True,
                )
                console.print("[green]Changes purged successfully.[/green]")
                return False
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[red]hg update --clean failed (exit code {e.returncode})[/red]"
                )
                return False
            except FileNotFoundError:
                console.print("[red]hg command not found[/red]")
                return False

        else:
            console.print(f"[red]Invalid option: {user_input}[/red]")
            return False

    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Revert STATUS back to original status
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
