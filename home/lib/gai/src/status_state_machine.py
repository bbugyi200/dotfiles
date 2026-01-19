"""
State machine for managing ChangeSpec STATUS field transitions.

This module provides centralized logic for validating and performing
STATUS field transitions across all gai workflows.
"""

import logging
import re
from datetime import datetime

from ace.changespec import changespec_lock, get_base_status, write_changespec_atomic

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


def _apply_status_update(
    lines: list[str], changespec_name: str, new_status: str
) -> str:
    """Apply STATUS field update to file lines.

    Args:
        lines: Current file lines.
        changespec_name: NAME of the ChangeSpec to update.
        new_status: New STATUS value.

    Returns:
        Updated file content as a string.
    """
    updated_lines = []
    in_target_changespec = False

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

    return "".join(updated_lines)


def _apply_cl_update(lines: list[str], changespec_name: str, new_cl: str | None) -> str:
    """Apply CL field update to file lines.

    Args:
        lines: Current file lines.
        changespec_name: NAME of the ChangeSpec to update.
        new_cl: New CL value (None to reset/remove).

    Returns:
        Updated file content as a string.
    """
    updated_lines = []
    in_target_changespec = False
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

    return "".join(updated_lines)


def update_changespec_cl_atomic(
    project_file: str, changespec_name: str, new_cl: str | None
) -> None:
    """Update the CL field of a specific ChangeSpec in the project file.

    Acquires a lock for the entire read-modify-write cycle.
    If the CL field doesn't exist and new_cl is not None, it will be
    added before the STATUS field.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        new_cl: New CL value (None to reset/remove)
    """
    commit_msg = (
        f"Update CL to {new_cl} for {changespec_name}"
        if new_cl
        else f"Remove CL for {changespec_name}"
    )

    with changespec_lock(project_file):
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        updated_content = _apply_cl_update(lines, changespec_name, new_cl)

        write_changespec_atomic(project_file, updated_content, commit_msg)


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
        update_changespec_cl_atomic(project_file, changespec_name, None)
        logger.info(f"Removed CL field for {changespec_name}")
        return True
    except Exception as e:
        logger.error(f"Error resetting CL for {changespec_name}: {e}")
        return False


def _read_status_from_lines(lines: list[str], changespec_name: str) -> str | None:
    """Read STATUS from file lines (unlocked helper).

    Args:
        lines: File lines to search.
        changespec_name: NAME of the ChangeSpec to find.

    Returns:
        Current STATUS value, or None if not found.
    """
    in_target_changespec = False
    for line in lines:
        if line.startswith("NAME:"):
            current_name = line.split(":", 1)[1].strip()
            in_target_changespec = current_name == changespec_name
        if in_target_changespec and line.startswith("STATUS:"):
            return line.split(":", 1)[1].strip()
    return None


