"""Revert operations for ChangeSpecs."""

import os
import re
import subprocess
import sys
from pathlib import Path

from rich.console import Console

# Add parent directory to path for status_state_machine import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from gai_utils import (
    get_next_suffix_number,
    get_workspace_directory_for_changespec,
    has_suffix,
)
from running_field import (
    get_claimed_workspaces,
    release_workspace,
    update_running_field_cl_name,
)
from status_state_machine import (
    reset_changespec_cl,
    transition_changespec_status,
    update_parent_references_atomic,
)

from .changespec import (
    ChangeSpec,
    changespec_lock,
    find_all_changespecs,
    write_changespec_atomic,
)
from .comments.operations import (
    mark_comment_agents_as_killed,
    update_changespec_comments_field,
)
from .hooks.execution import update_changespec_hooks_field
from .hooks.processes import (
    kill_running_agent_processes,
    kill_running_hook_processes,
    kill_running_mentor_processes,
    mark_hook_agents_as_killed,
    mark_hooks_as_killed,
    mark_mentor_agents_as_killed,
)
from .mentors import update_changespec_mentors_field


def _extract_mentor_workflow_from_suffix(suffix: str) -> str | None:
    """Extract workflow name from mentor suffix.

    Args:
        suffix: Mentor suffix in format "mentor_{name}-{PID}-{timestamp}"

    Returns:
        Workflow name in format "axe(mentor)-{name}-{timestamp}" or None
    """
    match = re.match(r"^mentor_(.+)-\d+-(\d{6}_\d{6})$", suffix)
    if match:
        mentor_name = match.group(1)
        timestamp = match.group(2)
        return f"axe(mentor)-{mentor_name}-{timestamp}"
    return None


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

    # Kill any running hook processes before reverting
    killed_processes = kill_running_hook_processes(changespec)
    if killed_processes:
        if console:
            console.print(
                f"[cyan]Killed {len(killed_processes)} running hook process(es)[/cyan]"
            )
        # Update hooks to mark as killed and persist
        if changespec.hooks:
            updated_hooks = mark_hooks_as_killed(
                changespec.hooks,
                killed_processes,
                "Killed hook running on reverted CL.",
            )
            update_changespec_hooks_field(
                changespec.file_path, changespec.name, updated_hooks
            )

    # Kill any running agent processes before reverting
    killed_hook_agents, killed_comment_agents = kill_running_agent_processes(changespec)
    total_killed_agents = len(killed_hook_agents) + len(killed_comment_agents)
    if total_killed_agents:
        if console:
            console.print(
                f"[cyan]Killed {total_killed_agents} running agent process(es)[/cyan]"
            )
        # Update hooks to mark agents as killed and persist
        if killed_hook_agents and changespec.hooks:
            updated_hooks = mark_hook_agents_as_killed(
                changespec.hooks, killed_hook_agents
            )
            update_changespec_hooks_field(
                changespec.file_path, changespec.name, updated_hooks
            )
        # Update comments to mark agents as killed and persist
        if killed_comment_agents and changespec.comments:
            updated_comments = mark_comment_agents_as_killed(
                changespec.comments, killed_comment_agents
            )
            update_changespec_comments_field(
                changespec.file_path, changespec.name, updated_comments
            )

    # Kill any running mentor processes before reverting
    killed_mentors = kill_running_mentor_processes(changespec)
    if killed_mentors:
        if console:
            console.print(
                f"[cyan]Killed {len(killed_mentors)} running mentor process(es)[/cyan]"
            )
        # Update mentors to mark as killed and persist
        if changespec.mentors:
            updated_mentors = mark_mentor_agents_as_killed(
                changespec.mentors, killed_mentors
            )
            update_changespec_mentors_field(
                changespec.file_path, changespec.name, updated_mentors
            )

        # Release workspaces claimed by killed mentor processes
        for _entry, status_line, _pid in killed_mentors:
            if not status_line.suffix:
                continue

            workflow = _extract_mentor_workflow_from_suffix(status_line.suffix)
            if not workflow:
                continue

            for claim in get_claimed_workspaces(changespec.file_path):
                if claim.workflow == workflow and claim.cl_name == changespec.name:
                    release_workspace(
                        changespec.file_path,
                        claim.workspace_num,
                        workflow,
                        changespec.name,
                    )
                    if console:
                        console.print(
                            f"[cyan]Released workspace #{claim.workspace_num} "
                            f"for killed mentor[/cyan]"
                        )
                    break

    # Get all changespecs to check for children and name conflicts
    all_changespecs = find_all_changespecs()

    # Validate no children
    if _has_children(changespec, all_changespecs):
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
    # Skip adding suffix if this is a WIP ChangeSpec that already has one
    if changespec.status == "WIP" and has_suffix(changespec.name):
        new_name = changespec.name  # Keep existing name
    else:
        existing_names = {cs.name for cs in all_changespecs}
        suffix = get_next_suffix_number(changespec.name, existing_names)
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

    # Rename the ChangeSpec (skip if name is unchanged, e.g., WIP with existing suffix)
    if new_name != changespec.name:
        try:
            update_changespec_name_atomic(
                changespec.file_path, changespec.name, new_name
            )
            # Also update any RUNNING field entries that reference the old name
            update_running_field_cl_name(
                changespec.file_path, changespec.name, new_name
            )
            # Update PARENT fields in any child ChangeSpecs
            update_parent_references_atomic(
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
