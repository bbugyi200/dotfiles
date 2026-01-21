"""
State machine for managing ChangeSpec STATUS field transitions.

This package provides centralized logic for validating and performing
STATUS field transitions across all gai workflows.
"""

from .constants import (
    VALID_STATUSES,
    VALID_TRANSITIONS,
    is_valid_transition,
    remove_workspace_suffix,
)
from .field_updates import (
    reset_changespec_cl,
    update_changespec_cl_atomic,
    update_changespec_parent_atomic,
    update_parent_references_atomic,
)
from .mail_suffix import (
    add_ready_to_mail_suffix,
    remove_ready_to_mail_suffix,
)
from .transitions import (
    SiblingRevertResult,
    transition_changespec_status,
)

__all__ = [
    # Constants
    "VALID_STATUSES",
    "VALID_TRANSITIONS",
    # Validation
    "is_valid_transition",
    "remove_workspace_suffix",
    # Field updates
    "reset_changespec_cl",
    "update_changespec_cl_atomic",
    "update_changespec_parent_atomic",
    "update_parent_references_atomic",
    # Mail suffix
    "add_ready_to_mail_suffix",
    "remove_ready_to_mail_suffix",
    # Transitions
    "SiblingRevertResult",
    "transition_changespec_status",
]
