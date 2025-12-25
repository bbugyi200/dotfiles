"""Handler functions for workflow-related operations in the work subcommand."""

import os
import subprocess
import sys
from typing import TYPE_CHECKING

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from chat_history import save_chat_history
from gemini_wrapper import GeminiCommandWrapper
from langchain_core.messages import HumanMessage
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

from ..changespec import ChangeSpec, display_changespec, parse_project_file
from ..hooks import (
    clear_hook_suffix,
    get_failing_hooks_for_fix,
    get_hook_output_path,
    get_last_history_entry_num,
    set_hook_suffix,
)
from ..hooks import (
    generate_timestamp as generate_fix_hook_timestamp,
)
from ..operations import update_to_changespec
from ..workflow_ops import (
    run_crs_workflow,
    run_fix_tests_workflow,
    run_qa_workflow,
)

if TYPE_CHECKING:
    from ..workflow import WorkWorkflow


def _strip_hook_prefix(hook_command: str) -> str:
    """Strip the '!' prefix from a hook command if present.

    The '!' prefix indicates that FAILED status lines should auto-append
    '- (!)' to skip fix-hook hints. This function strips it for display
    and execution purposes.

    Args:
        hook_command: The hook command string.

    Returns:
        The command with the '!' prefix stripped if present.
    """
    if hook_command.startswith("!"):
        return hook_command[1:]
    return hook_command


