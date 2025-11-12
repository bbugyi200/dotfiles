"""Handler functions for tool-related operations in the work subcommand."""

import os
import subprocess
from typing import TYPE_CHECKING

from ..changespec import ChangeSpec
from ..mail_ops import handle_mail as mail_ops_handle_mail
from ..operations import update_to_changespec

if TYPE_CHECKING:
    from ..workflow import WorkWorkflow


def handle_show_diff(self: "WorkWorkflow", changespec: ChangeSpec) -> None:
    """Handle 'd' (show diff) action.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
    """
    if changespec.cl is None or changespec.cl == "None":
        self.console.print("[yellow]Cannot show diff: CL is not set[/yellow]")
        return

    # Update to the changespec branch (NAME field) to show the diff
    success, error_msg = update_to_changespec(
        changespec, self.console, revision=changespec.name
    )
    if not success:
        self.console.print(f"[red]Error: {error_msg}[/red]")
        return

    # Run branch_diff
    # Get target directory for running branch_diff
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")
    # These should be set since update_to_changespec already validated them
    assert goog_cloud_dir is not None
    assert goog_src_dir_base is not None
    target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    try:
        # Run branch_diff and let it take over the terminal
        subprocess.run(
            ["branch_diff"],
            cwd=target_dir,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        self.console.print(f"[red]branch_diff failed (exit code {e.returncode})[/red]")
    except FileNotFoundError:
        self.console.print("[red]branch_diff command not found[/red]")
    except Exception as e:
        self.console.print(f"[red]Unexpected error running branch_diff: {str(e)}[/red]")


def handle_create_tmux(self: "WorkWorkflow", changespec: ChangeSpec) -> None:
    """Handle 't' (create tmux window) action.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
    """
    if changespec.cl is None or changespec.cl == "None":
        self.console.print("[yellow]Cannot create tmux window: CL is not set[/yellow]")
        return

    if not self._is_in_tmux():
        self.console.print(
            "[yellow]Cannot create tmux window: not in tmux session[/yellow]"
        )
        return

    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Get required environment variables
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

    if not goog_cloud_dir:
        self.console.print(
            "[red]Error: GOOG_CLOUD_DIR environment variable is not set[/red]"
        )
        return
    if not goog_src_dir_base:
        self.console.print(
            "[red]Error: GOOG_SRC_DIR_BASE environment variable is not set[/red]"
        )
        return

    # Build target directory path
    target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    # Build the command to run in the new tmux window
    # cd to the directory, run bb_hg_update, then start a shell
    tmux_cmd = f"cd {target_dir} && bb_hg_update {changespec.name} && exec $SHELL"

    try:
        # Create new tmux window with the project name
        subprocess.run(
            [
                "tmux",
                "new-window",
                "-n",
                project_basename,
                tmux_cmd,
            ],
            check=True,
        )
        self.console.print(f"[green]Created tmux window '{project_basename}'[/green]")
    except subprocess.CalledProcessError as e:
        self.console.print(f"[red]tmux command failed (exit code {e.returncode})[/red]")
    except FileNotFoundError:
        self.console.print("[red]tmux command not found[/red]")
    except Exception as e:
        self.console.print(
            f"[red]Unexpected error creating tmux window: {str(e)}[/red]"
        )


def handle_findreviewers(self: "WorkWorkflow", changespec: ChangeSpec) -> None:
    """Handle 'f' (findreviewers) action.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
    """
    if changespec.status != "Pre-Mailed":
        self.console.print(
            "[yellow]findreviewers option only available for Pre-Mailed ChangeSpecs[/yellow]"
        )
        return

    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Get required environment variables
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

    if not goog_cloud_dir:
        self.console.print(
            "[red]Error: GOOG_CLOUD_DIR environment variable is not set[/red]"
        )
        return
    if not goog_src_dir_base:
        self.console.print(
            "[red]Error: GOOG_SRC_DIR_BASE environment variable is not set[/red]"
        )
        return

    # Build target directory path
    target_dir = os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)

    try:
        # Get the CL number using branch_number command
        result = subprocess.run(
            ["branch_number"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )

        cl_number = result.stdout.strip()
        if not cl_number or not cl_number.isdigit():
            self.console.print(
                f"[red]Error: branch_number returned invalid CL number: {cl_number}[/red]"
            )
            return

        # Run p4 findreviewers command
        self.console.print("[cyan]Running p4 findreviewers...[/cyan]\n")
        result = subprocess.run(
            ["p4", "findreviewers", "-c", cl_number],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )

        # Display the output
        if result.stdout:
            self.console.print(result.stdout)
        else:
            self.console.print("[yellow]No output from p4 findreviewers[/yellow]")

        # Wait for user to press enter before returning
        self.console.print("\n[dim]Press enter to continue...[/dim]", end="")
        input()

    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed (exit code {e.returncode})"
        if e.stderr:
            error_msg += f": {e.stderr.strip()}"
        elif e.stdout:
            error_msg += f": {e.stdout.strip()}"
        self.console.print(f"[red]{error_msg}[/red]")
    except FileNotFoundError as e:
        command_name = str(e).split("'")[1] if "'" in str(e) else "command"
        self.console.print(f"[red]{command_name} command not found[/red]")
    except Exception as e:
        self.console.print(
            f"[red]Unexpected error running findreviewers: {str(e)}[/red]"
        )


def handle_mail(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle 'm' (mail) action.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    if changespec.status != "Pre-Mailed":
        self.console.print(
            "[yellow]mail option only available for Pre-Mailed ChangeSpecs[/yellow]"
        )
        return changespecs, current_idx

    # Update to the changespec branch (NAME field) to ensure we're on the correct branch
    success, error_msg = update_to_changespec(
        changespec, self.console, revision=changespec.name
    )
    if not success:
        self.console.print(f"[red]Error: {error_msg}[/red]")
        return changespecs, current_idx

    # Run the mail handler
    success = mail_ops_handle_mail(changespec, self.console)

    if success:
        # Reload changespecs to reflect the status update
        changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx
