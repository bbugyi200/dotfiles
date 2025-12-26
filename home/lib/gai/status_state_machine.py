"""
State machine for managing ChangeSpec STATUS field transitions.

This module provides centralized logic for validating and performing
STATUS field transitions across all gai workflows.
"""

import logging
import os
import re
import tempfile
from datetime import datetime

logger = logging.getLogger(__name__)


def remove_workspace_suffix(status: str) -> str:
    """Remove workspace share suffix from a status value.

    Args:
        status: STATUS value, possibly with workspace suffix

    Returns:
        STATUS value without workspace suffix
    """
    # Remove pattern: " (<project>_<N>)" at the end
    return re.sub(r" \([a-zA-Z0-9_-]+_\d+\)$", "", status)


# All valid STATUS values for ChangeSpecs
# Note: In-progress statuses (ending with "...") have been removed.
# Workspace tracking is now done via the RUNNING field in ProjectSpec files.
# Note: "Changes Requested" status has been replaced by the COMMENTS field.
VALID_STATUSES = [
    "Drafted",
    "Mailed",
    "Submitted",
    "Reverted",
]


# Valid state transitions
# Key: current status, Value: list of allowed next statuses
VALID_TRANSITIONS: dict[str, list[str]] = {
    "Drafted": ["Mailed"],
    "Mailed": ["Submitted"],
    # Submitted is terminal
    "Submitted": [],
    # Reverted is terminal
    "Reverted": [],
}


def _is_valid_transition(from_status: str, to_status: str) -> bool:
    """
    Check if a status transition is valid.

    NOTE: Workspace suffixes are stripped before validation, so:
    - "Creating EZ CL... (fig_3)" is treated as "Creating EZ CL..."
    - "Finishing TDD CL... (fig_2)" is treated as "Finishing TDD CL..."

    Args:
        from_status: Current status (possibly with workspace suffix)
        to_status: Target status (possibly with workspace suffix)

    Returns:
        True if transition is allowed, False otherwise
    """
    # Strip workspace suffixes before validation
    from_status_base = remove_workspace_suffix(from_status)
    to_status_base = remove_workspace_suffix(to_status)

    if from_status_base not in VALID_STATUSES:
        logger.warning(f"Invalid from_status: {from_status_base}")
        return False

    if to_status_base not in VALID_STATUSES:
        logger.warning(f"Invalid to_status: {to_status_base}")
        return False

    allowed_transitions = VALID_TRANSITIONS.get(from_status_base, [])
    return to_status_base in allowed_transitions


def _read_current_status(project_file: str, changespec_name: str) -> str | None:
    """
    Read the current STATUS of a ChangeSpec from the project file.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to read

    Returns:
        Current STATUS value, or None if not found
    """
    try:
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        in_target_changespec = False
        current_name = None

        for line in lines:
            # Check if this is a NAME field
            if line.startswith("NAME:"):
                current_name = line.split(":", 1)[1].strip()
                in_target_changespec = current_name == changespec_name

            # Read STATUS if we're in the target ChangeSpec
            if in_target_changespec and line.startswith("STATUS:"):
                return line.split(":", 1)[1].strip()

        return None
    except Exception as e:
        logger.error(f"Error reading status from {project_file}: {e}")
        return None


def _update_changespec_status_atomic(
    project_file: str, changespec_name: str, new_status: str
) -> None:
    """
    Update the STATUS field of a specific ChangeSpec in the project file.

    This is an atomic operation that writes to a temp file first, then
    atomically renames it to the target file.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        new_status: New STATUS value (e.g., "In Progress")
    """
    with open(project_file, encoding="utf-8") as f:
        lines = f.readlines()

    # Find the ChangeSpec and update its STATUS
    updated_lines = []
    in_target_changespec = False
    current_name = None

    for line in lines:
        # Check if this is a NAME field
        if line.startswith("NAME:"):
            current_name = line.split(":", 1)[1].strip()
            in_target_changespec = current_name == changespec_name

        # Update STATUS if we're in the target ChangeSpec
        if in_target_changespec and line.startswith("STATUS:"):
            # Replace the STATUS line
            updated_lines.append(f"STATUS: {new_status}\n")
            in_target_changespec = False  # Done updating this ChangeSpec
        else:
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


