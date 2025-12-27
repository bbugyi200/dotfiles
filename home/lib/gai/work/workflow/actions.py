"""Action handlers for the work workflow."""

import os
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from status_state_machine import transition_changespec_status

from ..changespec import ChangeSpec
from ..display import display_changespec
from ..revert import revert_changespec
from ..status import STATUS_REVERTED, prompt_status_change

if TYPE_CHECKING:
    from .main import WorkWorkflow


def handle_next(
    workflow: "WorkWorkflow", current_idx: int, max_idx: int
) -> tuple[int, str] | tuple[None, None]:
    """Handle 'n' (next) navigation.

    Args:
        workflow: The WorkWorkflow instance
        current_idx: Current index in changespecs list
        max_idx: Maximum valid index

    Returns:
        Tuple of (new_index, new_direction) or (None, None) if can't move
    """
    if current_idx < max_idx:
        return current_idx + 1, "n"
    else:
        workflow.console.print("[yellow]Already at last ChangeSpec[/yellow]")
        return None, None


def handle_prev(
    workflow: "WorkWorkflow", current_idx: int
) -> tuple[int, str] | tuple[None, None]:
    """Handle 'p' (prev) navigation.

    Args:
        workflow: The WorkWorkflow instance
        current_idx: Current index in changespecs list

    Returns:
        Tuple of (new_index, new_direction) or (None, None) if can't move
    """
    if current_idx > 0:
        return current_idx - 1, "p"
    else:
        workflow.console.print("[yellow]Already at first ChangeSpec[/yellow]")
        return None, None


