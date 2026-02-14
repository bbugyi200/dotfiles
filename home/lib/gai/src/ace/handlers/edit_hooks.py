"""Handler for the edit-hooks tool action."""

from typing import TYPE_CHECKING

from ..changespec import ChangeSpec

if TYPE_CHECKING:
    from ..tui._workflow_context import WorkflowContext


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
    self: "WorkflowContext",
    changespec: ChangeSpec,
    test_targets_input: str,
) -> bool:
    """Add bb_rabbit_test hooks for each test target.

    Args:
        self: The WorkflowContext instance
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
            display_target = target.lstrip("/")
            self.console.print(f"[green]Added hook: //{display_target}[/green]")
        return True
    else:
        self.console.print("[yellow]Hooks already exist or error adding[/yellow]")
        return False


def handle_edit_hooks(
    self: "WorkflowContext",
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
        self: The WorkflowContext instance
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
        "[cyan]  • Enter '//target1 //target2' to add test target hooks[/cyan]"
    )
    self.console.print("[cyan]  • Enter any other text to add as a hook command[/cyan]")
    self.console.print("[dim]Example: //foo:bar_test[/dim]")

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
        # overwriting changes made by gai axe
        success = add_hook_to_changespec(
            changespec.file_path,
            changespec.name,
            user_input,
        )
        if not success:
            self.console.print("[red]Error adding hook[/red]")
            return changespecs, current_idx

        from hook_history import add_or_update_hook

        add_or_update_hook(user_input)
        self.console.print(f"[green]Added hook: {user_input}[/green]")
        changespecs, current_idx = self._reload_and_reposition(changespecs, changespec)
        return changespecs, current_idx


def _handle_rerun_delete_hooks(
    self: "WorkflowContext",
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
        self: The WorkflowContext instance
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

    # Get the last COMMITS entry ID - we only delete status lines for this entry
    last_history_entry_id = get_last_history_entry_id(changespec)
    if last_history_entry_id is None:
        self.console.print("[yellow]No COMMITS entries found[/yellow]")
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
            # Remove only the status line for the last COMMITS entry (to trigger rerun)
            if hook.status_lines:
                # Keep all status lines except the one for the last COMMITS entry
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
