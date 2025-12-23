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


def handle_add_hook(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle 'h' (add hook) action.

    Prompts user for a hook command and adds it to the ChangeSpec's HOOKS field.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    from ..hooks import add_hook_to_changespec
    from ..status import prompt_hook_command

    # Prompt user for hook command
    hook_command = prompt_hook_command(self.console)
    if hook_command is None:
        # User cancelled
        return changespecs, current_idx

    # Add hook to the ChangeSpec
    success = add_hook_to_changespec(
        changespec.file_path,
        changespec.name,
        hook_command,
        changespec.hooks,
    )
    if not success:
        self.console.print("[red]Error adding hook[/red]")
        return changespecs, current_idx

    self.console.print(f"[green]Added hook: {hook_command}[/green]")

    # Reload changespecs to reflect the update
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx


def handle_findreviewers(self: "WorkWorkflow", changespec: ChangeSpec) -> None:
    """Handle 'f' (findreviewers) action.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
    """
    if changespec.status != "Drafted":
        self.console.print(
            "[yellow]findreviewers option only available for Drafted ChangeSpecs[/yellow]"
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


def handle_rerun_hooks(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle 'H' (rerun hooks) action.

    Displays the ChangeSpec with hints on hooks (like 'v' view), allows user to
    select which ones to rerun by clearing their status lines.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    from ..changespec import HookEntry, display_changespec
    from ..hooks import get_hook_output_path, update_changespec_hooks_field

    if not changespec.hooks:
        self.console.print("[yellow]No hooks defined[/yellow]")
        return changespecs, current_idx

    # Filter to hooks that have status lines (timestamp and status)
    hooks_with_status = [
        (i, hook)
        for i, hook in enumerate(changespec.hooks)
        if hook.timestamp and hook.status
    ]

    if not hooks_with_status:
        self.console.print("[yellow]No hooks with status lines to rerun[/yellow]")
        return changespecs, current_idx

    # Clear and re-display the ChangeSpec with hints (like 'v' view option)
    self.console.clear()
    hint_mappings = display_changespec(changespec, self.console, with_hints=True)

    # Build mapping from hint number to hook index by matching hook output paths
    hint_to_hook_idx: dict[int, int] = {}
    for hook_idx, hook in hooks_with_status:
        assert hook.timestamp is not None  # Guaranteed by filter
        hook_output_path = get_hook_output_path(changespec.name, hook.timestamp)
        # Find the hint number that maps to this hook output path
        for hint_num, path in hint_mappings.items():
            if path == hook_output_path:
                hint_to_hook_idx[hint_num] = hook_idx
                break

    if not hint_to_hook_idx:
        self.console.print("[yellow]No hook hints found[/yellow]")
        return changespecs, current_idx

    # Show instructions
    self.console.print()
    self.console.print(
        "[cyan]Enter hook hint numbers (space-separated) to rerun, or press Enter to cancel.[/cyan]"
    )
    self.console.print(
        "[cyan]Add '@' suffix to completely delete a hook (e.g., '2@').[/cyan]"
    )

    try:
        user_input = input("Hints: ").strip()
    except (EOFError, KeyboardInterrupt):
        self.console.print("\n[yellow]Cancelled[/yellow]")
        return changespecs, current_idx

    if not user_input:
        return changespecs, current_idx

    # Parse hint numbers - track which to rerun (clear status) vs delete entirely
    hints_to_rerun: list[int] = []
    hints_to_delete: list[int] = []
    for part in user_input.split():
        delete_hook = False
        if part.endswith("@"):
            delete_hook = True
            part = part[:-1]

        try:
            hint_num = int(part)
            if hint_num in hint_to_hook_idx:
                if delete_hook:
                    hints_to_delete.append(hint_num)
                else:
                    hints_to_rerun.append(hint_num)
            else:
                self.console.print(f"[yellow]Invalid hint: {hint_num}[/yellow]")
        except ValueError:
            self.console.print(f"[yellow]Invalid input: {part}[/yellow]")

    if not hints_to_rerun and not hints_to_delete:
        return changespecs, current_idx

    # Get the hook indices for each action
    hook_indices_to_clear = {hint_to_hook_idx[h] for h in hints_to_rerun}
    hook_indices_to_delete = {hint_to_hook_idx[h] for h in hints_to_delete}

    # Create updated hooks list
    updated_hooks: list[HookEntry] = []
    for i, hook in enumerate(changespec.hooks):
        if i in hook_indices_to_delete:
            # Skip this hook entirely (delete it)
            continue
        elif i in hook_indices_to_clear:
            # Clear status by removing timestamp, status, and duration
            updated_hooks.append(
                HookEntry(
                    command=hook.command,
                    timestamp=None,
                    status=None,
                    duration=None,
                )
            )
        else:
            updated_hooks.append(hook)

    # Update the project file
    success = update_changespec_hooks_field(
        changespec.file_path,
        changespec.name,
        updated_hooks,
    )

    if not success:
        self.console.print("[red]Error updating hooks[/red]")
        return changespecs, current_idx

    # Show confirmation
    messages = []
    if hints_to_rerun:
        messages.append(
            f"Cleared status for {len(hints_to_rerun)} hook(s) - will be rerun by gai monitor"
        )
    if hints_to_delete:
        messages.append(f"Deleted {len(hints_to_delete)} hook(s)")
    self.console.print(f"[green]{'; '.join(messages)}[/green]")

    # Reload changespecs to reflect the update
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