def handle_status_change(
    workflow: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle 's' (status change) action.

    Args:
        workflow: The WorkWorkflow instance
        changespec: Current ChangeSpec
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    new_status = prompt_status_change(workflow.console, changespec.status)
    if new_status:
        # Special handling for "Reverted" status - run revert workflow
        if new_status == STATUS_REVERTED:
            success, error_msg = revert_changespec(changespec, workflow.console)
            if not success:
                workflow.console.print(f"[red]Error reverting: {error_msg}[/red]")
                return changespecs, current_idx

            # Reload changespecs to reflect the update
            changespecs, current_idx = workflow._reload_and_reposition(
                changespecs, changespec
            )
            return changespecs, current_idx

        # Update the status in the project file
        success, old_status, error_msg = transition_changespec_status(
            changespec.file_path,
            changespec.name,
            new_status,
            validate=False,  # Don't validate - allow any transition
        )
        if success:
            workflow.console.print(
                f"[green]Status updated: {old_status} → {new_status}[/green]"
            )

            # Reload changespecs to reflect the update
            changespecs, current_idx = workflow._reload_and_reposition(
                changespecs, changespec
            )
        else:
            workflow.console.print(f"[red]Error: {error_msg}[/red]")

    return changespecs, current_idx


def handle_refresh(
    workflow: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
) -> tuple[list[ChangeSpec], int]:
    """Handle 'y' (refresh) action - rescan project files.

    Rescans project files to refresh the list of ChangeSpecs based on
    the current filter flags (-s and -p).

    Args:
        workflow: The WorkWorkflow instance
        changespec: Current ChangeSpec (used for repositioning after refresh)
        changespecs: List of all changespecs
        current_idx: Current index

    Returns:
        Tuple of (updated_changespecs, updated_index)
    """
    workflow.console.print("[cyan]Refreshing ChangeSpec list...[/cyan]")

    # Reload changespecs from disk and apply filters
    changespecs, current_idx = workflow._reload_and_reposition(changespecs, changespec)

    workflow.console.print(f"[green]Found {len(changespecs)} ChangeSpec(s)[/green]")
    return changespecs, current_idx


def handle_view(workflow: "WorkWorkflow", changespec: ChangeSpec) -> None:
    """Handle 'v' (view files) action.

    Displays the ChangeSpec with numbered hints next to file paths,
    prompts user to select files, and displays them using bat/cat.
    If the last hint ends with '@', opens all selected files in $EDITOR.

    Args:
        workflow: The WorkWorkflow instance
        changespec: Current ChangeSpec
    """
    # Re-display with hints enabled
    workflow.console.clear()
    hint_mappings, _ = display_changespec(changespec, workflow.console, with_hints=True)

    if not hint_mappings:
        workflow.console.print("[yellow]No files available to view[/yellow]")
        return

    # Show available hints
    workflow.console.print()
    workflow.console.print(
        "[cyan]Enter hint numbers (space-separated) to view files.[/cyan]"
    )
    workflow.console.print(
        "[cyan]Use [0] to view the project file. "
        "Add '@' to last number (e.g., '3@') to open in $EDITOR.[/cyan]"
    )
    workflow.console.print()

    try:
        user_input = input("Hints: ").strip()
    except (EOFError, KeyboardInterrupt):
        workflow.console.print("\n[yellow]Cancelled[/yellow]")
        return

    if not user_input:
        return

    # Parse hint numbers
    parts = user_input.split()
    if not parts:
        return

    open_in_editor = False
    hints_to_view: list[int] = []

    for part in parts:
        # Check for '@' suffix on the last part
        if part.endswith("@"):
            open_in_editor = True
            part = part[:-1]

        try:
            hint_num = int(part)
            if hint_num in hint_mappings:
                hints_to_view.append(hint_num)
            else:
                workflow.console.print(f"[yellow]Invalid hint: {hint_num}[/yellow]")
        except ValueError:
            workflow.console.print(f"[yellow]Invalid input: {part}[/yellow]")

    if not hints_to_view:
        return

    # Collect file paths and expand ~ to home directory
    files_to_view = [os.path.expanduser(hint_mappings[h]) for h in hints_to_view]

    if open_in_editor:
        # Open in $EDITOR
        editor = os.environ.get("EDITOR", "vi")
        try:
            subprocess.run([editor] + files_to_view, check=False)
        except FileNotFoundError:
            workflow.console.print(f"[red]Editor not found: {editor}[/red]")
    else:
        # Display using bat or cat
        viewer = "bat" if shutil.which("bat") else "cat"
        try:
            subprocess.run([viewer] + files_to_view, check=False)
        except FileNotFoundError:
            workflow.console.print(f"[red]Viewer not found: {viewer}[/red]")


def handle_accept_proposal(
    workflow: "WorkWorkflow",
    changespec: ChangeSpec,
    changespecs: list[ChangeSpec],
    current_idx: int,
    user_input: str,
) -> tuple[list[ChangeSpec], int]:
    """Handle accepting a proposed HISTORY entry.

    Args:
        workflow: The WorkWorkflow instance
        changespec: Current ChangeSpec.
        changespecs: List of all ChangeSpecs.
        current_idx: Current index in the list.
        user_input: User input (e.g., "a", "a 2a", "a 2a fix typo").

    Returns:
        Tuple of (updated changespecs, updated current_idx).
    """
    from accept_workflow import AcceptWorkflow

    # Parse user_input: "a", "a 2a", or "a 2a fix typo"
    parts = user_input.split(maxsplit=2)

    if len(parts) < 2:
        # Just "a" - show usage
        workflow.console.print("[red]Usage: a <proposal_id> [msg][/red]")
        workflow.console.print("[dim]Example: a 2a[/dim]")
        workflow.console.print("[dim]Example: a 2a fix typo[/dim]")
        return changespecs, current_idx

    proposal_id = parts[1]
    msg = parts[2] if len(parts) > 2 else None

    # Run accept workflow
    workflow.console.print(f"[cyan]Accepting proposal {proposal_id}...[/cyan]")
    accept_workflow = AcceptWorkflow(
        proposal=proposal_id,
        msg=msg,
        cl_name=changespec.name,
        project_file=changespec.file_path,
    )
    accept_workflow.run()

    # Reload changespecs to reflect updates
    changespecs, current_idx = workflow._reload_and_reposition(changespecs, changespec)
    return changespecs, current_idx
