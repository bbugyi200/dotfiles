"""QA workflow runner."""

import os
import subprocess
import sys

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from qa_workflow import QaWorkflow
from shared_utils import generate_workflow_tag
from status_state_machine import transition_changespec_status

from ..changespec import ChangeSpec
from ..operations import update_to_changespec


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

    # Update to the changespec NAME (cd and bb_hg_update to the CL being QA'd)
    success, error_msg = update_to_changespec(
        changespec, console, revision=changespec.name
    )
    if not success:
        console.print(f"[red]Error: {error_msg}[/red]")
        return False

    # Get target directory for running workflow
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")
    # These should be set since update_to_changespec already validated them
    assert goog_cloud_dir is not None
    assert goog_src_dir_base is not None
    target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    # Copy context files from ~/.gai/context/<project> to target_dir/.gai/context/<project>
    source_context_dir = os.path.expanduser(f"~/.gai/context/{project_basename}")
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

    # Save original status and update to "Running QA..."
    original_status = changespec.status
    success, old_status, error_msg = transition_changespec_status(
        changespec.file_path,
        changespec.name,
        "Running QA...",
        validate=True,
    )
    if not success:
        console.print(f"[red]Error updating status: {error_msg}[/red]")
        return False

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
            workflow_succeeded = False
            return False
        except FileNotFoundError:
            console.print("[red]hg command not found[/red]")
            workflow_succeeded = False
            return False

        if not has_changes:
            # No changes to show - just show warning and prompt to continue
            console.print(
                "\n[yellow]Warning: QA workflow completed but no changes were made.[/yellow]"
            )
            console.print("[dim]Press enter to continue...[/dim]", end="")
            input()
            workflow_succeeded = False
            return False

        # Show diff with color
        console.print("\n[cyan]Showing changes from QA workflow...[/cyan]\n")
        try:
            subprocess.run(
                ["hg", "diff", "--color=always"],
                cwd=target_dir,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]hg diff failed (exit code {e.returncode})[/red]")
            workflow_succeeded = False
            return False
        except FileNotFoundError:
            console.print("[red]hg command not found[/red]")
            workflow_succeeded = False
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
                    ["hg", "amend", "-n", f"@AI({workflow_tag}) [qa]"],
                    cwd=target_dir,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]hg amend failed (exit code {e.returncode})[/red]")
                workflow_succeeded = False
                return False
            except FileNotFoundError:
                console.print("[red]hg command not found[/red]")
                workflow_succeeded = False
                return False

            # Run hg evolve
            console.print("[cyan]Running hg evolve...[/cyan]")
            try:
                subprocess.run(
                    ["hg", "evolve"],
                    cwd=target_dir,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]hg evolve failed (exit code {e.returncode})[/red]")
                workflow_succeeded = False
                return False
            except FileNotFoundError:
                console.print("[red]hg command not found[/red]")
                workflow_succeeded = False
                return False

            # Upload to Critique
            console.print("[cyan]Uploading to Critique...[/cyan]")
            try:
                subprocess.run(
                    ["hg", "upload", "tree"],
                    cwd=target_dir,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[red]hg upload tree failed (exit code {e.returncode})[/red]"
                )
                workflow_succeeded = False
                return False
            except FileNotFoundError:
                console.print("[red]hg command not found[/red]")
                workflow_succeeded = False
                return False

            # Revert status to original
            success, _, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                original_status,
                validate=True,
            )
            if success:
                console.print("[green]QA workflow completed successfully![/green]")
            else:
                console.print(
                    f"[yellow]Warning: Could not update status to '{original_status}': {error_msg}[/yellow]"
                )

        elif user_input == "n":
            # Reject changes - just return
            console.print(
                "[yellow]Changes rejected. Returning to ChangeSpec view.[/yellow]"
            )
            workflow_succeeded = False
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
                workflow_succeeded = False
                return False
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[red]hg update --clean failed (exit code {e.returncode})[/red]"
                )
                workflow_succeeded = False
                return False
            except FileNotFoundError:
                console.print("[red]hg command not found[/red]")
                workflow_succeeded = False
                return False

        else:
            console.print(f"[red]Invalid option: {user_input}[/red]")
            workflow_succeeded = False
            return False

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

        # Revert status to original if workflow didn't succeed
        if not workflow_succeeded:
            success, _, error_msg = transition_changespec_status(
                changespec.file_path,
                changespec.name,
                original_status,
                validate=True,
            )
            if not success:
                console.print(
                    f"[red]Critical: Failed to revert status: {error_msg}[/red]"
                )

    return workflow_succeeded