def transition_changespec_status(
    project_file: str,
    changespec_name: str,
    new_status: str,
    validate: bool = True,
) -> tuple[bool, str | None, str | None]:
    """
    Transition a ChangeSpec to a new STATUS with optional validation.

    Acquires a lock for the entire read-validate-write cycle.

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
    # Track if we need to strip suffix after lock releases
    suffix_strip_info: tuple[str, str] | None = None
    result: tuple[bool, str | None, str | None] | None = None

    with changespec_lock(project_file):
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        # Read current status
        old_status = _read_status_from_lines(lines, changespec_name)

        if old_status is None:
            error_msg = f"ChangeSpec '{changespec_name}' not found in {project_file}"
            logger.error(error_msg)
            result = (False, None, error_msg)
        elif not validate:
            # Skip validation if not requested (e.g., for rollback operations)
            logger.info(
                f"Transitioning {changespec_name}: '{old_status}' -> '{new_status}' "
                f"(validation skipped)"
            )
            updated_content = _apply_status_update(lines, changespec_name, new_status)
            write_changespec_atomic(
                project_file,
                updated_content,
                f"Update STATUS to {new_status} for {changespec_name}",
            )

            # Clear #WIP from mentors when transitioning from WIP to Drafted
            if old_status == "WIP" and new_status == "Drafted":
                from ace.mentors import clear_mentor_wip_flags

                clear_mentor_wip_flags(project_file, changespec_name)

                # Check if we need to strip suffix (done outside lock)
                from gai_utils import has_suffix, strip_reverted_suffix

                if has_suffix(changespec_name):
                    suffix_strip_info = (
                        changespec_name,
                        strip_reverted_suffix(changespec_name),
                    )

            result = (True, old_status, None)
        elif not _is_valid_transition(old_status, new_status):
            # Validate transition
            error_msg = (
                f"Invalid status transition for '{changespec_name}': "
                f"'{old_status}' -> '{new_status}'. "
                f"Allowed transitions from '{old_status}': "
                f"{VALID_TRANSITIONS.get(old_status, [])}"
            )
            logger.error(error_msg)
            result = (False, old_status, error_msg)
        else:
            # Perform transition
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                f"[{timestamp}] Transitioning {changespec_name}: "
                f"'{old_status}' -> '{new_status}'"
            )

            updated_content = _apply_status_update(lines, changespec_name, new_status)
            write_changespec_atomic(
                project_file,
                updated_content,
                f"Update STATUS to {new_status} for {changespec_name}",
            )

            # Clear #WIP from mentors when transitioning from WIP to Drafted
            if old_status == "WIP" and new_status == "Drafted":
                from ace.mentors import clear_mentor_wip_flags

                clear_mentor_wip_flags(project_file, changespec_name)

                # Check if we need to strip suffix (done outside lock)
                from gai_utils import has_suffix, strip_reverted_suffix

                if has_suffix(changespec_name):
                    suffix_strip_info = (
                        changespec_name,
                        strip_reverted_suffix(changespec_name),
                    )

            result = (True, old_status, None)

    # Strip __<N> suffix when transitioning from WIP to Drafted (outside lock)
    if suffix_strip_info is not None:
        suffixed_name, base_name = suffix_strip_info
        import subprocess
        from pathlib import Path

        from ace.revert import update_changespec_name_atomic
        from running_field import get_workspace_directory, update_running_field_cl_name

        # Update NAME field
        update_changespec_name_atomic(project_file, suffixed_name, base_name)

        # Rename the CL in Mercurial to match the new name
        project_basename = Path(project_file).stem
        try:
            workspace_dir = get_workspace_directory(project_basename)
            rename_result = subprocess.run(
                ["bb_hg_rename", base_name],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
            )
            if rename_result.returncode != 0:
                logger.warning(f"Failed to rename CL: {rename_result.stderr}")
        except RuntimeError as e:
            logger.warning(f"Could not get workspace directory: {e}")

        # Update PARENT references in other ChangeSpecs
        _update_parent_references_atomic(project_file, suffixed_name, base_name)

        # Update RUNNING field entries
        update_running_field_cl_name(project_file, suffixed_name, base_name)

    assert result is not None
    return result


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

        current_status = _read_status_from_lines(lines, changespec_name)
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
        updated_content = _apply_status_update(lines, changespec_name, new_status)
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

        current_status = _read_status_from_lines(lines, changespec_name)
        if current_status is None:
            logger.error(f"ChangeSpec '{changespec_name}' not found in {project_file}")
            return False

        # Check if suffix is present
        if "(!: READY TO MAIL)" not in current_status:
            return False

        new_status = current_status.replace(_READY_TO_MAIL_SUFFIX, "")
        updated_content = _apply_status_update(lines, changespec_name, new_status)
        write_changespec_atomic(
            project_file,
            updated_content,
            f"Remove READY TO MAIL suffix for {changespec_name}",
        )
        return True


def _apply_parent_update(
    lines: list[str], changespec_name: str, new_parent: str | None
) -> str:
    """Apply PARENT field update to file lines.

    Args:
        lines: Current file lines.
        changespec_name: NAME of the ChangeSpec to update.
        new_parent: New PARENT value (None to remove).

    Returns:
        Updated file content as a string.
    """
    updated_lines = []
    in_target_changespec = False
    found_parent_line = False
    in_description = False

    for line in lines:
        # Check if this is a NAME field
        if line.startswith("NAME:"):
            current_name = line.split(":", 1)[1].strip()
            in_target_changespec = current_name == changespec_name
            found_parent_line = False
            in_description = False

        # Track when we're in the DESCRIPTION field
        if in_target_changespec and line.startswith("DESCRIPTION:"):
            in_description = True

        # Update PARENT if we're in the target ChangeSpec
        if in_target_changespec and line.startswith("PARENT:"):
            found_parent_line = True
            # Replace the PARENT line, or skip it entirely if resetting to None
            if new_parent is not None:
                updated_lines.append(f"PARENT: {new_parent}\n")
            # When new_parent is None, we simply skip this line (don't append it)
        elif (
            in_target_changespec
            and in_description
            and (line.startswith("CL:") or line.startswith("STATUS:"))
            and not found_parent_line
        ):
            # PARENT field doesn't exist - add it before CL or STATUS if we have value
            if new_parent is not None:
                updated_lines.append(f"PARENT: {new_parent}\n")
                found_parent_line = True
            in_description = False
            updated_lines.append(line)
        else:
            # End description section when we hit another field
            if (
                in_target_changespec
                and in_description
                and line.startswith(
                    ("PARENT:", "CL:", "STATUS:", "TEST TARGETS:", "KICKSTART:")
                )
            ):
                in_description = False
            updated_lines.append(line)

    return "".join(updated_lines)


def update_changespec_parent_atomic(
    project_file: str, changespec_name: str, new_parent: str | None
) -> None:
    """Update the PARENT field of a specific ChangeSpec in the project file.

    Acquires a lock for the entire read-modify-write cycle.
    If the PARENT field doesn't exist and new_parent is not None, it will be
    added before the CL or STATUS field.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        new_parent: New PARENT value (None to remove)
    """
    commit_msg = (
        f"Update PARENT to {new_parent} for {changespec_name}"
        if new_parent
        else f"Remove PARENT for {changespec_name}"
    )

    with changespec_lock(project_file):
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        updated_content = _apply_parent_update(lines, changespec_name, new_parent)

        write_changespec_atomic(project_file, updated_content, commit_msg)


def _update_parent_references_atomic(
    project_file: str, old_name: str, new_name: str
) -> None:
    """Update all PARENT field references from old_name to new_name.

    Acquires a lock for the entire read-modify-write cycle.

    Args:
        project_file: Path to the ProjectSpec file
        old_name: The old name to replace in PARENT fields
        new_name: The new name to use in PARENT fields
    """
    with changespec_lock(project_file):
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        updated_lines = []
        for line in lines:
            if line.startswith("PARENT: "):
                current_parent = line[8:].strip()
                if current_parent == old_name:
                    updated_lines.append(f"PARENT: {new_name}\n")
                    continue
            updated_lines.append(line)

        write_changespec_atomic(
            project_file,
            "".join(updated_lines),
            f"Update PARENT references from {old_name} to {new_name}",
        )
