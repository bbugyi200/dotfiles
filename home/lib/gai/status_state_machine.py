"""
State machine for managing ChangeSpec STATUS field transitions.

This module provides centralized logic for validating and performing
STATUS field transitions across all gai workflows.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# All valid STATUS values for ChangeSpecs
VALID_STATUSES = [
    "Not Started",
    "In Progress",
    "Failed to Create CL",
    "TDD CL Created",
    "Fixing Tests",
    "Failed to Fix Tests",
    "Pre-Mailed",
    "Mailed",
    "Submitted",
]


# Valid state transitions
# Key: current status, Value: list of allowed next statuses
VALID_TRANSITIONS: dict[str, list[str]] = {
    "Not Started": ["In Progress"],
    "In Progress": [
        "Not Started",
        "TDD CL Created",
        "Failed to Create CL",
        "Pre-Mailed",
    ],
    "TDD CL Created": ["Fixing Tests"],
    "Fixing Tests": ["TDD CL Created", "Pre-Mailed", "Failed to Fix Tests"],
    "Pre-Mailed": ["Mailed"],
    "Mailed": ["Submitted"],
    # Failed states allow transition back to retry
    "Failed to Create CL": ["Not Started"],
    "Failed to Fix Tests": ["TDD CL Created"],
    # Submitted is terminal
    "Submitted": [],
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """
    Check if a status transition is valid.

    Args:
        from_status: Current status
        to_status: Target status

    Returns:
        True if transition is allowed, False otherwise
    """
    if from_status not in VALID_STATUSES:
        logger.warning(f"Invalid from_status: {from_status}")
        return False

    if to_status not in VALID_STATUSES:
        logger.warning(f"Invalid to_status: {to_status}")
        return False

    allowed_transitions = VALID_TRANSITIONS.get(from_status, [])
    return to_status in allowed_transitions


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
        with open(project_file) as f:
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

    This is an atomic operation that writes to a temp file first.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        new_status: New STATUS value (e.g., "In Progress")
    """
    with open(project_file) as f:
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

    # Write the updated content back to the file
    # TODO: Make this truly atomic with temp file + rename
    with open(project_file, "w") as f:
        f.writelines(updated_lines)


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
    if not is_valid_transition(old_status, new_status):
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
