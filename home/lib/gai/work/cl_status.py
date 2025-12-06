"""CL submission status checking for ChangeSpecs."""

import os
import subprocess

from rich.console import Console

from .changespec import ChangeSpec, find_all_changespecs
from .sync_cache import clear_cache_entry, should_check, update_last_checked


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


def check_and_update_submission_status(
    changespec: ChangeSpec,
    console: Console,
    force: bool = False,
) -> bool:
    """Check if a mailed CL has been submitted and update status if so.

    This function only checks ChangeSpecs with "Mailed" status and only if
    enough time has passed since the last check (or if force=True).

    Args:
        changespec: The ChangeSpec to check.
        console: Rich Console object for output.
        force: If True, skip the time-based check and always check.

    Returns:
        True if the status was updated to Submitted, False otherwise.
    """
    # Only check mailed ChangeSpecs
    if changespec.status != "Mailed":
        return False

    # Only check if parent is submitted (or no parent)
    if not _is_parent_submitted(changespec):
        return False

    # Check if enough time has passed (unless forced)
    if not force and not should_check(changespec.name):
        return False

    # Update the last_checked timestamp
    update_last_checked(changespec.name)

    # Check if submitted
    if _is_cl_submitted(changespec):
        # Import here to avoid circular imports
        import sys

        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from status_state_machine import transition_changespec_status

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


def check_mailed_changespecs_for_submission(
    changespecs: list[ChangeSpec],
    console: Console,
) -> int:
    """Check all mailed ChangeSpecs for submission status.

    Only checks ChangeSpecs that haven't been checked recently
    (based on MIN_CHECK_INTERVAL_SECONDS).

    Args:
        changespecs: List of ChangeSpecs to check.
        console: Rich Console object for output.

    Returns:
        Number of ChangeSpecs that were updated to Submitted.
    """
    updated_count = 0

    for changespec in changespecs:
        if check_and_update_submission_status(changespec, console):
            updated_count += 1

    return updated_count
