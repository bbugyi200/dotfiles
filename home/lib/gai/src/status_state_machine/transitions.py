"""
Main status transition logic for ChangeSpecs.

This module contains the core transition_changespec_status function and related helpers.
"""

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ace.changespec import changespec_lock, write_changespec_atomic

from .constants import VALID_TRANSITIONS, is_valid_transition
from .field_updates import apply_status_update, read_status_from_lines

if TYPE_CHECKING:
    from rich.console import Console

logger = logging.getLogger(__name__)


@dataclass
class SiblingRevertResult:
    """Result of reverting a sibling WIP ChangeSpec."""

    name: str
    success: bool
    error: str | None = None


def _revert_sibling_wip_changespecs(
    project_file: str,
    base_name: str,
    excluded_name: str,
    console: "Console | None" = None,
) -> list[SiblingRevertResult]:
    """Revert all WIP ChangeSpecs with the same basename.

    When a WIP ChangeSpec transitions to Drafted and has its suffix stripped,
    any other WIP ChangeSpecs with the same base name are automatically reverted
    since they are now obsolete.

    Args:
        project_file: Path to the project file.
        base_name: The base name without suffix (e.g., "foo_bar").
        excluded_name: The original suffixed name that was just transitioned
            (don't revert this one).
        console: Optional Rich console for output.

    Returns:
        List of SiblingRevertResult for each sibling that was attempted to be
        reverted.
    """
    from ace.changespec import parse_project_file
    from ace.revert import revert_changespec
    from gai_utils import strip_reverted_suffix

    changespecs = parse_project_file(project_file)
    results: list[SiblingRevertResult] = []

    for cs in changespecs:
        # Skip the one we just transitioned
        if cs.name == excluded_name:
            continue

        # Check if same basename and is WIP
        cs_base = strip_reverted_suffix(cs.name)
        if cs_base == base_name and cs.status == "WIP":
            logger.info(f"Auto-reverting sibling WIP ChangeSpec: {cs.name}")
            if console:
                console.print(f"[yellow]Auto-reverting sibling WIP:[/] {cs.name}")
            success, error = revert_changespec(cs, console=console)
            if not success:
                logger.warning(f"Failed to revert {cs.name}: {error}")
            results.append(
                SiblingRevertResult(name=cs.name, success=success, error=error)
            )

    return results


