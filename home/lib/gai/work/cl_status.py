"""CL submission and comment status checking for ChangeSpecs."""

import os
import re
import subprocess
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from running_field import get_workspace_directory as get_workspace_dir

from .changespec import ChangeSpec, find_all_changespecs

# Statuses that should be checked for submission/comments
SYNCABLE_STATUSES = ["Mailed", "Changes Requested"]

# Time in seconds after which a hook is considered a zombie (24 hours)
HOOK_ZOMBIE_THRESHOLD_SECONDS = 24 * 60 * 60

# Time in seconds after which a fix-hook timestamp suffix is considered stale (1 hour)
FIX_HOOK_STALE_THRESHOLD_SECONDS = 60 * 60


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
        The workspace directory path, or None if bb_get_workspace fails.
    """
    # Extract project basename from file path
    project_basename = os.path.splitext(os.path.basename(changespec.file_path))[0]

    try:
        return get_workspace_dir(project_basename)
    except RuntimeError:
        return None


def is_parent_submitted(changespec: ChangeSpec) -> bool:
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


def is_cl_submitted(changespec: ChangeSpec) -> bool:
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


def has_pending_comments(changespec: ChangeSpec) -> bool:
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
