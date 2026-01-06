"""Status-related operations for ChangeSpecs."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from status_state_machine import VALID_STATUSES

# Status that triggers revert workflow
STATUS_REVERTED = "Reverted"


def get_available_statuses(current_status: str) -> list[str]:
    """Get list of available statuses for selection.

    Excludes:
    - Current status
    - Statuses ending with "..." (transient/automated states)

    Args:
        current_status: The current status value

    Returns:
        List of available status strings
    """
    return [
        status
        for status in VALID_STATUSES
        if status != current_status and not status.endswith("...")
    ]
