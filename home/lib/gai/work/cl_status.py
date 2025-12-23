"""CL submission and comment status checking for ChangeSpecs."""

import os
import re
import subprocess
import sys
import tempfile
import time

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from running_field import get_workspace_directory as get_workspace_dir

from .changespec import ChangeSpec, find_all_changespecs

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


def check_presubmit_status(changespec: ChangeSpec) -> int:
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


def presubmit_needs_check(presubmit_value: str | None) -> bool:
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


def get_presubmit_file_path(presubmit_value: str) -> str | None:
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


def get_presubmit_file_age_seconds(file_path: str) -> float | None:
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


def update_changespec_presubmit_tag(
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
