"""Handler functions for tool-related operations in the work subcommand."""

import os
import subprocess
import sys
from typing import TYPE_CHECKING

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import HumanMessage

from ..changespec import ChangeSpec, find_all_changespecs
from ..mail_ops import handle_mail as mail_ops_handle_mail
from ..operations import get_workspace_directory, update_to_changespec

if TYPE_CHECKING:
    from ..workflow import WorkWorkflow


def handle_show_diff(self: "WorkWorkflow", changespec: ChangeSpec) -> None:
    """Handle 'd' (show diff) action.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
    """
    if changespec.cl is None:
        self.console.print("[yellow]Cannot show diff: CL is not set[/yellow]")
        return

    # Determine which workspace directory to use
    all_changespecs = find_all_changespecs()
    workspace_dir, workspace_suffix = get_workspace_directory(
        changespec, all_changespecs
    )

    if workspace_suffix:
        self.console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")

    # Update to the changespec branch (NAME field) to show the diff
    success, error_msg = update_to_changespec(
        changespec, self.console, revision=changespec.name, workspace_dir=workspace_dir
    )
    if not success:
        self.console.print(f"[red]Error: {error_msg}[/red]")
        return

    # Use the determined workspace directory for running branch_diff
    target_dir = workspace_dir

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


def handle_failing_test(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle 't' (failing test) action.

    Prompts user for failing test targets and adds them to the ChangeSpec
    with (FAILED) markers.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    from ..field_updates import add_failing_test_targets
    from ..status import prompt_failing_test_targets

    # Prompt user for failing test targets
    failing_targets = prompt_failing_test_targets(self.console)
    if failing_targets is None:
        # User cancelled
        return changespecs, current_idx

    # Add failing test targets to the ChangeSpec
    success, error_msg = add_failing_test_targets(
        changespec.file_path, changespec.name, failing_targets
    )
    if not success:
        self.console.print(f"[red]Error adding test targets: {error_msg}[/red]")
        return changespecs, current_idx

    self.console.print(
        f"[green]Added {len(failing_targets)} failing test target(s)[/green]"
    )

    # Reload changespecs to reflect the update
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx


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

    # Determine which workspace directory to use
    all_changespecs = find_all_changespecs()
    workspace_dir, workspace_suffix = get_workspace_directory(
        changespec, all_changespecs
    )

    if workspace_suffix:
        self.console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")

    # Use the determined workspace directory
    target_dir = workspace_dir

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

    # Determine which workspace directory to use
    all_changespecs = find_all_changespecs()
    workspace_dir, workspace_suffix = get_workspace_directory(
        changespec, all_changespecs
    )

    if workspace_suffix:
        self.console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")

    # Update to the changespec branch (NAME field) to ensure we're on the correct branch
    success, error_msg = update_to_changespec(
        changespec, self.console, revision=changespec.name, workspace_dir=workspace_dir
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


def handle_run_query(self: "WorkWorkflow", changespec: ChangeSpec) -> None:
    """Handle 'R' (run query) action.

    Prompts the user for a query, changes to the appropriate directory,
    runs bb_hg_update, and executes the query through Gemini.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
    """
    # Determine which workspace directory to use
    all_changespecs = find_all_changespecs()
    workspace_dir, workspace_suffix = get_workspace_directory(
        changespec, all_changespecs
    )

    if workspace_suffix:
        self.console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")

    # Update to the changespec
    success, error_msg = update_to_changespec(
        changespec, self.console, workspace_dir=workspace_dir
    )
    if not success:
        self.console.print(f"[red]Error: {error_msg}[/red]")
        return

    # Prompt user for query
    self.console.print("\n[cyan]Enter your query for Gemini:[/cyan]")
    query = input("> ").strip()

    if not query:
        self.console.print("[yellow]No query provided[/yellow]")
        return

    # Save current directory to restore later
    original_dir = os.getcwd()

    try:
        # Change to the workspace directory
        os.chdir(workspace_dir)

        # Run the query through Gemini
        self.console.print("[cyan]Running query through Gemini...[/cyan]\n")
        wrapper = GeminiCommandWrapper(model_size="little")
        wrapper.set_logging_context(
            agent_type="query", suppress_output=False, workflow="work-query"
        )

        response = wrapper.invoke([HumanMessage(content=query)])
        self.console.print(f"\n[green]Response:[/green]\n{response.content}\n")

    finally:
        # Restore original directory
        os.chdir(original_dir)
