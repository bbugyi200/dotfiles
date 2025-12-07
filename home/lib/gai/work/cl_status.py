"""CL submission and comment status checking for ChangeSpecs."""

import os
import subprocess

from rich.console import Console

from .changespec import ChangeSpec, find_all_changespecs
from .sync_cache import clear_cache_entry, should_check, update_last_checked

# Statuses that should be checked for submission/comments
SYNCABLE_STATUSES = ["Mailed", "Changes Requested"]


def _get_workspace_directory(changespec: ChangeSpec) -> str | None:
    """Get the workspace directory for a ChangeSpec.

    Args:
        changespec: The ChangeSpec to get the workspace directory for.

    Returns:
        The workspace directory path, or None if environment variables are not set.
    """
    # Extract project basename from file path
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    # Get required environment variables
    goog_cloud_dir = os.environ.get("GOOG_CLOUD_DIR")
    goog_src_dir_base = os.environ.get("GOOG_SRC_DIR_BASE")

    if not goog_cloud_dir or not goog_src_dir_base:
        return None

    return os.path.join(goog_cloud_dir, project_basename, goog_src_dir_base)


def _is_parent_submitted(changespec: ChangeSpec) -> bool:
    """Check if a ChangeSpec's parent has been submitted.

    Args:
        changespec: The ChangeSpec to check the parent of.

    Returns:
        True if the parent is submitted or if there is no parent, False otherwise.
    """
    # No parent means we can proceed
    if changespec.parent is None:
        return True

    # Find all changespecs to locate the parent
    all_changespecs = find_all_changespecs()

    # Look for the parent by name
    for cs in all_changespecs:
        if cs.name == changespec.parent:
            return cs.status == "Submitted"

    # Parent not found - assume it's okay to proceed (might have been deleted)
    return True


def _is_cl_submitted(changespec: ChangeSpec) -> bool:
    """Check if a CL has been submitted using the is_cl_submitted command.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        True if the CL has been submitted, False otherwise.
    """
    # Get the workspace directory to run the command from
    workspace_dir = _get_workspace_directory(changespec)

    try:
        result = subprocess.run(
            ["is_cl_submitted", changespec.name],
            capture_output=True,
            text=True,
            cwd=workspace_dir,
        )
        # Command exits with 0 if submitted, non-zero if not
        return result.returncode == 0
    except FileNotFoundError:
        # Command not found - assume not submitted
        return False
    except Exception:
        # Any other error - assume not submitted
        return False


def _has_pending_comments(changespec: ChangeSpec) -> bool:
    """Check if a CL has pending comments using the critique_comment command.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        True if there are pending comments, False otherwise.
    """
    # Get the workspace directory to run the command from
    workspace_dir = _get_workspace_directory(changespec)

    try:
        result = subprocess.run(
            ["critique_comment", changespec.name],
            capture_output=True,
            text=True,
            cwd=workspace_dir,
        )
        # If there's any output, there are comments
        return bool(result.stdout.strip())
    except FileNotFoundError:
        # Command not found - assume no comments
        return False
    except Exception:
        # Any other error - assume no comments
        return False


def _sync_changespec(
    changespec: ChangeSpec,
    console: Console,
    force: bool = False,
) -> bool:
    """Sync a ChangeSpec by checking submission status and comments.

    This function checks ChangeSpecs with "Mailed" or "Changes Requested" status
    and only if enough time has passed since the last check (or if force=True).

    Checks performed:
    1. If CL is submitted -> status becomes "Submitted"
    2. If CL has pending comments (and status is "Mailed") -> status becomes
       "Changes Requested"

    Args:
        changespec: The ChangeSpec to check.
        console: Rich Console object for output.
        force: If True, skip the time-based check and always check.

    Returns:
        True if the status was updated, False otherwise.
    """
    # Only check syncable statuses
    if changespec.status not in SYNCABLE_STATUSES:
        return False

    # Only check if parent is submitted (or no parent)
    if not _is_parent_submitted(changespec):
        return False

    # Check if enough time has passed (unless forced)
    if not force and not should_check(changespec.name):
        return False

    # Update the last_checked timestamp
    update_last_checked(changespec.name)

    # Import here to avoid circular imports
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from status_state_machine import transition_changespec_status

    # Print that we're checking
    console.print(f"[cyan]Syncing '{changespec.name}'...[/cyan]")

    # First, check if submitted (applies to both Mailed and Changes Requested)
    if _is_cl_submitted(changespec):
        success, old_status, error_msg = transition_changespec_status(
            changespec.file_path,
            changespec.name,
            "Submitted",
            validate=False,  # Skip validation for this automatic transition
        )

        if success:
            console.print(
                f"[green]CL for '{changespec.name}' has been submitted! "
                f"Status updated: {old_status} → Submitted[/green]"
            )
            # Clear the cache entry since we no longer need to track it
            clear_cache_entry(changespec.name)
            return True
        else:
            console.print(
                f"[yellow]CL for '{changespec.name}' was submitted but "
                f"failed to update status: {error_msg}[/yellow]"
            )
            return False

    # If not submitted and status is "Mailed", check for comments
    if changespec.status == "Mailed" and _has_pending_comments(changespec):
        success, old_status, error_msg = transition_changespec_status(
            changespec.file_path,
            changespec.name,
            "Changes Requested",
            validate=False,  # Skip validation for this automatic transition
        )

        if success:
            console.print(
                f"[yellow]CL for '{changespec.name}' has pending comments! "
                f"Status updated: {old_status} → Changes Requested[/yellow]"
            )
            return True
        else:
            console.print(
                f"[yellow]CL for '{changespec.name}' has comments but "
                f"failed to update status: {error_msg}[/yellow]"
            )
            return False

    # No changes
    console.print(f"[dim]'{changespec.name}' is up to date[/dim]")
    return False


def sync_all_changespecs(
    console: Console,
    force: bool = False,
) -> int:
    """Sync all eligible ChangeSpecs across all projects.

    Checks all ChangeSpecs with "Mailed" or "Changes Requested" status
    that have no parent or a submitted parent, and haven't been checked
    recently (unless force=True).

    Args:
        console: Rich Console object for output.
        force: If True, skip the time-based check and always check.

    Returns:
        Number of ChangeSpecs that were updated.
    """
    all_changespecs = find_all_changespecs()
    updated_count = 0

    for changespec in all_changespecs:
        if _sync_changespec(changespec, console, force):
            updated_count += 1

    return updated_count