def _handle_suffix_strip(
    project_file: str,
    suffixed_name: str,
    base_name: str,
    console: "Console | None" = None,
) -> list[SiblingRevertResult]:
    """Handle stripping __<N> suffix when transitioning from WIP to Drafted.

    Args:
        project_file: Path to the project file.
        suffixed_name: The current name with suffix (e.g., "foo_bar__1").
        base_name: The base name without suffix (e.g., "foo_bar").
        console: Optional Rich console for output.

    Returns:
        List of SiblingRevertResult for reverted siblings.
    """
    from ace.revert import update_changespec_name_atomic
    from running_field import get_workspace_directory, update_running_field_cl_name

    from .field_updates import update_parent_references_atomic

    # Update NAME field
    update_changespec_name_atomic(project_file, suffixed_name, base_name)

    # Rename the CL in Mercurial to match the new name
    project_basename = Path(project_file).stem
    try:
        workspace_dir = get_workspace_directory(project_basename)

        # First checkout the CL we want to rename
        update_result = subprocess.run(
            ["bb_hg_update", suffixed_name],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if update_result.returncode != 0:
            logger.warning(
                f"Failed to checkout CL {suffixed_name}: {update_result.stderr}"
            )
        else:
            # Now rename the CL
            rename_result = subprocess.run(
                ["bb_hg_rename", base_name],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if rename_result.returncode != 0:
                logger.warning(f"Failed to rename CL: {rename_result.stderr}")
    except subprocess.TimeoutExpired:
        logger.warning("bb_hg_update or bb_hg_rename timed out")
    except RuntimeError as e:
        logger.warning(f"Could not get workspace directory: {e}")

    # Update PARENT references in other ChangeSpecs
    update_parent_references_atomic(project_file, suffixed_name, base_name)

    # Update RUNNING field entries
    update_running_field_cl_name(project_file, suffixed_name, base_name)

    # Auto-revert sibling WIP ChangeSpecs with the same basename
    return _revert_sibling_wip_changespecs(
        project_file, base_name, suffixed_name, console
    )


def _handle_suffix_append(
    project_file: str,
    base_name: str,
    suffixed_name: str,
) -> None:
    """Handle appending __<N> suffix when transitioning from Drafted to WIP.

    Args:
        project_file: Path to the project file.
        base_name: The base name without suffix (e.g., "foo_bar").
        suffixed_name: The new name with suffix (e.g., "foo_bar__1").
    """
    from ace.revert import update_changespec_name_atomic
    from running_field import get_workspace_directory, update_running_field_cl_name

    from .field_updates import update_parent_references_atomic

    # Update NAME field
    update_changespec_name_atomic(project_file, base_name, suffixed_name)

    # Rename the CL in Mercurial to match the new name
    project_basename = Path(project_file).stem
    try:
        workspace_dir = get_workspace_directory(project_basename)

        # First checkout the CL we want to rename
        update_result = subprocess.run(
            ["bb_hg_update", base_name],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if update_result.returncode != 0:
            logger.warning(f"Failed to checkout CL {base_name}: {update_result.stderr}")
        else:
            # Now rename the CL
            rename_result = subprocess.run(
                ["bb_hg_rename", suffixed_name],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if rename_result.returncode != 0:
                logger.warning(f"Failed to rename CL: {rename_result.stderr}")
    except subprocess.TimeoutExpired:
        logger.warning("bb_hg_update or bb_hg_rename timed out")
    except RuntimeError as e:
        logger.warning(f"Could not get workspace directory: {e}")

    # Update PARENT references in other ChangeSpecs
    update_parent_references_atomic(project_file, base_name, suffixed_name)

    # Update RUNNING field entries
    update_running_field_cl_name(project_file, base_name, suffixed_name)


def _handle_wip_transition(
    project_file: str,
    changespec_name: str,
    old_status: str,
    new_status: str,
    lines: list[str],
    validate: bool,
) -> tuple[bool, str | None, str | None, tuple[str, str] | None]:
    """Handle transition to WIP status.

    Returns:
        Tuple of (success, old_status, error_msg, suffix_append_info)
    """
    from ace.changespec import find_all_changespecs
    from ace.mentors import set_mentor_wip_flags
    from gai_utils import get_next_suffix_number

    all_changespecs = find_all_changespecs()
    invalid_children = [
        cs
        for cs in all_changespecs
        if cs.parent == changespec_name and cs.status not in ("WIP", "Reverted")
    ]
    if invalid_children:
        child_info = ", ".join(f"{cs.name} ({cs.status})" for cs in invalid_children)
        error_msg = (
            f"Cannot transition '{changespec_name}' to WIP: "
            f"children must be WIP or Reverted. "
            f"Invalid children: {child_info}"
        )
        logger.error(error_msg)
        return (False, old_status, error_msg, None)

    if validate and not is_valid_transition(old_status, new_status):
        error_msg = (
            f"Invalid status transition for '{changespec_name}': "
            f"'{old_status}' -> '{new_status}'. "
            f"Allowed transitions from '{old_status}': "
            f"{VALID_TRANSITIONS.get(old_status, [])}"
        )
        logger.error(error_msg)
        return (False, old_status, error_msg, None)

    # Valid transition to WIP
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = (
        f"[{timestamp}] Transitioning {changespec_name}: "
        f"'{old_status}' -> '{new_status}'"
    )
    if not validate:
        log_msg += " (validation skipped)"
    logger.info(log_msg)

    updated_content = apply_status_update(lines, changespec_name, new_status)
    write_changespec_atomic(
        project_file,
        updated_content,
        f"Update STATUS to {new_status} for {changespec_name}",
    )

    # Add __<N> suffix when transitioning to WIP
    existing_names = {cs.name for cs in all_changespecs}
    suffix_num = get_next_suffix_number(changespec_name, existing_names)
    suffix_append_info = (
        changespec_name,
        f"{changespec_name}__{suffix_num}",
    )

    # Set #WIP flag on mentors
    set_mentor_wip_flags(project_file, changespec_name)

    return (True, old_status, None, suffix_append_info)


def _handle_non_wip_transition(
    project_file: str,
    changespec_name: str,
    old_status: str,
    new_status: str,
    lines: list[str],
    validate: bool,
) -> tuple[bool, str | None, str | None, tuple[str, str] | None]:
    """Handle transition to non-WIP/non-Reverted status (e.g., Drafted, Mailed, Submitted).

    Returns:
        Tuple of (success, old_status, error_msg, suffix_strip_info)
    """
    from ace.changespec import parse_project_file

    # Check parent constraint
    changespecs = parse_project_file(project_file)
    current_cs = next((cs for cs in changespecs if cs.name == changespec_name), None)
    if current_cs and current_cs.parent:
        parent_cs = next(
            (cs for cs in changespecs if cs.name == current_cs.parent), None
        )
        if parent_cs and parent_cs.status == "WIP":
            error_msg = (
                f"Cannot transition '{changespec_name}' to {new_status}: "
                f"parent '{current_cs.parent}' is WIP. "
                f"Children of WIP ChangeSpecs must be WIP or Reverted."
            )
            logger.error(error_msg)
            return (False, old_status, error_msg, None)

    # Validate transition if requested
    if validate and not is_valid_transition(old_status, new_status):
        error_msg = (
            f"Invalid status transition for '{changespec_name}': "
            f"'{old_status}' -> '{new_status}'. "
            f"Allowed transitions from '{old_status}': "
            f"{VALID_TRANSITIONS.get(old_status, [])}"
        )
        logger.error(error_msg)
        return (False, old_status, error_msg, None)

    # Perform transition
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = (
        f"[{timestamp}] Transitioning {changespec_name}: "
        f"'{old_status}' -> '{new_status}'"
    )
    if not validate:
        log_msg += " (validation skipped)"
    logger.info(log_msg)

    updated_content = apply_status_update(lines, changespec_name, new_status)
    write_changespec_atomic(
        project_file,
        updated_content,
        f"Update STATUS to {new_status} for {changespec_name}",
    )

    suffix_strip_info = None

    # Clear #WIP from mentors when transitioning from WIP to Drafted
    if old_status == "WIP" and new_status == "Drafted":
        from ace.mentors import clear_mentor_wip_flags
        from gai_utils import has_suffix, strip_reverted_suffix

        clear_mentor_wip_flags(project_file, changespec_name)

        # Check if we need to strip suffix (done outside lock)
        if has_suffix(changespec_name):
            suffix_strip_info = (
                changespec_name,
                strip_reverted_suffix(changespec_name),
            )

    return (True, old_status, None, suffix_strip_info)


def _handle_reverted_transition(
    project_file: str,
    changespec_name: str,
    old_status: str,
    new_status: str,
    lines: list[str],
    validate: bool,
) -> tuple[bool, str | None, str | None]:
    """Handle transition to Reverted status.

    Returns:
        Tuple of (success, old_status, error_msg)
    """
    if validate and not is_valid_transition(old_status, new_status):
        error_msg = (
            f"Invalid status transition for '{changespec_name}': "
            f"'{old_status}' -> '{new_status}'. "
            f"Allowed transitions from '{old_status}': "
            f"{VALID_TRANSITIONS.get(old_status, [])}"
        )
        logger.error(error_msg)
        return (False, old_status, error_msg)

    # Perform transition to Reverted
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = (
        f"[{timestamp}] Transitioning {changespec_name}: "
        f"'{old_status}' -> '{new_status}'"
    )
    if not validate:
        log_msg += " (validation skipped)"
    logger.info(log_msg)

    updated_content = apply_status_update(lines, changespec_name, new_status)
    write_changespec_atomic(
        project_file,
        updated_content,
        f"Update STATUS to {new_status} for {changespec_name}",
    )
    return (True, old_status, None)


def transition_changespec_status(
    project_file: str,
    changespec_name: str,
    new_status: str,
    validate: bool = True,
    console: "Console | None" = None,
) -> tuple[bool, str | None, str | None, list[SiblingRevertResult]]:
    """
    Transition a ChangeSpec to a new STATUS with optional validation.

    Acquires a lock for the entire read-validate-write cycle.

    Args:
        project_file: Path to the ProjectSpec file
        changespec_name: NAME of the ChangeSpec to update
        new_status: New STATUS value
        validate: If True, validate the transition is allowed
        console: Optional Rich console for output during sibling reverts

    Returns:
        Tuple of (success, old_status, error_msg, sibling_revert_results)
        - success: True if transition succeeded
        - old_status: Previous status value (None if not found)
        - error_msg: Error message if failed (None if succeeded)
        - sibling_revert_results: List of SiblingRevertResult for reverted siblings
    """
    # Track if we need to strip/append suffix after lock releases
    suffix_strip_info: tuple[str, str] | None = None
    suffix_append_info: tuple[str, str] | None = None
    result: tuple[bool, str | None, str | None] | None = None
    sibling_results: list[SiblingRevertResult] = []

    with changespec_lock(project_file):
        with open(project_file, encoding="utf-8") as f:
            lines = f.readlines()

        # Read current status
        old_status = read_status_from_lines(lines, changespec_name)

        if old_status is None:
            error_msg = f"ChangeSpec '{changespec_name}' not found in {project_file}"
            logger.error(error_msg)
            result = (False, None, error_msg)

        elif new_status == "WIP":
            success, old_st, err, suffix_append_info = _handle_wip_transition(
                project_file, changespec_name, old_status, new_status, lines, validate
            )
            result = (success, old_st, err)

        elif new_status not in ("WIP", "Reverted"):
            success, old_st, err, suffix_strip_info = _handle_non_wip_transition(
                project_file, changespec_name, old_status, new_status, lines, validate
            )
            result = (success, old_st, err)

        else:
            # new_status == "Reverted"
            result = _handle_reverted_transition(
                project_file, changespec_name, old_status, new_status, lines, validate
            )

    # Strip __<N> suffix when transitioning from WIP to Drafted (outside lock)
    if suffix_strip_info is not None:
        suffixed_name, base_name = suffix_strip_info
        sibling_results = _handle_suffix_strip(
            project_file, suffixed_name, base_name, console
        )

    # Append __<N> suffix when transitioning from Drafted to WIP (outside lock)
    if suffix_append_info is not None:
        base_name, suffixed_name = suffix_append_info
        _handle_suffix_append(project_file, base_name, suffixed_name)

    assert result is not None
    return (result[0], result[1], result[2], sibling_results)
