"""CL submission and comment status checking for ChangeSpecs."""

import os
import re
import subprocess
import tempfile
import time

from rich.console import Console

from .changespec import ChangeSpec, find_all_changespecs
from .sync_cache import clear_cache_entry, should_check, update_last_checked

# Statuses that should be checked for submission/comments
SYNCABLE_STATUSES = ["Mailed", "Changes Requested"]

# Time in seconds after which a presubmit is considered a zombie (24 hours)
PRESUBMIT_ZOMBIE_THRESHOLD_SECONDS = 24 * 60 * 60


def _extract_cl_number(cl_url: str | None) -> str | None:
    """Extract the CL number from a CL URL.

    Args:
        cl_url: The CL URL in the format http://cl/123456789

    Returns:
        The CL number as a string, or None if the URL is invalid or None.
    """
    if not cl_url:
        return None

    # Match http://cl/<number> or https://cl/<number>
    match = re.match(r"https?://cl/(\d+)", cl_url)
    if match:
        return match.group(1)

    return None


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
    # Extract CL number from the CL URL
    cl_number = _extract_cl_number(changespec.cl)
    if not cl_number:
        # No CL URL or invalid format - can't check submission status
        return False

    # Get the workspace directory to run the command from
    workspace_dir = _get_workspace_directory(changespec)

    try:
        result = subprocess.run(
            ["is_cl_submitted", cl_number],
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
    """Check if a CL has pending comments using the critique_comments command.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        True if there are pending comments, False otherwise.
    """
    # Get the workspace directory to run the command from
    workspace_dir = _get_workspace_directory(changespec)

    try:
        result = subprocess.run(
            ["critique_comments", changespec.name],
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


def _check_presubmit_status(changespec: ChangeSpec) -> int:
    """Check if a presubmit has completed using the is_presubmit_complete command.

    Args:
        changespec: The ChangeSpec to check.

    Returns:
        0 if presubmit completed successfully
        1 if presubmit completed with failure
        2 if presubmit is still running
        -1 if there was an error checking
    """
    # Get the workspace directory to run the command from
    workspace_dir = _get_workspace_directory(changespec)

    try:
        result = subprocess.run(
            ["is_presubmit_complete", changespec.name],
            capture_output=True,
            text=True,
            cwd=workspace_dir,
        )
        return result.returncode
    except FileNotFoundError:
        # Command not found - return error
        return -1
    except Exception:
        # Any other error
        return -1


def _presubmit_needs_check(presubmit_value: str | None) -> bool:
    """Check if a PRESUBMIT field value needs to be checked.

    A presubmit needs to be checked if it has a value and doesn't have
    a terminal tag: (FAILED), (PASSED), or (ZOMBIE).

    Args:
        presubmit_value: The PRESUBMIT field value.

    Returns:
        True if the presubmit needs to be checked, False otherwise.
    """
    if not presubmit_value:
        return False

    # Check for terminal tags
    terminal_tags = ["(FAILED)", "(PASSED)", "(ZOMBIE)"]
    for tag in terminal_tags:
        if tag in presubmit_value:
            return False

    return True


def _get_presubmit_file_path(presubmit_value: str) -> str | None:
    """Extract the file path from a PRESUBMIT field value.

    The PRESUBMIT field may contain a path followed by tags, e.g.:
    "~/.gai/projects/proj/presubmit_output/name_20250101_120000.log (RUNNING)"

    Args:
        presubmit_value: The PRESUBMIT field value.

    Returns:
        The expanded file path, or None if invalid.
    """
    if not presubmit_value:
        return None

    # Extract path (everything before any tag in parentheses)
    path = presubmit_value.split(" (")[0].strip()

    # Expand ~ to home directory
    return os.path.expanduser(path)


def _get_presubmit_file_age_seconds(file_path: str) -> float | None:
    """Get the age of a presubmit file in seconds.

    Args:
        file_path: Path to the presubmit file.

    Returns:
        Age in seconds, or None if file doesn't exist.
    """
    try:
        mtime = os.path.getmtime(file_path)
        return time.time() - mtime
    except OSError:
        return None


def _update_changespec_presubmit_tag(
    project_file: str,
    changespec_name: str,
    new_presubmit_value: str,
) -> bool:
    """Update the PRESUBMIT field value in the project file.

    Args:
        project_file: Path to the ProjectSpec file.
        changespec_name: NAME of the ChangeSpec to update.
        new_presubmit_value: New PRESUBMIT value (path with tag).

    Returns:
        True if update succeeded, False otherwise.
    """
    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        # Find the ChangeSpec and update PRESUBMIT field
        updated_lines = []
        in_target_changespec = False
        current_name = None

        for line in lines:
            # Check if this is a NAME field
            if line.startswith("NAME:"):
                current_name = line.split(":", 1)[1].strip()
                in_target_changespec = current_name == changespec_name
                updated_lines.append(line)
                continue

            # Update PRESUBMIT if we're in the target ChangeSpec
            if in_target_changespec and line.startswith("PRESUBMIT:"):
                updated_lines.append(f"PRESUBMIT: {new_presubmit_value}\n")
                continue

            updated_lines.append(line)

        # Write to temp file then atomically rename
        project_dir = os.path.dirname(project_file)
        fd, temp_path = tempfile.mkstemp(dir=project_dir, prefix=".tmp_", suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)
            os.replace(temp_path, project_file)
            return True
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    except Exception:
        return False


def _sync_presubmit(
    changespec: ChangeSpec,
    console: Console,
    force: bool = False,
) -> bool:
    """Sync presubmit status for a ChangeSpec.

    Checks ChangeSpecs with PRESUBMIT field that doesn't have terminal tags
    (FAILED, PASSED, ZOMBIE).

    Updates the PRESUBMIT field with appropriate tag based on:
    - Presubmit completed successfully -> adds (PASSED)
    - Presubmit failed -> adds (FAILED)
    - Presubmit running > 24h -> adds (ZOMBIE)
    - Still running -> no change

    Args:
        changespec: The ChangeSpec to check.
        console: Rich Console object for output.
        force: If True, skip the time-based check.

    Returns:
        True if the PRESUBMIT field was updated, False otherwise.
    """
    # Only check if presubmit needs checking
    if not _presubmit_needs_check(changespec.presubmit):
        return False

    # Check if enough time has passed (unless forced)
    cache_key = f"presubmit:{changespec.name}"
    if not force and not should_check(cache_key):
        return False

    # Update the last_checked timestamp
    update_last_checked(cache_key)

    # Get the presubmit value (guaranteed not None due to _presubmit_needs_check above)
    presubmit_value = changespec.presubmit
    if not presubmit_value:
        return False

    # Get the presubmit file path
    presubmit_path = _get_presubmit_file_path(presubmit_value)
    if not presubmit_path:
        return False

    # Print that we're checking
    console.print(f"[cyan]Checking presubmit for '{changespec.name}'...[/cyan]")

    # Check if presubmit is a zombie (running > 24h)
    file_age = _get_presubmit_file_age_seconds(presubmit_path)
    if file_age is not None and file_age > PRESUBMIT_ZOMBIE_THRESHOLD_SECONDS:
        # Mark as zombie
        new_value = f"{presubmit_value} (ZOMBIE)"
        if _update_changespec_presubmit_tag(
            changespec.file_path, changespec.name, new_value
        ):
            console.print(
                f"[yellow]Presubmit for '{changespec.name}' marked as ZOMBIE "
                f"(running > 24h)[/yellow]"
            )
            return True
        return False

    # Check presubmit completion status
    presubmit_result = _check_presubmit_status(changespec)

    if presubmit_result == 0:
        # Presubmit succeeded - add (PASSED) tag
        new_value = f"{presubmit_value} (PASSED)"
        if _update_changespec_presubmit_tag(
            changespec.file_path, changespec.name, new_value
        ):
            console.print(
                f"[green]Presubmit succeeded for '{changespec.name}'![/green]"
            )
            clear_cache_entry(cache_key)
            return True

    elif presubmit_result == 1:
        # Presubmit failed - add (FAILED) tag
        new_value = f"{presubmit_value} (FAILED)"
        if _update_changespec_presubmit_tag(
            changespec.file_path, changespec.name, new_value
        ):
            console.print(
                f"[red]Presubmit failed for '{changespec.name}'. "
                f"See log: {presubmit_path}[/red]"
            )
            return True

    elif presubmit_result == 2:
        # Presubmit still running
        console.print(f"[dim]Presubmit still running for '{changespec.name}'[/dim]")

    else:
        # Error checking presubmit status
        console.print(
            f"[yellow]Could not check presubmit status for '{changespec.name}'[/yellow]"
        )

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
    # Only check syncable statuses (strip workspace suffix for comparison)
    # Import here to avoid issues at module load time
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from status_state_machine import remove_workspace_suffix

    base_status = remove_workspace_suffix(changespec.status)
    if base_status not in SYNCABLE_STATUSES:
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
    # Only check submission if parent is submitted (or no parent), since CLs
    # cannot be submitted until their parent is submitted
    if _is_parent_submitted(changespec) and _is_cl_submitted(changespec):
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
    # Only check comments if parent is submitted (or no parent), since CLs
    # cannot receive meaningful reviews until their parent is submitted
    if (
        changespec.status == "Mailed"
        and _is_parent_submitted(changespec)
        and _has_pending_comments(changespec)
    ):
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

    # If status is "Changes Requested", check if comments have been cleared
    # If no pending comments remain, transition back to "Mailed"
    if changespec.status == "Changes Requested" and not _has_pending_comments(
        changespec
    ):
        success, old_status, error_msg = transition_changespec_status(
            changespec.file_path,
            changespec.name,
            "Mailed",
            validate=False,  # Skip validation for this automatic transition
        )

        if success:
            console.print(
                f"[green]Comments cleared for '{changespec.name}'! "
                f"Status updated: {old_status} → Mailed[/green]"
            )
            return True
        else:
            console.print(
                f"[yellow]Comments cleared for '{changespec.name}' but "
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

    Performs two types of syncs:
    1. Status sync: Checks ChangeSpecs with "Mailed" or "Changes Requested" status
       for submission/comment updates.
    2. Presubmit sync: Checks ChangeSpecs with PRESUBMIT field that doesn't have
       terminal tags (FAILED, PASSED, ZOMBIE) for presubmit completion.

    Args:
        console: Rich Console object for output.
        force: If True, skip the time-based check and always check.

    Returns:
        Number of ChangeSpecs that were updated.
    """
    all_changespecs = find_all_changespecs()
    updated_count = 0

    for changespec in all_changespecs:
        # Sync status (submission/comments)
        if _sync_changespec(changespec, console, force):
            updated_count += 1

        # Sync presubmit status
        if _sync_presubmit(changespec, console, force):
            updated_count += 1

    return updated_count
