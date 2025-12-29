"""Restore operations for reverted ChangeSpecs."""

import os
import subprocess
import sys
from pathlib import Path

from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gai_utils import get_workspace_directory_for_changespec, strip_reverted_suffix
from running_field import (
    update_running_field_cl_name,
)

from .changespec import ChangeSpec, find_all_changespecs
from .revert import update_changespec_name_atomic


def list_reverted_changespecs() -> list[ChangeSpec]:
    """Find all ChangeSpecs with "Reverted" status.

    Returns:
        List of ChangeSpecs that have status "Reverted"
    """
    all_changespecs = find_all_changespecs()
    return [cs for cs in all_changespecs if cs.status == "Reverted"]


def _run_bb_hg_update(target: str, workspace_dir: str) -> tuple[bool, str | None]:
    """Run bb_hg_update command to update to a target.

    Args:
        target: The target to update to (e.g., "p4head" or parent name)
        workspace_dir: The workspace directory to run command in

    Returns:
        Tuple of (success, error_message)
    """
    try:
        result = subprocess.run(
            ["bb_hg_update", target],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            return (False, f"bb_hg_update failed (cwd: {workspace_dir}): {error_msg}")

        return (True, None)
    except FileNotFoundError:
        return (False, f"bb_hg_update command not found (cwd: {workspace_dir})")
    except Exception as e:
        return (False, f"Error running bb_hg_update (cwd: {workspace_dir}): {e}")


def _run_hg_import(diff_file: str, workspace_dir: str) -> tuple[bool, str | None]:
    """Run hg import --no-commit to apply a diff file.

    Args:
        diff_file: Path to the diff file to import
        workspace_dir: The workspace directory to run command in

    Returns:
        Tuple of (success, error_message)
    """
    try:
        result = subprocess.run(
            ["hg", "import", "--no-commit", diff_file],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            return (False, f"hg import failed: {error_msg}")

        return (True, None)
    except FileNotFoundError:
        return (False, "hg command not found")
    except Exception as e:
        return (False, f"Error running hg import: {e}")


def _run_gai_commit(name: str, workspace_dir: str) -> tuple[bool, str | None]:
    """Run gai commit command.

    Args:
        name: The CL name to use (without project prefix)
        workspace_dir: The workspace directory to run command in

    Returns:
        Tuple of (success, error_message)
    """
    try:
        result = subprocess.run(
            ["gai", "commit", name],
            cwd=workspace_dir,
            capture_output=False,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return (False, "gai commit failed")

        return (True, None)
    except FileNotFoundError:
        return (False, "gai command not found")
    except Exception as e:
        return (False, f"Error running gai commit: {e}")


def _clear_hook_status_lines_for_last_history(
    changespec: ChangeSpec, base_name: str, console: Console | None = None
) -> tuple[bool, str | None]:
    """Clear hook status lines for the last HISTORY entry so hooks will rerun.

    This removes the status line for the last HISTORY entry from every hook,
    allowing gai loop to rerun all hooks after a restore.

    Args:
        changespec: The ChangeSpec being restored
        base_name: The base name (after stripping __<N> suffix)
        console: Optional Rich Console for output

    Returns:
        Tuple of (success, error_message)
    """
    from .changespec import HookEntry
    from .hooks import get_last_history_entry_id, update_changespec_hooks_field

    # Skip if no hooks
    if not changespec.hooks:
        return (True, None)

    # Get the last HISTORY entry ID
    last_history_entry_id = get_last_history_entry_id(changespec)
    if last_history_entry_id is None:
        # No history entries, nothing to clear
        return (True, None)

    # Build updated hooks list with status lines for last HISTORY entry removed
    updated_hooks: list[HookEntry] = []
    hooks_cleared = 0

    for hook in changespec.hooks:
        if hook.status_lines:
            # Keep all status lines except the one for the last HISTORY entry
            remaining_status_lines = [
                sl
                for sl in hook.status_lines
                if sl.history_entry_num != last_history_entry_id
            ]
            if len(remaining_status_lines) < len(hook.status_lines):
                hooks_cleared += 1
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

    # Update the project file with the cleared hooks
    # Use base_name since the ChangeSpec may have been renamed
    success = update_changespec_hooks_field(
        changespec.file_path,
        base_name,
        updated_hooks,
    )

    if not success:
        return (False, "Failed to clear hook status lines")

    if console and hooks_cleared > 0:
        console.print(
            f"[green]Cleared status for {hooks_cleared} hook(s) - "
            f"will be rerun by gai loop[/green]"
        )

    return (True, None)


def restore_changespec(
    changespec: ChangeSpec, console: Console | None = None
) -> tuple[bool, str | None]:
    """Restore a reverted ChangeSpec by re-applying its diff and creating a new CL.

    This function:
    1. Validates that the ChangeSpec has "Reverted" status
    2. Renames the ChangeSpec to remove the __<N> suffix
    3. Runs bb_hg_update to either p4head or the parent
    4. Runs hg import --no-commit to apply the stashed diff
    5. Runs gai commit with the base name (which will find the renamed ChangeSpec)

    Args:
        changespec: The ChangeSpec to restore
        console: Optional Rich Console for output

    Returns:
        Tuple of (success, error_message)
    """
    # Validate status is "Reverted"
    if changespec.status != "Reverted":
        return (False, f"ChangeSpec status is '{changespec.status}', not 'Reverted'")

    # Get workspace directory
    workspace_dir = get_workspace_directory_for_changespec(changespec)
    if not workspace_dir:
        return (False, "Could not determine workspace directory")

    if not os.path.isdir(workspace_dir):
        return (False, f"Workspace directory does not exist: {workspace_dir}")

    # Extract base name (without __<N> suffix)
    base_name = strip_reverted_suffix(changespec.name)
    if console:
        console.print(f"[cyan]Base name: {base_name}[/cyan]")

    # Rename the ChangeSpec to remove the __<N> suffix
    # This allows gai commit to find it and use its description
    if base_name != changespec.name:
        try:
            update_changespec_name_atomic(
                changespec.file_path, changespec.name, base_name
            )
            if console:
                console.print(
                    f"[green]Renamed ChangeSpec: {changespec.name} → {base_name}[/green]"
                )
            # Also update any RUNNING field entries that reference the old name
            update_running_field_cl_name(
                changespec.file_path, changespec.name, base_name
            )
        except Exception as e:
            return (False, f"Failed to rename ChangeSpec: {e}")

    # Clear hook status lines for the last HISTORY entry so hooks will rerun
    success, error = _clear_hook_status_lines_for_last_history(
        changespec, base_name, console
    )
    if not success:
        return (False, error)

    # Determine update target
    update_target = changespec.parent if changespec.parent else "p4head"
    if console:
        console.print(f"[cyan]Updating to: {update_target}[/cyan]")

    # Run bb_hg_update
    success, error = _run_bb_hg_update(update_target, workspace_dir)
    if not success:
        return (False, error)

    if console:
        console.print(f"[green]Updated to: {update_target}[/green]")

    # Check for diff file
    diff_file = Path.home() / ".gai" / "reverted" / f"{changespec.name}.diff"
    if not diff_file.exists():
        return (False, f"Diff file not found: {diff_file}")

    if console:
        console.print(f"[cyan]Importing diff: {diff_file}[/cyan]")

    # Run hg import
    success, error = _run_hg_import(str(diff_file), workspace_dir)
    if not success:
        return (False, error)

    if console:
        console.print("[green]Diff imported successfully[/green]")

    # Run gai commit - it will find the renamed ChangeSpec and use its description
    if console:
        console.print(f"[cyan]Running gai commit {base_name}...[/cyan]")

    success, error = _run_gai_commit(base_name, workspace_dir)
    if not success:
        return (False, error)

    if console:
        console.print("[green]ChangeSpec restored successfully[/green]")

    return (True, None)