def _update_changespec_cl_atomic(
    project_file: str, changespec_name: str, new_cl: str | None
) -> None:
    """
    Update the CL field of a specific ChangeSpec in the project file.

    This is an atomic operation that writes to a temp file first, then
    atomically renames it to the target file. If the CL field doesn't exist
    and new_cl is not None, it will be added before the STATUS field.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        new_cl: New CL value (None to reset/remove)
    """
    with open(project_file, encoding="utf-8") as f:
        lines = f.readlines()

    # Find the ChangeSpec and update its CL
    updated_lines = []
    in_target_changespec = False
    current_name = None
    found_cl_line = False

    for line in lines:
        # Check if this is a NAME field
        if line.startswith("NAME:"):
            current_name = line.split(":", 1)[1].strip()
            in_target_changespec = current_name == changespec_name
            found_cl_line = False  # Reset for new ChangeSpec

        # Update CL if we're in the target ChangeSpec
        if in_target_changespec and line.startswith("CL:"):
            found_cl_line = True
            # Replace the CL line, or skip it entirely if resetting to None
            if new_cl is not None:
                updated_lines.append(f"CL: {new_cl}\n")
            # When new_cl is None, we simply skip this line (don't append it)
        elif in_target_changespec and line.startswith("STATUS:") and not found_cl_line:
            # CL field doesn't exist - add it before STATUS if we have a new value
            if new_cl is not None:
                updated_lines.append(f"CL: {new_cl}\n")
                found_cl_line = True
            updated_lines.append(line)
        else:
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


def reset_changespec_cl(project_file: str, changespec_name: str) -> bool:
    """
    Remove the CL field from a ChangeSpec.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update

    Returns:
        True if reset succeeded, False otherwise
    """
    try:
        _update_changespec_cl_atomic(project_file, changespec_name, None)
        logger.info(f"Removed CL field for {changespec_name}")
        return True
    except Exception as e:
        logger.error(f"Error resetting CL for {changespec_name}: {e}")
        return False


def transition_changespec_status(
    project_file: str,
    changespec_name: str,
    new_status: str,
    validate: bool = True,
) -> tuple[bool, str | None, str | None]:
    """
    Transition a ChangeSpec to a new STATUS with optional validation.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        new_status: New STATUS value
        validate: If True, validate the transition is allowed

    Returns:
        Tuple of (success, old_status, error_msg)
        - success: True if transition succeeded
        - old_status: Previous status value (None if not found)
        - error_msg: Error message if failed (None if succeeded)
    """
    # Read current status
    old_status = _read_current_status(project_file, changespec_name)

    if old_status is None:
        error_msg = f"ChangeSpec '{changespec_name}' not found in {project_file}"
        logger.error(error_msg)
        return (False, None, error_msg)

    # Skip validation if not requested (e.g., for rollback operations)
    if not validate:
        logger.info(
            f"Transitioning {changespec_name}: '{old_status}' -> '{new_status}' "
            f"(validation skipped)"
        )
        _update_changespec_status_atomic(project_file, changespec_name, new_status)
        return (True, old_status, None)

    # Validate transition
    if not _is_valid_transition(old_status, new_status):
        error_msg = (
            f"Invalid status transition for '{changespec_name}': "
            f"'{old_status}' -> '{new_status}'. "
            f"Allowed transitions from '{old_status}': "
            f"{VALID_TRANSITIONS.get(old_status, [])}"
        )
        logger.error(error_msg)
        return (False, old_status, error_msg)

    # Perform transition
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        f"[{timestamp}] Transitioning {changespec_name}: "
        f"'{old_status}' -> '{new_status}'"
    )

    _update_changespec_status_atomic(project_file, changespec_name, new_status)

    return (True, old_status, None)
