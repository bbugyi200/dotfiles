"""Revert operations for ChangeSpecs."""

import os
import sys
from pathlib import Path

from rich.console import Console

# Add parent directory to path for status_state_machine import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from gai_utils import (
    get_workspace_directory_for_changespec,
)
from status_state_machine import (
    reset_changespec_cl,
    transition_changespec_status,
)
from vcs_provider import get_vcs_provider

from .changespec import (
    ChangeSpec,
    changespec_lock,
    find_all_changespecs,
    write_changespec_atomic,
)
from .hooks.processes import kill_and_persist_all_running_processes
from .operations import (
    calculate_lifecycle_new_name,
    has_active_children,
    rename_changespec_with_references,
    save_diff_to_file,
)


def has_children(changespec: ChangeSpec, all_changespecs: list[ChangeSpec]) -> bool:
    """Check if any non-reverted ChangeSpec has this one as a parent.

    Args:
        changespec: The ChangeSpec to check for children
        all_changespecs: All ChangeSpecs to search through

    Returns:
        True if any non-reverted ChangeSpec has this one as parent, False otherwise
    """
    return has_active_children(changespec, all_changespecs)


def update_changespec_name_atomic(
    project_file: str, old_name: str, new_name: str
) -> None:
    """Update the NAME field of a specific ChangeSpec in the project file.

    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project_file: Path to the ProjectSpec file
        old_name: Current NAME value of the ChangeSpec
        new_name: New NAME value
    """
    with changespec_lock(project_file):
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        updated_lines = []
        for line in lines:
            if line.startswith("NAME:"):
                current_name = line.split(":", 1)[1].strip()
                if current_name == old_name:
                    updated_lines.append(f"NAME: {new_name}\n")
                    continue
            updated_lines.append(line)

        write_changespec_atomic(
            project_file,
            "".join(updated_lines),
            f"Rename ChangeSpec {old_name} to {new_name}",
        )


def revert_changespec(
    changespec: ChangeSpec, console: Console | None = None
) -> tuple[bool, str | None]:
    """Revert a ChangeSpec by pruning its CL and updating its status.

    This function:
    1. Validates that the ChangeSpec has a valid CL set
    2. Validates that the ChangeSpec has no children
    3. Renames the ChangeSpec by appending `__<N>` suffix
    4. Saves the diff to `~/.gai/reverted/<new_name>.diff`
    5. Runs `bb_hg_prune <name>` to remove the revision
    6. Updates STATUS to "Reverted" and CL to "None"

    Args:
        changespec: The ChangeSpec to revert
        console: Optional Rich Console for output

    Returns:
        Tuple of (success, error_message)
    """
    # Validate CL is set
    if changespec.cl is None:
        return (False, "ChangeSpec does not have a valid CL set")

    # Kill any running processes before reverting
    log_fn = (lambda msg: console.print(f"[cyan]{msg}[/cyan]")) if console else None
    kill_and_persist_all_running_processes(
        changespec,
        changespec.file_path,
        changespec.name,
        "Killed hook running on reverted CL.",
        log_fn=log_fn,
    )

    # Get all changespecs to check for children and name conflicts
    all_changespecs = find_all_changespecs()

    # Validate no children
    if has_children(changespec, all_changespecs):
        return (
            False,
            "Cannot revert: other ChangeSpecs have this one as their parent",
        )

    # Get workspace directory
    workspace_dir = get_workspace_directory_for_changespec(changespec)
    if not workspace_dir:
        return (False, "Could not determine workspace directory")

    if not os.path.isdir(workspace_dir):
        return (False, f"Workspace directory does not exist: {workspace_dir}")

    # Calculate new name with suffix
    new_name = calculate_lifecycle_new_name(changespec, all_changespecs)

    if console:
        console.print(f"[cyan]Renaming ChangeSpec to: {new_name}[/cyan]")

    # Save diff to file
    success, error = save_diff_to_file(changespec, new_name, workspace_dir, "reverted")
    if not success:
        return (False, f"Failed to save diff: {error}")

    if console:
        diff_path = Path.home() / ".gai" / "reverted" / f"{new_name}.diff"
        console.print(f"[green]Saved diff to: {diff_path}[/green]")

    # Run bb_hg_prune
    provider = get_vcs_provider(workspace_dir)
    success, error = provider.prune(changespec.name, workspace_dir)
    if not success:
        return (False, f"Failed to prune revision: {error}")

    if console:
        console.print(f"[green]Pruned revision: {changespec.name}[/green]")

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
                f"[green]Renamed ChangeSpec: {changespec.name} → {new_name}[/green]"
            )

    # Update STATUS to Reverted
    success, _, error, _ = transition_changespec_status(
        changespec.file_path,
        new_name,  # Use the new name after rename
        "Reverted",
        validate=False,
    )
    if not success:
        return (False, f"Failed to update status: {error}")

    # Reset CL to None
    reset_changespec_cl(changespec.file_path, new_name)

    if console:
        console.print("[green]Status updated to Reverted, CL removed[/green]")

    return (True, None)
