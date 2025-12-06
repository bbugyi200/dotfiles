"""CL submission status checking for ChangeSpecs."""

import subprocess

from rich.console import Console

from .changespec import ChangeSpec
from .sync_cache import clear_cache_entry, should_check, update_last_checked


def _is_cl_submitted(changespec_name: str) -> bool:
    """Check if a CL has been submitted using the is_cl_submitted command.

    Args:
        changespec_name: The NAME field value of the ChangeSpec.

    Returns:
        True if the CL has been submitted, False otherwise.
    """
    try:
        result = subprocess.run(
            ["is_cl_submitted", changespec_name],
            capture_output=True,
            text=True,
        )
        # Command exits with 0 if submitted, non-zero if not
        return result.returncode == 0
    except FileNotFoundError:
        # Command not found - assume not submitted
        return False
    except Exception:
        # Any other error - assume not submitted
        return False


def check_and_update_submission_status(
    changespec: ChangeSpec,
    console: Console,
    force: bool = False,
) -> bool:
    """Check if a mailed CL has been submitted and update status if so.

    This function only checks ChangeSpecs with "Mailed" status and only if
    enough time has passed since the last check (or if force=True).

    Args:
        changespec: The ChangeSpec to check.
        console: Rich Console object for output.
        force: If True, skip the time-based check and always check.

    Returns:
        True if the status was updated to Submitted, False otherwise.
    """
    # Only check mailed ChangeSpecs
    if changespec.status != "Mailed":
        return False

    # Check if enough time has passed (unless forced)
    if not force and not should_check(changespec.name):
        return False

    # Update the last_checked timestamp
    update_last_checked(changespec.name)

    # Check if submitted
    if _is_cl_submitted(changespec.name):
        # Import here to avoid circular imports
        import os
        import sys

        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from status_state_machine import transition_changespec_status

        success, old_status, error_msg = transition_changespec_status(
            changespec.file_path,
            changespec.name,
            "Submitted",
            validate=False,  # Skip validation for this automatic transition
        )

        if success:
            console.print(
                f"[green]CL for '{changespec.name}' has been submitted! "
                f"Status updated: {old_status} → Submitted[/green]"
            )
            # Clear the cache entry since we no longer need to track it
            clear_cache_entry(changespec.name)
            return True
        else:
            console.print(
                f"[yellow]CL for '{changespec.name}' was submitted but "
                f"failed to update status: {error_msg}[/yellow]"
            )

    return False


def check_mailed_changespecs_for_submission(
    changespecs: list[ChangeSpec],
    console: Console,
) -> int:
    """Check all mailed ChangeSpecs for submission status.

    Only checks ChangeSpecs that haven't been checked recently
    (based on MIN_CHECK_INTERVAL_SECONDS).

    Args:
        changespecs: List of ChangeSpecs to check.
        console: Rich Console object for output.

    Returns:
        Number of ChangeSpecs that were updated to Submitted.
    """
    updated_count = 0

    for changespec in changespecs:
        if check_and_update_submission_status(changespec, console):
            updated_count += 1

    return updated_count
