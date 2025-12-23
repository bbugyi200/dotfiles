"""Revert operations for ChangeSpecs."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console

# Add parent directory to path for status_state_machine import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from running_field import get_workspace_directory as get_workspace_dir
from status_state_machine import reset_changespec_cl, transition_changespec_status

from .changespec import ChangeSpec, find_all_changespecs


def _has_valid_cl(changespec: ChangeSpec) -> bool:
    """Check if a ChangeSpec has a valid CL set.

    Args:
        changespec: The ChangeSpec to check

    Returns:
        True if CL is set, False otherwise
    """
    return changespec.cl is not None


def _has_children(changespec: ChangeSpec, all_changespecs: list[ChangeSpec]) -> bool:
    """Check if any non-reverted ChangeSpec has this one as a parent.

    Args:
        changespec: The ChangeSpec to check for children
        all_changespecs: All ChangeSpecs to search through

    Returns:
        True if any non-reverted ChangeSpec has this one as parent, False otherwise
    """
    for cs in all_changespecs:
        if cs.parent == changespec.name and cs.status != "Reverted":
            return True
    return False


def _get_next_reverted_suffix(base_name: str, all_changespecs: list[ChangeSpec]) -> int:
    """Find the lowest positive integer N such that `<base_name>__<N>` doesn't exist.

    Args:
        base_name: The base name to append suffix to
        all_changespecs: All ChangeSpecs to check for conflicts

    Returns:
        The lowest available suffix number
    """
    existing_names = {cs.name for cs in all_changespecs}

    n = 1
    while f"{base_name}__{n}" in existing_names:
        n += 1

    return n


def update_changespec_name_atomic(
    project_file: str, old_name: str, new_name: str
) -> None:
    """Update the NAME field of a specific ChangeSpec in the project file.

    This is an atomic operation that writes to a temp file first, then
    atomically renames it to the target file.

    Args:
        project_file: Path to the ProjectSpec file
        old_name: Current NAME value of the ChangeSpec
        new_name: New NAME value
    """
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

    # Write to temp file in same directory, then atomically rename
    project_dir = os.path.dirname(project_file)
    fd, temp_path = tempfile.mkstemp(dir=project_dir, prefix=".tmp_", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)
        # Atomic rename
        os.replace(temp_path, project_file)
    except Exception:
        # Clean up temp file if something went wrong
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _get_workspace_directory(changespec: ChangeSpec) -> str | None:
    """Get the workspace directory for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to get workspace directory for

    Returns:
        The workspace directory path, or None if bb_get_workspace fails
    """
    # Extract project basename from file path
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    try:
        return get_workspace_dir(project_basename)
    except RuntimeError:
        return None


def _save_diff_to_file(
    changespec: ChangeSpec, new_name: str, workspace_dir: str
) -> tuple[bool, str | None]:
    """Save the diff of a ChangeSpec to the reverted directory.

    Runs `hg diff -c <name>` in the workspace directory and saves
    the output to `~/.gai/reverted/<new_name>.diff`.

    Args:
        changespec: The ChangeSpec to save diff for
        new_name: The new name (with suffix) for the diff file
        workspace_dir: The workspace directory to run hg diff in

    Returns:
        Tuple of (success, error_message)
    """
    # Create reverted directory if it doesn't exist
    reverted_dir = Path.home() / ".gai" / "reverted"
    reverted_dir.mkdir(parents=True, exist_ok=True)

    diff_file = reverted_dir / f"{new_name}.diff"

    try:
        result = subprocess.run(
            ["hg", "diff", "-c", changespec.name],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return (False, f"hg diff failed: {result.stderr.strip()}")

        # Write the diff output to file
        with open(diff_file, "w", encoding="utf-8") as f:
            f.write(result.stdout)

        return (True, None)
    except FileNotFoundError:
        return (False, "hg command not found")
    except Exception as e:
        return (False, f"Error saving diff: {e}")


def _run_bb_hg_prune(name: str, workspace_dir: str) -> tuple[bool, str | None]:
    """Run bb_hg_prune command on a revision.

    Args:
        name: The revision name to prune
        workspace_dir: The workspace directory to run command in

    Returns:
        Tuple of (success, error_message)
    """
    try:
        result = subprocess.run(
            ["bb_hg_prune", name],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            return (False, f"bb_hg_prune failed: {error_msg}")

        return (True, None)
    except FileNotFoundError:
        return (False, "bb_hg_prune command not found")
    except Exception as e:
        return (False, f"Error running bb_hg_prune: {e}")


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
    if not _has_valid_cl(changespec):
        return (False, "ChangeSpec does not have a valid CL set")

    # Get all changespecs to check for children and name conflicts
    all_changespecs = find_all_changespecs()

    # Validate no children
    if _has_children(changespec, all_changespecs):
        return (
            False,
            "Cannot revert: other ChangeSpecs have this one as their parent",
        )

    # Get workspace directory
    workspace_dir = _get_workspace_directory(changespec)
    if not workspace_dir:
        return (False, "Could not determine workspace directory")

    if not os.path.isdir(workspace_dir):
        return (False, f"Workspace directory does not exist: {workspace_dir}")

    # Calculate new name with suffix
    suffix = _get_next_reverted_suffix(changespec.name, all_changespecs)
    new_name = f"{changespec.name}__{suffix}"

    if console:
        console.print(f"[cyan]Renaming ChangeSpec to: {new_name}[/cyan]")

    # Save diff to file
    success, error = _save_diff_to_file(changespec, new_name, workspace_dir)
    if not success:
        return (False, f"Failed to save diff: {error}")

    if console:
        diff_path = Path.home() / ".gai" / "reverted" / f"{new_name}.diff"
        console.print(f"[green]Saved diff to: {diff_path}[/green]")

    # Run bb_hg_prune
    success, error = _run_bb_hg_prune(changespec.name, workspace_dir)
    if not success:
        return (False, f"Failed to prune revision: {error}")

    if console:
        console.print(f"[green]Pruned revision: {changespec.name}[/green]")

    # Rename the ChangeSpec
    try:
        update_changespec_name_atomic(changespec.file_path, changespec.name, new_name)
    except Exception as e:
        return (False, f"Failed to rename ChangeSpec: {e}")

    if console:
        console.print(
            f"[green]Renamed ChangeSpec: {changespec.name} → {new_name}[/green]"
        )

    # Update STATUS to Reverted
    success, _, error = transition_changespec_status(
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
