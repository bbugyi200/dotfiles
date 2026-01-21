"""
Ready-to-mail suffix management for ChangeSpecs.

This module handles adding/removing the READY TO MAIL suffix from STATUS fields.
"""

import logging

from ace.changespec import changespec_lock, get_base_status, write_changespec_atomic

from .field_updates import apply_status_update, read_status_from_lines

logger = logging.getLogger(__name__)


# Suffix appended to STATUS line when ChangeSpec is ready to be mailed
_READY_TO_MAIL_SUFFIX = " - (!: READY TO MAIL)"


def add_ready_to_mail_suffix(project_file: str, changespec_name: str) -> bool:
    """Add the READY TO MAIL suffix to a ChangeSpec's STATUS line.

    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update

    Returns:
        True if the suffix was added, False if already present or error.
    """
    with changespec_lock(project_file):
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        current_status = read_status_from_lines(lines, changespec_name)
        if current_status is None:
            logger.error(f"ChangeSpec '{changespec_name}' not found in {project_file}")
            return False

        # Only add suffix if base status is "Drafted" (prevents race condition
        # where gai axe has stale changespec but file status is already "Mailed")
        if get_base_status(current_status) != "Drafted":
            return False

        # Check if suffix already present
        if "(!: READY TO MAIL)" in current_status:
            return False

        new_status = current_status + _READY_TO_MAIL_SUFFIX
        updated_content = apply_status_update(lines, changespec_name, new_status)
        write_changespec_atomic(
            project_file,
            updated_content,
            f"Add READY TO MAIL suffix for {changespec_name}",
        )
        return True


def remove_ready_to_mail_suffix(project_file: str, changespec_name: str) -> bool:
    """Remove the READY TO MAIL suffix from a ChangeSpec's STATUS line.

    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update

    Returns:
        True if the suffix was removed, False if not present or error.
    """
    with changespec_lock(project_file):
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        current_status = read_status_from_lines(lines, changespec_name)
        if current_status is None:
            logger.error(f"ChangeSpec '{changespec_name}' not found in {project_file}")
            return False

        # Check if suffix is present
        if "(!: READY TO MAIL)" not in current_status:
            return False

        new_status = current_status.replace(_READY_TO_MAIL_SUFFIX, "")
        updated_content = apply_status_update(lines, changespec_name, new_status)
        write_changespec_atomic(
            project_file,
            updated_content,
            f"Remove READY TO MAIL suffix for {changespec_name}",
        )
        return True
