"""CL submission and comment status checking for ChangeSpecs."""

import os
import re
import subprocess
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from gai_utils import get_workspace_directory_for_changespec

from .changespec import ChangeSpec, find_all_changespecs

# Statuses that should be checked for submission/comments
# Note: "Changes Requested" has been replaced by the COMMENTS field
SYNCABLE_STATUSES = ["Mailed"]

# Re-export for backward compatibility
from .constants import DEFAULT_ZOMBIE_TIMEOUT_SECONDS  # noqa: E402, F401


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
    workspace_dir = get_workspace_directory_for_changespec(changespec)

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
