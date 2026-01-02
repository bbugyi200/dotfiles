"""Handler functions for tool-related operations in the work subcommand."""

import os
import subprocess
import sys
from typing import TYPE_CHECKING

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import HumanMessage

from ..changespec import ChangeSpec
from ..mail_ops import handle_mail as mail_ops_handle_mail
from ..operations import get_workspace_directory, update_to_changespec

if TYPE_CHECKING:
    from ..workflow import AceWorkflow


def handle_show_diff(self: "AceWorkflow", changespec: ChangeSpec) -> None:
    """Handle 'd' (show diff) action.

    Simplified implementation that runs 'hg diff <name>' in the primary workspace.
    Does not claim/release workspaces via the RUNNING field.

    Args:
        self: The AceWorkflow instance
        changespec: Current ChangeSpec
    """
    from running_field import get_workspace_directory as get_primary_workspace

    # Extract project basename from file path (e.g., /path/to/foobar.md -> foobar)
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Get the primary workspace directory (workspace #1)
    try:
        target_dir = get_primary_workspace(project_basename, 1)
    except RuntimeError as e:
        self.console.print(f"[red]Error getting workspace: {e}[/red]")
        return

    try:
        # Run hg diff -c <name> to show changes in the named changeset
        subprocess.run(
            ["hg", "diff", "-c", changespec.name],
            cwd=target_dir,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        self.console.print(f"[red]hg diff failed (exit code {e.returncode})[/red]")
    except FileNotFoundError:
        self.console.print("[red]hg command not found[/red]")
    except Exception as e:
        self.console.print(f"[red]Unexpected error running hg diff: {str(e)}[/red]")


def handle_reword(self: "AceWorkflow", changespec: ChangeSpec) -> None:
    """Handle 'w' (reword) action to change CL description.

    Claims a workspace in the 100-199 range, checks out the CL,
    runs bb_hg_reword (interactive), then releases the workspace.

    Args:
        self: The AceWorkflow instance
        changespec: Current ChangeSpec
    """
    from running_field import (
        claim_workspace,
        get_first_available_loop_workspace,
        get_workspace_directory_for_num,
        release_workspace,
    )

    from ..changespec import get_base_status

    # Validate status (strip any suffix like "READY TO MAIL")
    base_status = get_base_status(changespec.status)
    if base_status not in ("Drafted", "Mailed"):
        self.console.print(
            "[yellow]reword option only available for Drafted or Mailed ChangeSpecs[/yellow]"
        )
        return

    # Validate CL is set
    if changespec.cl is None:
        self.console.print("[yellow]reword option requires a CL to be set[/yellow]")
        return

    # Extract project basename from file path
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Claim a workspace in the 100-199 range
    workspace_num = get_first_available_loop_workspace(changespec.file_path)

    if not claim_workspace(
        changespec.file_path, workspace_num, "reword", changespec.name
    ):
        self.console.print("[red]Failed to claim workspace[/red]")
        return

    try:
        # Get workspace directory
        workspace_dir, workspace_suffix = get_workspace_directory_for_num(
            workspace_num, project_basename
        )

        if workspace_suffix:
            self.console.print(f"[cyan]Using workspace: {workspace_suffix}[/cyan]")

        # Update to the changespec (checkout the CL)
        self.console.print(f"[cyan]Checking out {changespec.name}...[/cyan]")
        try:
            subprocess.run(
                ["bb_hg_update", changespec.name],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else e.stdout.strip()
            self.console.print(f"[red]Error checking out CL: {error_msg}[/red]")
            return
        except FileNotFoundError:
            self.console.print("[red]bb_hg_update command not found[/red]")
            return

        # Run bb_hg_reword (interactive - opens editor)
        self.console.print("[cyan]Running bb_hg_reword...[/cyan]")
        try:
            reword_result = subprocess.run(
                ["bb_hg_reword"],
                cwd=workspace_dir,
                check=False,  # Don't raise on non-zero exit
            )
            if reword_result.returncode == 0:
                self.console.print("[green]CL description updated successfully[/green]")
            else:
                self.console.print(
                    f"[yellow]bb_hg_reword exited with code {reword_result.returncode}[/yellow]"
                )
        except FileNotFoundError:
            self.console.print("[red]bb_hg_reword command not found[/red]")
        except Exception as e:
            self.console.print(f"[red]Error running bb_hg_reword: {str(e)}[/red]")

    finally:
        # Always release the workspace
        release_workspace(
            changespec.file_path, workspace_num, "reword", changespec.name
        )


def _is_rerun_input(user_input: str) -> bool:
    """Check if user input is a rerun/delete command (list of integers with optional suffix).

    Suffixes:
        - No suffix: rerun the hook (clear status for last history entry)
        - '@' suffix: delete the hook entirely

    Args:
        user_input: The user's input string

    Returns:
        True if input looks like a rerun command (e.g., "1 2 3", "1@", "2@ 3")
    """
    if not user_input:
        return False

    for part in user_input.split():
        # Reject '@@' suffix (no longer supported)
        if part.endswith("@@"):
            return False
        # Strip optional '@' suffix
        part_stripped = part.rstrip("@")
        # Check if it's a valid integer
        if not part_stripped.isdigit():
            return False

    return True


def _add_hooks_for_test_targets(
    self: "AceWorkflow",
    changespec: ChangeSpec,
    test_targets_input: str,
) -> bool:
    """Add bb_rabbit_test hooks for each test target.

    Args:
        self: The AceWorkflow instance
        changespec: Current ChangeSpec
        test_targets_input: String starting with "//" containing test targets

    Returns:
        True if any hooks were added successfully
    """
    from ..hints import parse_test_targets
    from ..hooks import add_test_target_hooks_to_changespec

    # Parse targets from input
    targets = parse_test_targets(test_targets_input)

    if not targets:
        self.console.print("[yellow]No test targets provided[/yellow]")
        return False

    # Use add_test_target_hooks_to_changespec which handles multiple targets
    # correctly by adding all hooks in a single write operation
    success = add_test_target_hooks_to_changespec(
        changespec.file_path,
        changespec.name,
        targets,
    )

    if success:
        for target in targets:
            self.console.print(f"[green]Added hook: bb_rabbit_test {target}[/green]")
        return True
    else:
        self.console.print("[yellow]Hooks already exist or error adding[/yellow]")
        return False


def handle_edit_hooks(
    self: "AceWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle 'h' (edit hooks) action.

    Displays the ChangeSpec with hints on failing hooks and prompts for input.
    - If input is a list of integers (with optional '@' suffix): rerun/delete hooks
    - If input starts with "//": add bb_rabbit_test hooks for each test target
    - Otherwise: add the input as a new hook command

    Args:
        self: The AceWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    from ..display import display_changespec
    from ..hooks import add_hook_to_changespec

    # Clear screen and display ChangeSpec with hints for failing hooks
    self.console.clear()
    _, hint_to_hook_idx = display_changespec(
        changespec, self.console, with_hints=True, hints_for="hooks_latest_only"
    )

    # Show instructions
    self.console.print()
    self.console.print("[bold cyan]Edit hooks:[/bold cyan]")
    if hint_to_hook_idx:
        self.console.print(
            "[cyan]  • Enter hint numbers (space-separated) to rerun hooks[/cyan]"
        )
        self.console.print(
            "[cyan]  • Add '@' suffix to delete a hook (e.g., '2@')[/cyan]"
        )
    self.console.print(
        "[cyan]  • Enter '//target1 //target2' to add bb_rabbit_test hooks[/cyan]"
    )
    self.console.print("[cyan]  • Enter any other text to add as a hook command[/cyan]")
    self.console.print("[dim]Example: bb_rabbit_test //foo:bar_test[/dim]")

    try:
        user_input = input("Hook command: ").strip()
    except (EOFError, KeyboardInterrupt):
        self.console.print("\n[yellow]Cancelled[/yellow]")
        return changespecs, current_idx

    if not user_input:
        return changespecs, current_idx

    # Determine what action to take based on input format
    if _is_rerun_input(user_input):
        # Handle as rerun/delete commands
        return _handle_rerun_delete_hooks(
            self, changespec, changespecs, current_idx, user_input, hint_to_hook_idx
        )
    elif user_input.startswith("//"):
        # Handle as bb_rabbit_test targets
        success = _add_hooks_for_test_targets(self, changespec, user_input)
        if success:
            changespecs, current_idx = self._reload_and_reposition(
                changespecs, changespec
            )
        return changespecs, current_idx
    else:
        # Handle as new hook command
        # Don't pass existing_hooks - let it re-read from disk to avoid
        # overwriting changes made by gai loop
        success = add_hook_to_changespec(
            changespec.file_path,
            changespec.name,
            user_input,
        )
        if not success:
            self.console.print("[red]Error adding hook[/red]")
            return changespecs, current_idx

        self.console.print(f"[green]Added hook: {user_input}[/green]")
        changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)
        return changespecs, current_idx


def _handle_rerun_delete_hooks(
    self: "AceWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
    user_input: str,
    hint_to_hook_idx: dict[int, int],
) -> tuple[list[ChangeSpec], int]:
    """Handle rerun/delete hook commands based on hint numbers.

    Suffixes:
        - No suffix: Clear status for last history entry only (rerun)
        - '@' suffix: Delete the hook entirely

    Args:
        self: The AceWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index
        user_input: Space-separated hint numbers (with optional '@' suffix)
        hint_to_hook_idx: Mapping of hint numbers to hook indices

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    from ..changespec import HookEntry
    from ..hooks import (
        get_last_history_entry_id,
        kill_running_processes_for_hooks,
        update_changespec_hooks_field,
    )

    if not hint_to_hook_idx:
        self.console.print("[yellow]No hooks with status lines to rerun[/yellow]")
        return changespecs, current_idx

    # Get the last HISTORY entry ID - we only delete status lines for this entry
    last_history_entry_id = get_last_history_entry_id(changespec)
    if last_history_entry_id is None:
        self.console.print("[yellow]No HISTORY entries found[/yellow]")
        return changespecs, current_idx

    # Parse hint numbers - track actions: rerun or delete
    hints_to_rerun: list[int] = []
    hints_to_delete: list[int] = []
    for part in user_input.split():
        action = "rerun"  # default
        if part.endswith("@"):
            action = "delete"
            part = part[:-1]

        try:
            hint_num_val = int(part)
            if hint_num_val in hint_to_hook_idx:
                if action == "delete":
                    hints_to_delete.append(hint_num_val)
                else:
                    hints_to_rerun.append(hint_num_val)
            else:
                self.console.print(f"[yellow]Invalid hint: {hint_num_val}[/yellow]")
        except ValueError:
            self.console.print(f"[yellow]Invalid input: {part}[/yellow]")

    if not hints_to_rerun and not hints_to_delete:
        return changespecs, current_idx

    # Get the hook indices for each action
    hook_indices_to_rerun = {hint_to_hook_idx[h] for h in hints_to_rerun}
    hook_indices_to_delete = {hint_to_hook_idx[h] for h in hints_to_delete}

    # Kill any running processes/agents for hooks being rerun or deleted
    all_affected_indices = hook_indices_to_rerun | hook_indices_to_delete
    killed_count = kill_running_processes_for_hooks(
        changespec.hooks, all_affected_indices
    )
    if killed_count > 0:
        self.console.print(f"[cyan]Killed {killed_count} running process(es)[/cyan]")

    # Create updated hooks list
    updated_hooks: list[HookEntry] = []
    for i, hook in enumerate(changespec.hooks or []):
        if i in hook_indices_to_delete:
            # Skip this hook entirely (delete it)
            continue
        elif i in hook_indices_to_rerun:
            # Remove only the status line for the last HISTORY entry (to trigger rerun)
            if hook.status_lines:
                # Keep all status lines except the one for the last HISTORY entry
                remaining_status_lines = [
                    sl
                    for sl in hook.status_lines
                    if sl.commit_entry_num != last_history_entry_id
                ]
                updated_hooks.append(
                    HookEntry(
                        command=hook.command,
                        status_lines=(
                            remaining_status_lines if remaining_status_lines else None
                        ),
                    )
                )
            else:
                updated_hooks.append(hook)
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
            f"Cleared status for {len(hints_to_rerun)} hook(s) - will be rerun"
        )
    if hints_to_delete:
        messages.append(f"Deleted {len(hints_to_delete)} hook(s)")
    self.console.print(f"[green]{'; '.join(messages)}[/green]")

    # Reload changespecs to reflect the update
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx


def handle_findreviewers(self: "AceWorkflow", changespec: ChangeSpec) -> None:
    """Handle 'f' (findreviewers) action.

    Args:
        self: The AceWorkflow instance
        changespec: Current ChangeSpec
    """
    if changespec.status != "Drafted":
        self.console.print(
            "[yellow]findreviewers option only available for Drafted ChangeSpecs[/yellow]"
        )
        return

    # Determine which workspace directory to use
    workspace_dir, workspace_suffix = get_workspace_directory(changespec)

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
    self: "AceWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle 'm' (mail) action.

    Args:
        self: The AceWorkflow instance
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
    workspace_dir, workspace_suffix = get_workspace_directory(changespec)

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


def handle_run_query(self: "AceWorkflow", changespec: ChangeSpec) -> None:
    """Handle 'R' (run query) action.

    Prompts the user for a query, changes to the appropriate directory,
    runs bb_hg_update, and executes the query through Gemini.

    Args:
        self: The AceWorkflow instance
        changespec: Current ChangeSpec
    """
    # Determine which workspace directory to use
    workspace_dir, workspace_suffix = get_workspace_directory(changespec)

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
