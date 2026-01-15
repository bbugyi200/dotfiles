"""CL submission and comment status checking for ChangeSpecs."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from .changespec import ChangeSpec, find_all_changespecs

# Statuses that should be checked for submission/comments
# Note: "Changes Requested" has been replaced by the COMMENTS field
SYNCABLE_STATUSES = ["Mailed"]


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
