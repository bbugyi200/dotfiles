"""
Constants and validation helpers for STATUS field state machine.

This module defines the valid statuses and transitions for ChangeSpecs.
"""

import logging
import re

logger = logging.getLogger(__name__)


def remove_workspace_suffix(status: str) -> str:
    """Remove workspace share suffix and READY TO MAIL suffix from a status value.

    Args:
        status: STATUS value, possibly with workspace or READY TO MAIL suffix

    Returns:
        STATUS value without suffixes (base status only)
    """
    # Remove pattern: " (<project>_<N>)" at the end
    result = re.sub(r" \([a-zA-Z0-9_-]+_\d+\)$", "", status)
    # Remove READY TO MAIL suffix pattern: " - (!: READY TO MAIL)"
    result = re.sub(r" - \(!\: READY TO MAIL\)$", "", result)
    return result


# All valid STATUS values for ChangeSpecs
# Note: In-progress statuses (ending with "...") have been removed.
# Workspace tracking is now done via the RUNNING field in ProjectSpec files.
# Note: "Changes Requested" status has been replaced by the COMMENTS field.
VALID_STATUSES = [
    "WIP",
    "Drafted",
    "Mailed",
    "Submitted",
    "Reverted",
]


# Valid state transitions
# Key: current status, Value: list of allowed next statuses
VALID_TRANSITIONS: dict[str, list[str]] = {
    "WIP": ["Drafted"],
    "Drafted": ["Mailed", "WIP"],
    "Mailed": ["Submitted"],
    # Submitted is terminal
    "Submitted": [],
    # Reverted is terminal
    "Reverted": [],
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
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