def handle_run_workflow(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
    workflow_index: int = 0,
) -> tuple[list[ChangeSpec], int]:
    """Handle 'r' (run workflow) action.

    Runs workflow based on available workflows for the ChangeSpec.
    When multiple workflows are available, workflow_index selects which one to run.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index
        workflow_index: Index of workflow to run (default 0)

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    from ..operations import get_available_workflows

    workflows = get_available_workflows(changespec)
    if not workflows:
        self.console.print(
            "[yellow]Run option not available for this ChangeSpec[/yellow]"
        )
        return changespecs, current_idx

    # Validate workflow index
    if workflow_index < 0 or workflow_index >= len(workflows):
        self.console.print(f"[red]Invalid workflow index: {workflow_index + 1}[/red]")
        return changespecs, current_idx

    # Get the selected workflow
    selected_workflow = workflows[workflow_index]

    # Route to the appropriate handler based on workflow name
    if selected_workflow == "qa":
        return handle_run_qa_workflow(self, changespec, changespecs, current_idx)
    elif selected_workflow == "fix-hook":
        return handle_run_fix_hook_workflow(self, changespec, changespecs, current_idx)
    elif selected_workflow == "fix-tests":
        return handle_run_fix_tests_workflow(self, changespec, changespecs, current_idx)
    elif selected_workflow == "crs":
        return handle_run_crs_workflow(self, changespec, changespecs, current_idx)
    else:
        self.console.print(f"[red]Unknown workflow: {selected_workflow}[/red]")
        return changespecs, current_idx


def handle_run_qa_workflow(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle running qa workflow for 'Pre-Mailed' or 'Mailed' status.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    # Run the workflow (handles all logic including status transitions)
    run_qa_workflow(changespec, self.console)

    # Reload changespecs to reflect updates
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx


def handle_run_fix_tests_workflow(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle running fix-tests workflow for 'Failing Tests' status.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    # Run the workflow (handles all logic including status transitions)
    run_fix_tests_workflow(changespec, self.console)

    # Reload changespecs to reflect updates
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx


def handle_run_crs_workflow(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle running crs workflow for 'Mailed' status.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    # Run the workflow (handles all logic)
    run_crs_workflow(changespec, self.console)

    # Reload changespecs to reflect updates
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx


def handle_run_fix_hook_workflow(
    self: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle running fix-hook workflow for failing hooks.

    If only one hook is failing, runs the fix-hook agent directly.
    If multiple hooks are failing, prompts user to select which one to fix.

    Args:
        self: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    # Get failing hooks eligible for fix
    if not changespec.hooks:
        self.console.print("[yellow]No hooks found[/yellow]")
        return changespecs, current_idx

    failing_hooks = get_failing_hooks_for_fix(changespec.hooks)
    if not failing_hooks:
        self.console.print("[yellow]No failing hooks eligible for fix found[/yellow]")
        return changespecs, current_idx

    # Build a list of failing hooks with output paths
    hooks_with_output: list[tuple[str, str]] = []  # (command, output_path)
    for hook in failing_hooks:
        if hook.timestamp:
            output_path = get_hook_output_path(changespec.name, hook.timestamp)
            hooks_with_output.append((hook.command, output_path))

    if not hooks_with_output:
        self.console.print("[yellow]No failing hooks with output files found[/yellow]")
        return changespecs, current_idx

    # If only one failing hook, run it directly without prompting
    if len(hooks_with_output) == 1:
        hook_command, output_path = hooks_with_output[0]
    else:
        # Multiple failing hooks - display with hints for only those hooks
        self.console.clear()
        display_changespec(changespec, self.console, with_hints=False)

        # Show failing hooks with numbered hints
        self.console.print()
        self.console.print("[cyan]Multiple failing hooks found:[/cyan]")
        for i, (cmd, path) in enumerate(hooks_with_output, start=1):
            self.console.print(f"  [cyan]{i}[/cyan]: {cmd}")
            self.console.print(f"      Output: {path}")
        self.console.print()
        self.console.print("[cyan]Enter number for the failing hook to fix:[/cyan]")

        try:
            user_input = input("Number: ").strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("\n[yellow]Cancelled[/yellow]")
            return changespecs, current_idx

        if not user_input:
            self.console.print("[yellow]No number provided[/yellow]")
            return changespecs, current_idx

        try:
            hook_num = int(user_input)
        except ValueError:
            self.console.print(f"[red]Invalid number: {user_input}[/red]")
            return changespecs, current_idx

        if hook_num < 1 or hook_num > len(hooks_with_output):
            self.console.print(f"[red]Invalid number: {hook_num}[/red]")
            return changespecs, current_idx

        hook_command, output_path = hooks_with_output[hook_num - 1]

    # Extract project basename
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Generate timestamp for tracking this fix-hook run
    fix_hook_timestamp = generate_fix_hook_timestamp()

    # Get the last HISTORY entry number for the amend message
    last_history_num = get_last_history_entry_num(changespec)

    # Find first available workspace and claim it
    workspace_num = get_first_available_workspace(
        changespec.file_path, project_basename
    )
    workspace_dir, workspace_suffix = get_workspace_directory_for_num(
        workspace_num, project_basename
    )

    # Claim the workspace
    claim_success = claim_workspace(
        changespec.file_path,
        workspace_num,
        "fix-hook",
        changespec.name,
    )
    if not claim_success:
        self.console.print("[red]Error: Failed to claim workspace[/red]")
        return changespecs, current_idx

    if workspace_suffix:
        self.console.print(f"[cyan]Using workspace share: {workspace_suffix}[/cyan]")

    # Update to the changespec NAME (cd and bb_hg_update to the branch)
    success, error_msg = update_to_changespec(
        changespec, self.console, revision=changespec.name, workspace_dir=workspace_dir
    )
    if not success:
        self.console.print(f"[red]Error: {error_msg}[/red]")
        release_workspace(
            changespec.file_path, workspace_num, "fix-hook", changespec.name
        )
        return changespecs, current_idx

    # Set the timestamp suffix on the hook status line to mark it as being fixed
    if changespec.hooks:
        set_hook_suffix(
            changespec.file_path,
            changespec.name,
            hook_command,
            fix_hook_timestamp,
            changespec.hooks,
        )

    # Get the display/run command (strip "!" prefix if present)
    run_hook_command = _strip_hook_prefix(hook_command)

    # Build the prompt for the agent
    prompt = (
        f'The command "{run_hook_command}" is failing. The output of the last run can '
        f"be found in the @{output_path} file. Can you help me fix this command by "
        "making the appropriate file changes? Verify that your fix worked when you "
        "are done by re-running that command.\n\nx::this_cl"
    )

    # Save current directory to restore later
    original_dir = os.getcwd()

    try:
        # Change to workspace directory before running agent
        os.chdir(workspace_dir)

        # Run the agent
        self.console.print("[cyan]Running fix-hook agent...[/cyan]")
        self.console.print(f"[dim]Command: {run_hook_command}[/dim]")
        self.console.print()

        wrapper = GeminiCommandWrapper(model_size="big")
        wrapper.set_logging_context(
            agent_type="fix-hook", suppress_output=False, workflow="fix-hook"
        )

        response = wrapper.invoke([HumanMessage(content=prompt)])
        self.console.print(f"\n[green]Agent Response:[/green]\n{response.content}\n")

        # Save chat history for the HISTORY entry
        chat_path = save_chat_history(
            prompt=prompt,
            response=str(response.content),
            workflow="fix-hook",
        )

        # Verify the fix by re-running the hook command
        self.console.print(f"[cyan]Verifying fix by running: {run_hook_command}[/cyan]")
        try:
            result = subprocess.run(
                run_hook_command,
                shell=True,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                self.console.print("[green]Hook command passed![/green]")
            else:
                self.console.print("[red]Hook command still failing[/red]")
                if result.stderr:
                    self.console.print(f"[dim]{result.stderr[:500]}[/dim]")
        except Exception as e:
            self.console.print(f"[red]Error running hook: {e}[/red]")

        # Build workflow name with hook command and HISTORY entry reference
        history_ref = f"({last_history_num})" if last_history_num else ""
        workflow_name = f"fix-hook {history_ref} {run_hook_command}"

        # Prompt for action on changes (creates proposal first)
        prompt_result = prompt_for_change_action(
            self.console,
            workspace_dir,
            workflow_name=workflow_name,
            chat_path=chat_path,
        )
        if prompt_result is None:
            self.console.print("\n[yellow]Warning: No changes detected.[/yellow]")
        else:
            action, action_args = prompt_result

            # Handle reject (proposal stays in HISTORY)
            if action == "reject":
                self.console.print("[yellow]Changes rejected. Proposal saved.[/yellow]")
            elif action == "purge":
                # Delete the proposal
                execute_change_action(
                    action=action,
                    action_args=action_args,
                    console=self.console,
                    target_dir=workspace_dir,
                )
            else:
                # Accept the proposal
                execute_change_action(
                    action=action,
                    action_args=action_args,
                    console=self.console,
                    target_dir=workspace_dir,
                )

    except KeyboardInterrupt:
        self.console.print("\n[yellow]Workflow interrupted (Ctrl+C)[/yellow]")
    except Exception as e:
        self.console.print(f"[red]Workflow crashed: {e}[/red]")
    finally:
        # Restore original directory
        os.chdir(original_dir)

        # Clear the timestamp suffix from the hook status line
        # Need to reload hooks since they may have changed
        updated_changespecs = parse_project_file(changespec.file_path)
        for cs in updated_changespecs:
            if cs.name == changespec.name and cs.hooks:
                clear_hook_suffix(
                    changespec.file_path,
                    changespec.name,
                    hook_command,
                    cs.hooks,
                )
                break

        # Always release the workspace when done
        release_workspace(
            changespec.file_path, workspace_num, "fix-hook", changespec.name
        )

    # Reload changespecs to reflect updates
    changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)

    return changespecs, current_idx
