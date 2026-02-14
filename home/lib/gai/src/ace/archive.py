"""Archive operations for ChangeSpecs."""

import os
import sys
from pathlib import Path

from rich.console import Console

# Add parent directory to path for status_state_machine import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from running_field import (
    claim_workspace,
    get_first_available_axe_workspace,
    get_workspace_directory_for_num,
    release_workspace,
)
from status_state_machine import transition_changespec_status
from vcs_provider import get_vcs_provider

from .changespec import (
    ChangeSpec,
    find_all_changespecs,
)
from .hooks.processes import kill_and_persist_all_running_processes
from .operations import (
    calculate_lifecycle_new_name,
    has_active_children,
    rename_changespec_with_references,
    save_diff_to_file,
)


def archive_changespec(
    changespec: ChangeSpec, console: Console | None = None
) -> tuple[bool, str | None]:
    """Archive a ChangeSpec by archiving its CL and updating its status.

    This function:
    1. Validates that the ChangeSpec has a valid CL set
    2. Validates that all children are Archived or Reverted
    3. Claims a workspace >= 100
    4. Checks out the CL with bb_hg_update
    5. Saves the diff to `~/.gai/archived/<new_name>.diff`
    6. Runs `bb_hg_archive <name>` to archive the revision
    7. Renames the ChangeSpec by appending `__<N>` suffix
    8. Updates STATUS to "Archived" and CL to "None"
    9. Releases the claimed workspace

    Args:
        changespec: The ChangeSpec to archive
        console: Optional Rich Console for output

    Returns:
        Tuple of (success, error_message)
    """
    # Validate CL is set
    if changespec.cl is None:
        return (False, "ChangeSpec does not have a valid CL set")

    # Kill any running processes before archiving
    log_fn = (lambda msg: console.print(f"[cyan]{msg}[/cyan]")) if console else None
    kill_and_persist_all_running_processes(
        changespec,
        changespec.file_path,
        changespec.name,
        "Killed hook running on archived CL.",
        log_fn=log_fn,
    )

    # Get all changespecs to check for children and name conflicts
    all_changespecs = find_all_changespecs()

    # Validate no non-terminal children (different from revert!)
    if has_active_children(
        changespec, all_changespecs, terminal_statuses=("Archived", "Reverted")
    ):
        return (
            False,
            "Cannot archive: other ChangeSpecs have this one as their parent "
            "and are not Archived or Reverted",
        )

    # Get project basename for workspace operations
    project_basename = os.path.basename(changespec.file_path).replace(".gp", "")

    # Claim a workspace >= 100 for the archive operation
    workspace_num = get_first_available_axe_workspace(changespec.file_path)
    workflow_name = f"archive-{changespec.name}"
    pid = os.getpid()

    try:
        workspace_dir, _ = get_workspace_directory_for_num(
            workspace_num, project_basename
        )
    except RuntimeError as e:
        return (False, f"Failed to get workspace directory: {e}")

    if console:
        console.print(f"[cyan]Claiming workspace #{workspace_num}[/cyan]")

    if not claim_workspace(
        changespec.file_path, workspace_num, workflow_name, pid, changespec.name
    ):
        return (False, f"Failed to claim workspace #{workspace_num}")

    try:
        # Checkout the CL
        if console:
            console.print(f"[cyan]Checking out {changespec.name}...[/cyan]")

        provider = get_vcs_provider(workspace_dir)
        success, error = provider.checkout(changespec.name, workspace_dir)
        if not success:
            return (False, f"Failed to checkout CL: {error}")

        if console:
            console.print(f"[green]Checked out: {changespec.name}[/green]")

        # Calculate new name with suffix
        new_name = calculate_lifecycle_new_name(changespec, all_changespecs)

        if console:
            console.print(f"[cyan]Renaming ChangeSpec to: {new_name}[/cyan]")

        # Save diff to file
        success, error = save_diff_to_file(
            changespec, new_name, workspace_dir, "archived"
        )
        if not success:
            return (False, f"Failed to save diff: {error}")

        if console:
            diff_path = Path.home() / ".gai" / "archived" / f"{new_name}.diff"
            console.print(f"[green]Saved diff to: {diff_path}[/green]")

        # Run bb_hg_archive
        success, error = provider.archive(changespec.name, workspace_dir)
        if not success:
            return (False, f"Failed to archive revision: {error}")

        if console:
            console.print(f"[green]Archived revision: {changespec.name}[/green]")

        # Rename the ChangeSpec (skip if name is unchanged, e.g., WIP with existing suffix)
        if new_name != changespec.name:
            try:
                rename_changespec_with_references(
                    changespec.file_path, changespec.name, new_name
                )
            except Exception as e:
                return (False, f"Failed to rename ChangeSpec: {e}")

            if console:
                console.print(
                    f"[green]Renamed ChangeSpec: {changespec.name} -> {new_name}[/green]"
                )

        # Update STATUS to Archived
        success, _, error, _ = transition_changespec_status(
            changespec.file_path,
            new_name,  # Use the new name after rename
            "Archived",
            validate=False,
        )
        if not success:
            return (False, f"Failed to update status: {error}")

        if console:
            console.print("[green]Status updated to Archived[/green]")

        return (True, None)

    finally:
        # Always release the workspace
        release_workspace(
            changespec.file_path,
            workspace_num,
            workflow_name,
            changespec.name,
        )
        if console:
            console.print(f"[cyan]Released workspace #{workspace_num}[/cyan]")
